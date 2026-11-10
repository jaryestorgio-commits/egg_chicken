from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import re
from urllib.parse import quote
from zoneinfo import ZoneInfo

from flask import Blueprint, request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from extensions import db
from models import AuditLog, Category, Discount, Order, OrderItem, Payment, Product, User
from services.order_service import OrderError, cancel_order, serialize_order
from services.product_service import adjust_product_stock
from services.notification_service import record_admin_notification
from utils.auth import current_user, roles_required
from utils.responses import error_response, success_response
from utils.validators import parse_money, parse_positive_int, request_data, required_string


admin_bp = Blueprint("admin", __name__)
ORDER_STATUSES = {"pending", "confirmed", "processing", "shipped", "delivered", "cancelled"}
STORE_TIMEZONE = ZoneInfo("Asia/Manila")
LOW_STOCK_THRESHOLD = 10
DISCOUNT_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,31}$")


def serialize_discount(discount):
    return {
        "id": discount.id,
        "code": discount.code,
        "name": discount.name,
        "discount_type": discount.discount_type,
        "value": float(discount.value),
        "starts_at": discount.starts_at.isoformat() if discount.starts_at else None,
        "expires_at": discount.expires_at.isoformat() if discount.expires_at else None,
        "is_active": discount.is_active,
        "created_at": discount.created_at.isoformat() if discount.created_at else None,
    }


def _discount_values(data, existing=None):
    errors = {}
    values = {}
    for field in ("code", "name"):
        if field in data or existing is None:
            value, error = required_string(data, field, max_length=32 if field == "code" else 120)
            if error:
                errors[field] = error
            else:
                value = value.upper() if field == "code" else value
                if field == "code" and not DISCOUNT_CODE_PATTERN.fullmatch(value):
                    errors[field] = "Use 3–32 letters, numbers, underscores, or hyphens"
                else:
                    values[field] = value
    if "discount_type" in data or existing is None:
        discount_type = data.get("discount_type")
        if discount_type not in {"percentage", "fixed"}:
            errors["discount_type"] = "Choose percentage or fixed"
        else:
            values["discount_type"] = discount_type
    if "value" in data or existing is None:
        value, error = parse_money(data.get("value"), "value")
        if error or value <= 0:
            errors["value"] = error or "Value must be greater than zero"
        else:
            values["value"] = value
    if "is_active" in data or existing is None:
        is_active = data.get("is_active", True)
        if not isinstance(is_active, bool):
            errors["is_active"] = "is_active must be a boolean"
        else:
            values["is_active"] = is_active
    date_values = {}
    for field in ("starts_at", "expires_at"):
        if field in data or existing is None:
            raw_value = data.get(field) or None
            if raw_value is not None:
                if not isinstance(raw_value, str):
                    errors[field] = "Use a valid ISO date"
                    continue
                try:
                    parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
                except ValueError:
                    try:
                        parsed = datetime.combine(date.fromisoformat(raw_value), time.min)
                    except ValueError:
                        errors[field] = "Use a valid ISO date or datetime"
                        continue
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=STORE_TIMEZONE)
                date_values[field] = parsed.astimezone(timezone.utc)
            else:
                date_values[field] = None
    starts_at = date_values.get("starts_at", existing.starts_at if existing else None)
    expires_at = date_values.get("expires_at", existing.expires_at if existing else None)
    if starts_at and expires_at and expires_at <= starts_at:
        errors["expires_at"] = "Expiration must be after the start date"
    values.update(date_values)
    if values.get("discount_type", getattr(existing, "discount_type", None)) == "percentage":
        value = values.get("value", getattr(existing, "value", None))
        if value is not None and value > 100:
            errors["value"] = "Percentage discounts cannot exceed 100"
    return values, errors


def serialize_admin_order(order):
    data = serialize_order(order)
    data["customer"] = {
        "id": order.user.id,
        "name": order.user.name,
        "email": order.user.email,
    }
    data["payments"] = [
        {
            "payment_method": payment.payment_method,
            "payment_status": payment.payment_status,
            "amount": float(payment.amount),
            "created_at": payment.created_at.isoformat() if payment.created_at else None,
        }
        for payment in order.payments
    ]
    return data


@admin_bp.get("/users")
@roles_required("admin")
def list_users():
    query = User.query
    role = request.args.get("role")
    if role:
        if role not in {"admin", "customer"}:
            return error_response("Validation failed", {"role": "Invalid user role"}, 422)
        query = query.filter_by(role=role)
    search = request.args.get("search", "").strip()
    if len(search) > 120:
        return error_response("Validation failed", {"search": "Search must be at most 120 characters"}, 422)
    if search:
        query = query.filter(or_(User.name.ilike(f"%{search}%"), User.email.ilike(f"%{search}%")))
    users = query.order_by(User.created_at.desc()).all()
    return success_response({"users": [user.to_dict() for user in users]})


@admin_bp.get("/orders")
@roles_required("admin")
def list_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return success_response({"orders": [serialize_admin_order(order) for order in orders]})


@admin_bp.get("/orders/<int:order_id>")
@roles_required("admin")
def get_order(order_id):
    order = Order.query.get_or_404(order_id)
    return success_response({"order": serialize_admin_order(order)})


@admin_bp.get("/orders/<int:order_id>/history")
@roles_required("admin")
def get_order_history(order_id):
    order = Order.query.get_or_404(order_id)
    history = AuditLog.query.filter_by(action="order.status.updated").filter(
        AuditLog.description.startswith(f"Order {order.id}: ")
    ).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).all()
    return success_response({
        "history": [
            {
                "description": entry.description,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
            }
            for entry in history
        ]
    })


@admin_bp.get("/users/<int:user_id>/orders")
@roles_required("admin")
def list_customer_orders(user_id):
    user = User.query.filter_by(id=user_id, role="customer").first_or_404()
    orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).all()
    return success_response({"orders": [serialize_admin_order(order) for order in orders]})


@admin_bp.get("/search")
@roles_required("admin")
def search_admin_records():
    search = request.args.get("q", "").strip()
    if len(search) > 120:
        return error_response("Validation failed", {"q": "Search must be at most 120 characters"}, 422)
    if len(search) < 2:
        return success_response({"results": []})
    pattern = f"%{search}%"
    products = Product.query.filter(
        Product.is_active.is_(True),
        Product.name.ilike(pattern),
    ).order_by(Product.name.asc()).limit(5).all()
    customers = User.query.filter(
        User.role == "customer",
        or_(User.name.ilike(pattern), User.email.ilike(pattern)),
    ).order_by(User.name.asc()).limit(5).all()
    order_query = Order.query.join(User, User.id == Order.user_id)
    if search.isdecimal():
        order_query = order_query.filter(
            or_(Order.id == int(search), User.name.ilike(pattern), User.email.ilike(pattern))
        )
    else:
        order_query = order_query.filter(
            or_(User.name.ilike(pattern), User.email.ilike(pattern))
        )
    orders = order_query.order_by(Order.created_at.desc()).limit(5).all()
    results = [
        {"kind": "Product", "label": product.name, "detail": f"Product #{product.id}", "href": f"products.html?search={quote(search, safe='')}"}
        for product in products
    ] + [
        {"kind": "Customer", "label": customer.name, "detail": customer.email, "href": f"customers.html?search={quote(search, safe='')}"}
        for customer in customers
    ] + [
        {"kind": "Order", "label": f"Order #{order.id}", "detail": order.user.name, "href": f"orders.html?order={order.id}"}
        for order in orders
    ]
    return success_response({"results": results})


@admin_bp.patch("/orders/<int:order_id>/status")
@roles_required("admin")
def update_order_status(order_id):
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    status = data.get("status")
    if not isinstance(status, str) or status not in ORDER_STATUSES:
        return error_response("Validation failed", {"status": "Invalid order status"}, 422)
    order = Order.query.get_or_404(order_id)
    old_status = order.status
    if status == "cancelled" and old_status != "cancelled":
        try:
            order = cancel_order(order)
        except OrderError as error:
            return error_response(error.message, status=error.status)
    else:
        if old_status == "cancelled" and status != "cancelled":
            return error_response("A cancelled order cannot be reopened", status=409)
        order.status = status
        db.session.commit()
    db.session.add(AuditLog(
        user_id=current_user().id,
        action="order.status.updated",
        description=f"Order {order.id}: {old_status} -> {status}",
    ))
    db.session.commit()
    return success_response({"order": serialize_admin_order(order)}, "Order status updated")


@admin_bp.post("/orders")
@roles_required("admin")
def create_admin_order():
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    customer_id, error = parse_positive_int(data.get("customer_id"), "customer_id")
    if error:
        return error_response("Validation failed", {"customer_id": error}, 422)
    customer = User.query.filter_by(id=customer_id, role="customer").first()
    if customer is None:
        return error_response("Customer not found", status=404)
    shipping_address, error = required_string(data, "shipping_address", max_length=2000)
    if error:
        return error_response("Validation failed", {"shipping_address": error}, 422)
    submitted_items = data.get("items")
    if not isinstance(submitted_items, list) or not submitted_items or len(submitted_items) > 50:
        return error_response(
            "Validation failed",
            {"items": "Provide between 1 and 50 order items"},
            422,
        )
    quantities = {}
    for index, item in enumerate(submitted_items):
        if not isinstance(item, dict):
            return error_response(
                "Validation failed",
                {"items": f"Item {index + 1} must be an object"},
                422,
            )
        product_id, error = parse_positive_int(item.get("product_id"), "product_id")
        if error:
            return error_response("Validation failed", {"items": f"Item {index + 1}: {error}"}, 422)
        quantity, error = parse_positive_int(item.get("quantity"), "quantity")
        if error:
            return error_response("Validation failed", {"items": f"Item {index + 1}: {error}"}, 422)
        quantities[product_id] = quantities.get(product_id, 0) + quantity
    try:
        products = db.session.execute(
            select(Product).where(Product.id.in_(sorted(quantities))).order_by(Product.id).with_for_update()
        ).scalars().all()
        products_by_id = {product.id: product for product in products}
        missing = [product_id for product_id in quantities if product_id not in products_by_id]
        if missing:
            return error_response("One or more products were not found", status=404)
        for product_id, quantity in quantities.items():
            product = products_by_id[product_id]
            if not product.is_active:
                return error_response(f"{product.name} is not available", status=409)
            if quantity > product.stock:
                return error_response(f"Insufficient stock for {product.name}", status=409)
        order = Order(
            user_id=customer.id,
            status="pending",
            total_amount=Decimal("0.00"),
            shipping_address=shipping_address,
        )
        db.session.add(order)
        db.session.flush()
        subtotal = Decimal("0.00")
        for product_id, quantity in quantities.items():
            product = products_by_id[product_id]
            line_total = product.price * quantity
            subtotal += line_total
            db.session.add(OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=product.price,
                subtotal=line_total,
            ))
            adjust_product_stock(product, -quantity)
        shipping_fee = Decimal("50.00") if subtotal < Decimal("500.00") else Decimal("0.00")
        order.total_amount = subtotal + shipping_fee
        order.shipping_address = f"{shipping_address}\nDelivery option: standard"
        db.session.add(Payment(
            order_id=order.id,
            payment_method="cash_on_delivery",
            payment_status="pending",
            amount=order.total_amount,
        ))
        db.session.flush()
        db.session.add(AuditLog(
            user_id=current_user().id,
            action="order.created",
            description=f"Order {order.id} created by admin for customer {customer.id}",
        ))
        record_admin_notification(
            f"admin-created-order-{order.id}",
            "order",
            "Order created",
            f"Order #{order.id} was created for {customer.name}.",
            "order",
            order.id,
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error_response("The order could not be saved", status=409)
    return success_response({"order": serialize_admin_order(order)}, "Order created", 201)


@admin_bp.get("/discounts")
@roles_required("admin")
def list_discounts():
    discounts = Discount.query.order_by(Discount.created_at.desc(), Discount.id.desc()).all()
    return success_response({"discounts": [serialize_discount(discount) for discount in discounts]})


@admin_bp.post("/discounts")
@roles_required("admin")
def create_discount():
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    values, errors = _discount_values(data)
    if errors:
        return error_response("Validation failed", errors, 422)
    discount = Discount(**values)
    db.session.add(discount)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error_response("A discount with this code already exists", status=409)
    return success_response({"discount": serialize_discount(discount)}, "Discount created", 201)


@admin_bp.patch("/discounts/<int:discount_id>")
@roles_required("admin")
def update_discount(discount_id):
    discount = db.session.get(Discount, discount_id)
    if discount is None:
        return error_response("Discount not found", status=404)
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    values, errors = _discount_values(data, discount)
    if errors:
        return error_response("Validation failed", errors, 422)
    for field, value in values.items():
        setattr(discount, field, value)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error_response("A discount with this code already exists", status=409)
    return success_response({"discount": serialize_discount(discount)}, "Discount updated")


@admin_bp.delete("/discounts/<int:discount_id>")
@roles_required("admin")
def delete_discount(discount_id):
    discount = db.session.get(Discount, discount_id)
    if discount is None:
        return error_response("Discount not found", status=404)
    db.session.delete(discount)
    db.session.commit()
    return success_response({}, "Discount deleted")


@admin_bp.get("/dashboard")
@roles_required("admin")
def dashboard():
    store_today = datetime.now(STORE_TIMEZONE).date()
    start_value = request.args.get("start_date")
    end_value = request.args.get("end_date")
    try:
        start_date = date.fromisoformat(start_value) if start_value else store_today
        end_date = date.fromisoformat(end_value) if end_value else store_today
        if (start_value and start_date.isoformat() != start_value) or (
            end_value and end_date.isoformat() != end_value
        ):
            raise ValueError
    except ValueError:
        return error_response(
            "Validation failed",
            {"date": "Dates must use the YYYY-MM-DD format"},
            422,
        )
    if start_date > end_date or (end_date - start_date).days > 365 or end_date == date.max:
        return error_response(
            "Validation failed",
            {"date": "Select a valid date range of no more than 366 days"},
            422,
        )
    range_days = (end_date - start_date).days + 1
    start_at = datetime.combine(start_date, time.min, tzinfo=STORE_TIMEZONE).astimezone(timezone.utc)
    end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=STORE_TIMEZONE).astimezone(timezone.utc)
    previous_start = start_at - timedelta(days=range_days)

    total_sales = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.payment_status == "paid"
    ).scalar()
    active_customer_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    active_customers = db.session.query(
        func.count(func.distinct(Order.user_id))
    ).join(User, User.id == Order.user_id).filter(
        User.role == "customer",
        Order.created_at >= active_customer_cutoff,
        Order.status != "cancelled",
    ).scalar() or 0
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(6).all()
    status_counts = {
        status: Order.query.filter_by(status=status).count()
        for status in ORDER_STATUSES
    }
    active_order = Order.status != "cancelled"
    period_items = db.session.query(
        OrderItem.quantity,
        OrderItem.subtotal,
        Product.name,
        Category.name.label("category_name"),
        Order.created_at,
    ).join(Order, Order.id == OrderItem.order_id).join(
        Product, Product.id == OrderItem.product_id
    ).outerjoin(Category, Category.id == Product.category_id).filter(
        Order.created_at >= start_at,
        Order.created_at < end_at,
        active_order,
    ).all()
    top_products = db.session.query(
        Product.id,
        Product.name,
        Product.image_url,
        func.sum(OrderItem.quantity).label("units_sold"),
        func.sum(OrderItem.subtotal).label("sales"),
    ).join(OrderItem, OrderItem.product_id == Product.id).join(
        Order, Order.id == OrderItem.order_id
    ).filter(
        Order.created_at >= start_at,
        Order.created_at < end_at,
        Order.status != "cancelled",
    ).group_by(
        Product.id, Product.name, Product.image_url
    ).order_by(
        func.sum(OrderItem.quantity).desc(), Product.name.asc()
    ).limit(5).all()
    daily_sales = {}
    eggs_sold = 0
    chicken_sold = 0
    eggs_sales = 0.0
    chicken_sales = 0.0
    for quantity, subtotal, product_name, category_name, created_at in period_items:
        utc_created_at = (
            created_at.replace(tzinfo=timezone.utc)
            if created_at.tzinfo is None
            else created_at.astimezone(timezone.utc)
        )
        local_date = utc_created_at.astimezone(STORE_TIMEZONE).date()
        row = daily_sales.setdefault(
            local_date.isoformat(),
            {"gross_sales": 0.0, "eggs_sales": 0.0, "chicken_sales": 0.0},
        )
        amount = float(subtotal or 0)
        row["gross_sales"] += amount
        classification = f"{category_name or ''} {product_name}".lower()
        if "egg" in classification:
            eggs_sold += quantity
            eggs_sales += amount
            row["eggs_sales"] += amount
        elif "chicken" in classification:
            chicken_sold += quantity
            chicken_sales += amount
            row["chicken_sales"] += amount

    gross_sales = sum(row["gross_sales"] for row in daily_sales.values())
    previous_gross_sales = db.session.query(
        func.coalesce(func.sum(OrderItem.subtotal), 0)
    ).join(Order, Order.id == OrderItem.order_id).filter(
        Order.created_at >= previous_start,
        Order.created_at < start_at,
        active_order,
    ).scalar() or 0
    previous_orders = Order.query.filter(
        Order.created_at >= previous_start,
        Order.created_at < start_at,
        active_order,
    ).count()
    period_orders = Order.query.filter(
        Order.created_at >= start_at,
        Order.created_at < end_at,
        active_order,
    ).count()
    orders_today = Order.query.filter(
        Order.created_at >= datetime.combine(store_today, time.min, tzinfo=STORE_TIMEZONE).astimezone(timezone.utc),
        Order.created_at < datetime.combine(store_today + timedelta(days=1), time.min, tzinfo=STORE_TIMEZONE).astimezone(timezone.utc),
        active_order,
    ).count()
    delivered_today = Order.query.filter(
        Order.status == "delivered",
        Order.updated_at >= datetime.combine(store_today, time.min, tzinfo=STORE_TIMEZONE).astimezone(timezone.utc),
        Order.updated_at < datetime.combine(store_today + timedelta(days=1), time.min, tzinfo=STORE_TIMEZONE).astimezone(timezone.utc),
    ).count()
    low_stock_items = Product.query.filter(
        Product.is_active.is_(True),
        Product.stock <= LOW_STOCK_THRESHOLD,
    ).order_by(Product.stock.asc(), Product.name.asc()).limit(5).all()
    sales_by_day = [
        {
            "date": (start_date + timedelta(days=offset)).isoformat(),
            **daily_sales.get(
                (start_date + timedelta(days=offset)).isoformat(),
                {"gross_sales": 0.0, "eggs_sales": 0.0, "chicken_sales": 0.0},
            ),
        }
        for offset in range(range_days)
    ]
    return success_response({
        "total_users": User.query.count(),
        "total_customers": User.query.filter_by(role="customer").count(),
        "active_customers": active_customers,
        "total_products": Product.query.count(),
        "total_orders": Order.query.count(),
        "pending_orders": Order.query.filter_by(status="pending").count(),
        "total_sales": float(total_sales or 0),
        "low_stock_products": Product.query.filter(
            Product.is_active.is_(True),
            Product.stock <= LOW_STOCK_THRESHOLD,
        ).count(),
        "order_statuses": status_counts,
        "recent_orders": [serialize_admin_order(order) for order in recent_orders],
        "top_products": [
            {
                "id": product_id,
                "name": name,
                "image_url": image_url,
                "units_sold": int(units_sold),
                "sales": float(sales or 0),
            }
            for product_id, name, image_url, units_sold, sales in top_products
        ],
        "store_today": store_today.isoformat(),
        "sales_period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "gross_sales": gross_sales,
            "previous_gross_sales": float(previous_gross_sales),
            "gross_sales_change_percent": (
                (gross_sales - float(previous_gross_sales)) / float(previous_gross_sales) * 100
                if previous_gross_sales else None
            ),
            "previous_orders": previous_orders,
            "orders_change_percent": (
                (period_orders - previous_orders) / previous_orders * 100
                if previous_orders else None
            ),
            "orders": period_orders,
        },
        "orders_today": orders_today,
        "eggs_sold": eggs_sold,
        "chicken_sold": chicken_sold,
        "eggs_sales": eggs_sales,
        "chicken_sales": chicken_sales,
        "sales_by_day": sales_by_day,
        "fulfillment": {
            "to_pack": Order.query.filter(Order.status.in_(("pending", "confirmed", "processing"))).count(),
            "ready_for_dispatch": Order.query.filter_by(status="shipped").count(),
            "delivered_today": delivered_today,
        },
        "low_stock_items": [
            {
                "id": product.id,
                "name": product.name,
                "stock": product.stock,
                "reorder_threshold": LOW_STOCK_THRESHOLD,
                "category": product.category.name if product.category else None,
                "image_url": product.image_url,
            }
            for product in low_stock_items
        ],
    })


@admin_bp.get("/reports")
@roles_required("admin")
def reports():
    today = datetime.now(timezone.utc).date()
    start_value = request.args.get("start_date")
    end_value = request.args.get("end_date")
    try:
        start_date = date.fromisoformat(start_value) if start_value else None
        end_date = date.fromisoformat(end_value) if end_value else None
        if start_value and start_date.isoformat() != start_value:
            raise ValueError
        if end_value and end_date.isoformat() != end_value:
            raise ValueError
    except ValueError:
        return error_response(
            "Validation failed",
            {"date": "Dates must use the YYYY-MM-DD format"},
            422,
        )
    if start_date is None and end_date is None:
        end_date = today
        start_date = today - timedelta(days=29)
    elif start_date is None:
        start_date = end_date - timedelta(days=29)
    elif end_date is None:
        end_date = today
    if start_date > end_date:
        return error_response(
            "Validation failed",
            {"date": "start_date must be on or before end_date"},
            422,
        )
    if end_date == date.max:
        return error_response(
            "Validation failed",
            {"end_date": "end_date is outside the supported range"},
            422,
        )
    if (end_date - start_date).days > 365:
        return error_response(
            "Validation failed",
            {"date": "Date range cannot exceed 366 days"},
            422,
        )

    start_at = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    paid_filter = (
        Payment.payment_status == "paid",
        Payment.created_at >= start_at,
        Payment.created_at < end_at,
    )
    revenue = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter(*paid_filter).scalar()
    paid_orders = db.session.query(
        func.count(func.distinct(Payment.order_id))
    ).filter(*paid_filter).scalar() or 0
    sales_rows = db.session.query(
        func.date(Payment.created_at),
        func.coalesce(func.sum(Payment.amount), 0),
    ).filter(*paid_filter).group_by(
        func.date(Payment.created_at)
    ).order_by(func.date(Payment.created_at)).all()
    daily_sales = {
        row_date.isoformat() if hasattr(row_date, "isoformat") else str(row_date): float(amount or 0)
        for row_date, amount in sales_rows
    }

    order_query = Order.query.filter(
        Order.created_at >= start_at,
        Order.created_at < end_at,
    )
    order_count = order_query.count()
    status_rows = db.session.query(Order.status, func.count(Order.id)).filter(
        Order.created_at >= start_at,
        Order.created_at < end_at,
    ).group_by(Order.status).all()
    status_counts = {status: 0 for status in ORDER_STATUSES}
    status_counts.update({status: count for status, count in status_rows})
    customer_count = db.session.query(
        func.count(func.distinct(Order.user_id))
    ).filter(
        Order.created_at >= start_at,
        Order.created_at < end_at,
    ).scalar() or 0

    best_sellers = db.session.query(
        Product.id,
        Product.name,
        Product.image_url,
        func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
        func.coalesce(func.sum(OrderItem.subtotal), 0).label("sales"),
    ).join(OrderItem, OrderItem.product_id == Product.id).join(
        Order, Order.id == OrderItem.order_id
    ).filter(
        Order.created_at >= start_at,
        Order.created_at < end_at,
        Order.status != "cancelled",
    ).group_by(
        Product.id, Product.name, Product.image_url
    ).order_by(
        func.sum(OrderItem.quantity).desc(), Product.name.asc()
    ).limit(5).all()

    days = (end_date - start_date).days + 1
    return success_response({
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "summary": {
            "revenue": float(revenue or 0),
            "orders": order_count,
            "paid_orders": paid_orders,
            "average_paid_order": float(revenue or 0) / paid_orders if paid_orders else 0,
            "customers": customer_count,
        },
        "sales_by_day": [
            {
                "date": (start_date + timedelta(days=offset)).isoformat(),
                "revenue": daily_sales.get(
                    (start_date + timedelta(days=offset)).isoformat(), 0
                ),
            }
            for offset in range(days)
        ],
        "order_statuses": status_counts,
        "top_products": [
            {
                "id": product_id,
                "name": name,
                "image_url": image_url,
                "units_sold": int(units_sold),
                "sales": float(sales or 0),
            }
            for product_id, name, image_url, units_sold, sales in best_sellers
        ],
    })