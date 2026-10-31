from flask import Blueprint, current_app, request
from extensions import db
from models import Payment
from services.payment_service import (
    PaymentGatewayError,
    apply_invoice,
    create_payment,
    is_xendit_payment_method,
    refresh_payment,
    verify_xendit_callback,
)
from utils.auth import current_user, login_required
from utils.responses import error_response, success_response
from utils.validators import parse_positive_int, request_data


payments_bp = Blueprint("payments", __name__)


@payments_bp.post("")
@login_required
def submit_payment():
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    order_id, error = parse_positive_int(data.get("order_id"), "order_id")
    if error:
        return error_response("Validation failed", {"order_id": error}, 422)
    try:
        payment, message, status = create_payment(current_user().id, order_id, data.get("payment_method"))
    except PaymentGatewayError as error:
        db.session.rollback()
        current_app.logger.warning("Payment checkout could not be created: %s", error.message)
        return error_response(error.message, status=error.status)
    if message:
        return error_response(message, status=status)
    return success_response(
        {"payment": payment.to_dict(), "checkout_url": payment.checkout_url},
        "Payment checkout created" if payment.checkout_url else "Payment recorded",
        status,
    )


@payments_bp.get("/<int:payment_id>")
@login_required
def get_payment(payment_id):
    payment = Payment.query.join(Payment.order).filter(
        Payment.id == payment_id, Payment.order.has(user_id=current_user().id)
    ).first_or_404()
    if is_xendit_payment_method(payment.payment_method):
        try:
            payment = refresh_payment(payment)
        except PaymentGatewayError as error:
            current_app.logger.warning("Xendit payment verification failed: %s", error.message)
            return error_response(error.message, status=error.status)
    return success_response({"payment": payment.to_dict()})


@payments_bp.post("/xendit/webhook")
def xendit_webhook():
    if not verify_xendit_callback(request.headers.get("x-callback-token", "")):
        return error_response("Invalid Xendit callback token", status=401)

    payload = request.get_json(silent=True)
    invoice_id = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(invoice_id, str) or not invoice_id:
        return error_response("Invalid Xendit invoice webhook payload", status=400)

    try:
        from services.payment_service import retrieve_invoice

        verified_invoice = retrieve_invoice(invoice_id)
        apply_invoice(verified_invoice)
    except PaymentGatewayError as error:
        db.session.rollback()
        current_app.logger.warning("Xendit webhook could not be verified: %s", error.message)
        return error_response(error.message, status=error.status)
    except Exception:
        db.session.rollback()
        raise
    return success_response({}, "Xendit webhook processed")