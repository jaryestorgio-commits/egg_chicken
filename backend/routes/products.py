from flask import Blueprint, request
from flask_jwt_extended import verify_jwt_in_request
from extensions import db
from models import Category, Product
from services.product_service import set_product_stock
from utils.auth import current_user, roles_required
from utils.responses import error_response, success_response
from utils.validators import parse_money, parse_positive_int, request_data, required_string

products_bp = Blueprint("products", __name__)


def _require_admin_for_inactive_products():
    verify_jwt_in_request(optional=True)
    user = current_user()
    if user is None:
        return error_response("Authentication required", status=401)
    if user.role != "admin":
        return error_response("Admin access required", status=403)
    return None


@products_bp.get("")
def get_products():
    query = Product.query
    is_active = request.args.get("is_active")
    if is_active is None:
        query = query.filter(Product.is_active.is_(True))
    elif is_active.lower() in {"true", "false"}:
        if is_active.lower() == "false":
            error_response_result = _require_admin_for_inactive_products()
            if error_response_result:
                return error_response_result
        query = query.filter(Product.is_active.is_(is_active.lower() == "true"))
    else:
        return error_response("Validation failed", {"is_active": "is_active must be true or false"}, 400)

    search = request.args.get("search", "").strip()
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    category_filter = request.args.get("category_id", request.args.get("category"))
    if category_filter is not None:
        category_id, error = parse_positive_int(category_filter, "category_id")
        if error:
            return error_response("Validation failed", {"category_id": error}, 400)
        query = query.filter_by(category_id=category_id)
    for parameter, operator in (("min_price", ">="), ("max_price", "<=")):
        if request.args.get(parameter) is not None:
            amount, error = parse_money(request.args.get(parameter), parameter)
            if error:
                return error_response("Validation failed", {parameter: error}, 400)
            query = query.filter(Product.price >= amount if operator == ">=" else Product.price <= amount)
    page, error = parse_positive_int(request.args.get("page", "1"), "page")
    if error:
        return error_response("Validation failed", {"page": error}, 400)
    limit, error = parse_positive_int(request.args.get("limit", "20"), "limit")
    if error:
        return error_response("Validation failed", {"limit": error}, 400)
    if limit > 100:
        return error_response("Validation failed", {"limit": "limit cannot exceed 100"}, 400)
    pagination = query.order_by(Product.id).paginate(page=page, per_page=limit, error_out=False)
    return success_response({
        "products": [product.to_dict() for product in pagination.items],
        "pagination": {"page": page, "limit": limit, "total": pagination.total, "pages": pagination.pages},
    })

@products_bp.get("/<int:product_id>")
def get_product(product_id):
    product = Product.query.filter_by(id=product_id, is_active=True).first_or_404()
    return success_response({"product": product.to_dict()})

@products_bp.post("")
@roles_required("admin")
def create_product():
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    name, error = required_string(data, "name", max_length=150)
    if error:
        return error_response("Validation failed", {"name": error}, 400)
    price, error = parse_money(data.get("price"), "price")
    if error:
        return error_response("Validation failed", {"price": error}, 400)
    if "stock" in data and "stock_quantity" in data:
        return error_response("Validation failed", {"stock": "Provide stock or stock_quantity, not both"}, 400)
    stock_field = "stock_quantity" if "stock_quantity" in data else "stock"
    stock, error = parse_positive_int(data.get(stock_field, 0), stock_field, allow_zero=True)
    if error:
        return error_response("Validation failed", {stock_field: error}, 400)
    category_id = data.get("category_id")
    if category_id is not None:
        category_id, error = parse_positive_int(category_id, "category_id")
        if error or not db.session.get(Category, category_id):
            return error_response("Validation failed", {"category_id": error or "Category does not exist"}, 400)
    description = data.get("description")
    image_url = data.get("image_url")
    if description is not None and (not isinstance(description, str) or len(description) > 10000):
        return error_response("Validation failed", {"description": "description must be text no longer than 10000 characters"}, 400)
    if image_url is not None and (not isinstance(image_url, str) or len(image_url) > 500):
        return error_response("Validation failed", {"image_url": "image_url must be text no longer than 500 characters"}, 400)
    is_active = data.get("is_active", True)
    if not isinstance(is_active, bool):
        return error_response("Validation failed", {"is_active": "is_active must be a boolean"}, 400)
    product = Product(name=name, description=data.get("description"), price=price, stock=stock,
                      image_url=image_url, category_id=category_id, is_active=is_active)
    db.session.add(product)
    db.session.flush()
    set_product_stock(product, stock)
    db.session.commit()
    return success_response({"product": product.to_dict()}, "Product created", 201)


@products_bp.put("/<int:product_id>")
@products_bp.patch("/<int:product_id>")
@roles_required("admin")
def update_product(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        return error_response("Product not found", status=404)
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    errors = {}
    if "name" in data:
        name, error = required_string(data, "name", max_length=150)
        if error:
            errors["name"] = error
        else:
            product.name = name
    if "price" in data:
        product.price, error = parse_money(data["price"])
        if error:
            errors["price"] = error
    if "stock" in data and "stock_quantity" in data:
        errors["stock"] = "Provide stock or stock_quantity, not both"
    elif "stock" in data or "stock_quantity" in data:
        stock_field = "stock_quantity" if "stock_quantity" in data else "stock"
        stock, error = parse_positive_int(data[stock_field], stock_field, allow_zero=True)
        if error:
            errors[stock_field] = error
        else:
            set_product_stock(product, stock)
    if "category_id" in data:
        category_id = data["category_id"]
        if category_id is not None:
            category_id, error = parse_positive_int(category_id, "category_id")
            if error or not db.session.get(Category, category_id):
                errors["category_id"] = error or "Category does not exist"
            else:
                product.category_id = category_id
        else:
            product.category_id = None
    for field, max_length in (("description", 10000), ("image_url", 500)):
        if field in data:
            value = data[field]
            if value is not None and (not isinstance(value, str) or len(value) > max_length):
                errors[field] = f"{field} must be text no longer than {max_length} characters"
            else:
                setattr(product, field, value)
    if "is_active" in data:
        if not isinstance(data["is_active"], bool):
            errors["is_active"] = "is_active must be a boolean"
        else:
            product.is_active = data["is_active"]
    if errors:
        db.session.rollback()
        return error_response("Validation failed", errors, 400)
    db.session.commit()
    return success_response({"product": product.to_dict()}, "Product updated")


@products_bp.delete("/<int:product_id>")
@roles_required("admin")
def delete_product(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        return error_response("Product not found", status=404)
    product.is_active = False
    db.session.commit()
    return success_response({"product": product.to_dict()}, "Product deactivated")
