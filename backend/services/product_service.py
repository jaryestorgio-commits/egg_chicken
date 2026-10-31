from uuid import uuid4

from extensions import db
from models.inventory import Inventory
from services.notification_service import record_admin_notification


def set_product_stock(product, quantity):
    previous_quantity = product.stock
    product.stock = quantity
    inventory = Inventory.query.filter_by(product_id=product.id).with_for_update().first()
    if inventory is None:
        inventory = Inventory(product_id=product.id, quantity=quantity)
        db.session.add(inventory)
    else:
        inventory.quantity = quantity
    if product.id is not None and previous_quantity > 10 and quantity <= 10:
        record_admin_notification(
            f"low-stock-{product.id}-{uuid4().hex}",
            "low_stock",
            "Low stock",
            f"{product.name} has {quantity} units remaining.",
            "product",
            product.id,
        )
    return inventory


def adjust_product_stock(product, delta):
    return set_product_stock(product, product.stock + delta)