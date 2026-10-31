from decimal import Decimal
from extensions import db
from models.cart import Cart


def get_or_create_cart(user_id):
    cart = Cart.query.filter_by(user_id=user_id).first()
    if cart is None:
        cart = Cart(user_id=user_id)
        db.session.add(cart)
        db.session.flush()
    return cart


def serialize_cart(cart):
    items = []
    total = Decimal("0.00")
    for item in cart.items:
        product = item.product
        subtotal = product.price * item.quantity
        total += subtotal
        items.append({
            "id": item.id,
            "product_id": product.id,
            "name": product.name,
            "image_url": product.image_url,
            "unit_price": float(product.price),
            "quantity": item.quantity,
            "stock": product.stock,
            "subtotal": float(subtotal),
        })
    return {
        "id": cart.id,
        "items": items,
        "total": float(total),
        "created_at": cart.created_at.isoformat() if cart.created_at else None,
        "updated_at": cart.updated_at.isoformat() if cart.updated_at else None,
    }