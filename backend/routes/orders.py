from flask import Blueprint, current_app, request
from extensions import db
from models import Order
from services.order_service import OrderError, cancel_order, checkout, serialize_order
from services.payment_service import (
    PaymentGatewayError,
    create_payment,
    normalize_payment_method,
    is_xendit_payment_method,
    xendit_configuration_error,
)
from services.notification_service import record_admin_notification
from utils.auth import current_user, login_required
from utils.responses import error_response, success_response
from utils.validators import request_data, required_string

orders_bp = Blueprint("orders", __name__)

@orders_bp.get("")
@login_required
def get_orders():
    orders = Order.query.filter_by(user_id=current_user().id).order_by(Order.created_at.desc()).all()
    return success_response({"orders": [serialize_order(order) for order in orders]})


@orders_bp.post("")
@login_required
def create_order():
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    shipping_address, error = required_string(data, "shipping_address", max_length=2000)
    if error:
        return error_response("Validation failed", {"shipping_address": error}, 422)
    delivery_option = data.get("delivery_option", "pickup")
    if delivery_option not in {"standard", "pickup"}:
        return error_response("Validation failed", {"delivery_option": "delivery_option must be standard or pickup"}, 422)
    payment_method = None
    if "payment_method" in data:
        payment_method = normalize_payment_method(data["payment_method"])
        if payment_method is None:
            return error_response(
                "Validation failed",
                {"payment_method": "payment_method must be cash_on_delivery, gcash, card, or online_payment"},
                422,
            )
        if is_xendit_payment_method(payment_method):
            configuration_error = xendit_configuration_error()
            if configuration_error:
                return error_response(configuration_error, status=503)
    try:
        user_id = current_user().id
        order = checkout(
            user_id,
            shipping_address,
            delivery_option,
            commit=False,
        )
        payment = None
        if payment_method is not None:
            payment, message, status = create_payment(
                user_id,
                order.id,
                payment_method,
                commit=False,
            )
            if message:
                db.session.rollback()
                return error_response(message, status=status)
        record_admin_notification(
            f"new-order-{order.id}",
            "order",
            f"New order #{order.id}",
            f"A new order was placed by {current_user().name}.",
            "order",
            order.id,
        )
        db.session.commit()
    except OrderError as error:
        return error_response(error.message, status=error.status)
    except PaymentGatewayError as error:
        db.session.rollback()
        current_app.logger.warning("Order checkout could not create Xendit invoice: %s", error.message)
        return error_response(error.message, status=error.status)
    except Exception:
        db.session.rollback()
        raise
    result = {"order": serialize_order(order)}
    if payment is not None:
        result["payment"] = payment.to_dict()
        if payment.checkout_url:
            result["checkout_url"] = payment.checkout_url
    return success_response(result, "Order created", 201)


@orders_bp.get("/<int:order_id>")
@login_required
def get_order(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user().id).first_or_404()
    return success_response({"order": serialize_order(order)})


@orders_bp.patch("/<int:order_id>/cancel")
@login_required
def cancel_user_order(order_id):
    order = Order.query.get_or_404(order_id)
    try:
        order = cancel_order(order, current_user().id)
    except OrderError as error:
        return error_response(error.message, status=error.status)
    return success_response({"order": serialize_order(order)}, "Order cancelled")
