from flask import Blueprint, request
from extensions import db
from models import Inventory, Product
from services.product_service import set_product_stock
from utils.auth import roles_required
from utils.responses import error_response, success_response
from utils.validators import parse_positive_int, request_data


inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.get("")
@roles_required("admin")
def list_inventory():
    rows = Inventory.query.join(Product).order_by(Product.name).all()
    return success_response({"inventory": [row.to_dict() for row in rows]})


@inventory_bp.patch("/<int:product_id>")
@roles_required("admin")
def update_inventory(product_id):
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    quantity, error = parse_positive_int(data.get("quantity"), "quantity", allow_zero=True)
    if error:
        return error_response("Validation failed", {"quantity": error}, 422)
    product = Product.query.get_or_404(product_id)
    row = set_product_stock(product, quantity)
    db.session.commit()
    return success_response({"inventory": row.to_dict()}, "Inventory updated")