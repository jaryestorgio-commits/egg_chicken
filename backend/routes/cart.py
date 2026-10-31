from flask import Blueprint, request
from extensions import db
from models import CartItem, Product
from services.cart_service import get_or_create_cart, serialize_cart
from utils.auth import current_user, login_required
from utils.responses import error_response, success_response
from utils.validators import parse_positive_int, request_data

cart_bp = Blueprint("cart", __name__)

@cart_bp.get("")
@login_required
def get_cart():
    cart = get_or_create_cart(current_user().id)
    db.session.commit()
    return success_response({"cart": serialize_cart(cart)})


@cart_bp.post("/items")
@login_required
def add_cart_item():
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    product_id, error = parse_positive_int(data.get("product_id"), "product_id")
    if error:
        return error_response("Validation failed", {"product_id": error}, 422)
    quantity, error = parse_positive_int(data.get("quantity"), "quantity")
    if error:
        return error_response("Validation failed", {"quantity": error}, 422)
    product = db.session.get(Product, product_id)
    if product is None or not product.is_active:
        return error_response("Product not found", status=404)
    cart = get_or_create_cart(current_user().id)
    item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
    new_quantity = quantity + (item.quantity if item else 0)
    if new_quantity > product.stock:
        db.session.rollback()
        return error_response("Requested quantity exceeds available stock", {"available_stock": product.stock}, 409)
    if item:
        item.quantity = new_quantity
    else:
        db.session.add(CartItem(cart_id=cart.id, product_id=product_id, quantity=quantity))
    db.session.commit()
    return success_response({"cart": serialize_cart(cart)}, "Cart updated", 201)


@cart_bp.patch("/items/<int:item_id>")
@login_required
def update_cart_item(item_id):
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    quantity, error = parse_positive_int(data.get("quantity"), "quantity")
    if error:
        return error_response("Validation failed", {"quantity": error}, 422)
    item = CartItem.query.join(CartItem.cart).filter(
        CartItem.id == item_id, CartItem.cart.has(user_id=current_user().id)
    ).first_or_404()
    if not item.product.is_active:
        return error_response("Product is no longer available", status=409)
    if quantity > item.product.stock:
        return error_response("Requested quantity exceeds available stock", {"available_stock": item.product.stock}, 409)
    item.quantity = quantity
    db.session.commit()
    return success_response({"cart": serialize_cart(item.cart)}, "Cart updated")


@cart_bp.delete("/items/<int:item_id>")
@login_required
def delete_cart_item(item_id):
    item = CartItem.query.join(CartItem.cart).filter(
        CartItem.id == item_id, CartItem.cart.has(user_id=current_user().id)
    ).first_or_404()
    cart = item.cart
    db.session.delete(item)
    db.session.commit()
    return success_response({"cart": serialize_cart(cart)}, "Cart item removed")


@cart_bp.delete("")
@login_required
def clear_cart():
    cart = get_or_create_cart(current_user().id)
    cart.items.clear()
    db.session.commit()
    return success_response({"cart": serialize_cart(cart)}, "Cart cleared")
