from decimal import Decimal
from sqlalchemy import select
from extensions import db
from models.cart import Cart
from models.inventory import Inventory
from models.order import Order
from models.order_item import OrderItem
from models.product import Product
from services.product_service import adjust_product_stock


class OrderError(Exception):
    def __init__(self, message, status=400):
        self.message = message
        self.status = status
        super().__init__(message)


def serialize_order(order):
    item_total = sum((item.subtotal for item in order.items), Decimal("0.00"))
    return {
        "id": order.id,
        "user_id": order.user_id,
        "status": order.status,
        "total_amount": float(order.total_amount),
        "shipping_fee": float(order.total_amount - item_total),
        "shipping_address": order.shipping_address,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "payments": [payment.to_dict() for payment in order.payments],
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product.name if item.product else None,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "subtotal": float(item.subtotal),
            }
            for item in order.items
        ],
    }


def checkout(user_id, shipping_address, delivery_option="pickup", commit=True):
    if delivery_option not in {"standard", "pickup"}:
        raise OrderError("delivery_option must be standard or pickup", 422)
    try:
        cart = db.session.execute(
            select(Cart).where(Cart.user_id == user_id).with_for_update()
        ).scalar_one_or_none()
        if cart is None or not cart.items:
            raise OrderError("Your cart is empty", 400)

        order = Order(
            user_id=user_id,
            status="pending",
            total_amount=Decimal("0.00"),
            shipping_address=shipping_address,
        )
        db.session.add(order)
        total = Decimal("0.00")

        for cart_item in list(cart.items):
            product = db.session.execute(
                select(Product).where(Product.id == cart_item.product_id).with_for_update()
            ).scalar_one_or_none()
            if product is None or not product.is_active:
                raise OrderError("A product in your cart is no longer available", 409)
            if cart_item.quantity > product.stock:
                raise OrderError(f"Insufficient stock for {product.name}", 409)
            unit_price = product.price
            subtotal = unit_price * cart_item.quantity
            total += subtotal
            db.session.add(OrderItem(
                order=order,
                product_id=product.id,
                quantity=cart_item.quantity,
                unit_price=unit_price,
                subtotal=subtotal,
            ))
            adjust_product_stock(product, -cart_item.quantity)

        shipping_fee = Decimal("50.00") if delivery_option == "standard" and total < Decimal("500.00") else Decimal("0.00")
        order.total_amount = total + shipping_fee
        order.shipping_address = f"{shipping_address}\nDelivery option: {delivery_option}"
        cart.items.clear()
        db.session.flush()
        if commit:
            db.session.commit()
        return order
    except OrderError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        raise


def cancel_order(order, user_id=None):
    try:
        order = db.session.execute(
            select(Order).where(Order.id == order.id).with_for_update()
        ).scalar_one_or_none()
        if order is None:
            raise OrderError("Order not found", 404)
        if user_id is not None and order.user_id != user_id:
            raise OrderError("Order not found", 404)
        if order.status not in {"pending", "confirmed", "processing"}:
            raise OrderError("This order can no longer be cancelled", 409)
        if any(payment.payment_status == "paid" for payment in order.payments):
            raise OrderError("A paid order cannot be cancelled without a refund", 409)

        legacy_online_payments = [
            payment for payment in order.payments
            if payment.payment_method in {"online_payment", "gcash", "card"}
            and payment.payment_status in {"pending", "failed"}
            and payment.transaction_reference
            and payment.transaction_reference.startswith("cs_")
        ]
        if legacy_online_payments:
            raise OrderError(
                "This order has a pending checkout from the previous payment provider and cannot be safely cancelled here.",
                409,
            )

        online_payments = [
            payment for payment in order.payments
            if payment.payment_method in {"online_payment", "gcash", "card"}
            and payment.payment_status in {"pending", "failed"}
            and payment.transaction_reference
            and not payment.transaction_reference.startswith("cs_")
            and payment.checkout_url
        ]
        if online_payments:
            from services.payment_service import (
                PaymentGatewayError,
                apply_invoice,
                expire_invoice,
            )

            for payment in online_payments:
                try:
                    invoice = expire_invoice(payment.transaction_reference)
                    invoice_status = str(invoice.get("status", "")).upper()
                    if invoice_status == "PAID":
                        apply_invoice(invoice)
                        raise OrderError("This payment has completed and cannot be cancelled without a refund", 409)
                    if invoice_status != "EXPIRED":
                        raise OrderError("Xendit has not confirmed invoice expiry; the order remains active", 409)
                    payment.payment_status = "expired"
                except PaymentGatewayError as error:
                    raise OrderError(error.message, error.status) from error

        for item in order.items:
            product = db.session.execute(
                select(Product).where(Product.id == item.product_id).with_for_update()
            ).scalar_one_or_none()
            if product is not None:
                adjust_product_stock(product, item.quantity)
        order.status = "cancelled"
        db.session.commit()
        return order
    except OrderError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        raise