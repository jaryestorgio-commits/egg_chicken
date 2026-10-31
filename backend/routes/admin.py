from datetime import date, datetime, time, timedelta, timezone

from flask import Blueprint, request
from sqlalchemy import func, or_
from extensions import db
from models import AuditLog, Order, OrderItem, Payment, Product, User
from services.order_service import OrderError, cancel_order, serialize_order
from utils.auth import current_user, roles_required
from utils.responses import error_response, success_response
from utils.validators import request_data


admin_bp = Blueprint("admin", __name__)
ORDER_STATUSES = {"pending", "confirmed", "processing", "shipped", "delivered", "cancelled"}


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


@admin_bp.get("/dashboard")
@roles_required("admin")
def dashboard():
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
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(8).all()
    status_counts = {
        status: Order.query.filter_by(status=status).count()
        for status in ORDER_STATUSES
    }
    return success_response({
        "total_users": User.query.count(),
        "total_customers": User.query.filter_by(role="customer").count(),
        "active_customers": active_customers,
        "total_products": Product.query.count(),
        "total_orders": Order.query.count(),
        "pending_orders": Order.query.filter_by(status="pending").count(),
        "total_sales": float(total_sales or 0),
        "low_stock_products": Product.query.filter(Product.stock <= 10).count(),
        "order_statuses": status_counts,
        "recent_orders": [serialize_admin_order(order) for order in recent_orders],
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