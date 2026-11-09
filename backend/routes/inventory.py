from flask import Blueprint, request
from extensions import db
from models import AuditLog, Inventory, Product
from services.product_service import set_product_stock
from utils.auth import current_user, roles_required
from utils.responses import error_response, success_response
from utils.validators import parse_positive_int, request_data


inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.get("")
@roles_required("admin")
def list_inventory():
    rows = Inventory.query.join(Product).order_by(Product.name).all()
    return success_response({"inventory": [row.to_dict() for row in rows]})


@inventory_bp.get("/<int:product_id>/history")
@roles_required("admin")
def inventory_history(product_id):
    product = Product.query.get_or_404(product_id)
    entries = AuditLog.query.filter_by(action="inventory.stock.adjusted").filter(
        AuditLog.description.startswith(f"Product {product.id}:")
    ).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(50).all()
    return success_response({
        "history": [
            {
                "description": entry.description,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
                "admin_user_id": entry.user_id,
            }
            for entry in entries
        ]
    })


@inventory_bp.patch("/<int:product_id>")
@roles_required("admin")
def update_inventory(product_id):
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    operation = data.get("operation")
    if operation not in {None, "set", "stock_in", "stock_out"}:
        return error_response("Validation failed", {"operation": "Choose set, stock_in, or stock_out"}, 422)
    quantity, error = parse_positive_int(
        data.get("quantity"),
        "quantity",
        allow_zero=operation in {None, "set"},
    )
    if error:
        return error_response("Validation failed", {"quantity": error}, 422)
    product = Product.query.filter_by(id=product_id).with_for_update().first_or_404()
    previous_quantity = product.stock
    if operation == "stock_in":
        quantity += previous_quantity
    elif operation == "stock_out":
        if quantity > previous_quantity:
            return error_response("Stock out quantity exceeds available stock", status=409)
        quantity = previous_quantity - quantity
    row = set_product_stock(product, quantity)
    if quantity != previous_quantity:
        action = {
            "stock_in": "Stock in",
            "stock_out": "Stock out",
            "set": "Set stock",
            None: "Set stock",
        }[operation]
        db.session.add(AuditLog(
            user_id=current_user().id,
            action="inventory.stock.adjusted",
            description=f"Product {product.id}: {action} ({previous_quantity} -> {quantity})",
        ))
    db.session.commit()
    return success_response({"inventory": row.to_dict()}, "Inventory updated")