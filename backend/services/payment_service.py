import base64
import hmac
import json
import logging
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from flask import current_app
from sqlalchemy import select

from extensions import db
from models.order import Order
from models.payment import Payment
from services.order_service import cancel_order
from services.notification_service import record_admin_notification


VALID_PAYMENT_METHODS = {
    "cash_on_delivery": "cash_on_delivery",
    "cash on delivery": "cash_on_delivery",
    "online_payment": "online_payment",
    "online payment": "online_payment",
    "gcash": "gcash",
    "card": "card",
    "credit/debit card": "card",
    "credit_debit_card": "card",
}
XENDIT_PAYMENT_METHODS = {"online_payment", "gcash", "card"}
XENDIT_HOSTED_METHODS = {"gcash": "GCASH", "card": "CARDS"}
XENDIT_INVOICES_API_URL = "https://api.xendit.co/v2/invoices"
logger = logging.getLogger(__name__)


class PaymentGatewayError(Exception):
    def __init__(self, message, status=502):
        self.message = message
        self.status = status
        super().__init__(message)


def normalize_payment_method(payment_method):
    normalized_method = payment_method.strip().lower() if isinstance(payment_method, str) else ""
    return VALID_PAYMENT_METHODS.get(normalized_method)


def is_xendit_payment_method(payment_method):
    return payment_method in XENDIT_PAYMENT_METHODS


def xendit_configuration_error(require_webhook=True):
    secret_key = (current_app.config.get("XENDIT_SECRET_KEY") or "").strip()
    if not secret_key:
        return "Xendit is not configured. Set XENDIT_SECRET_KEY to a test-mode secret key in backend/.env."
    if not secret_key.startswith(("xnd_development-", "xnd_development_")):
        return "Sandbox checkout requires an Xendit test-mode secret key beginning with xnd_development- or xnd_development_."
    if require_webhook:
        missing = [
            setting for setting in (
                "XENDIT_CALLBACK_TOKEN",
                "XENDIT_SUCCESS_URL",
                "XENDIT_FAILURE_URL",
            )
            if not (current_app.config.get(setting) or "").strip()
        ]
        if missing:
            return f"Xendit configuration is incomplete: set {', '.join(missing)} in backend/.env."
    return None


def _checkout_url(setting, order_id):
    configured_url = (current_app.config.get(setting) or "").strip()
    url = configured_url.replace("{order_id}", str(order_id))
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise PaymentGatewayError(f"{setting} must be an absolute HTTP(S) URL.", 503)
    return url


def _provider_request(method, url, payload=None):
    secret_key = (current_app.config.get("XENDIT_SECRET_KEY") or "").strip()
    if not secret_key:
        raise PaymentGatewayError("Xendit is not configured. Set XENDIT_SECRET_KEY in backend/.env.", 503)
    authorization = base64.b64encode(f"{secret_key}:".encode("utf-8")).decode("ascii")
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Basic {authorization}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        logger.warning("Xendit API returned HTTP %s", error.code)
        raise PaymentGatewayError("Xendit could not process the checkout request.") from error
    except (URLError, TimeoutError) as error:
        logger.warning("Xendit API request failed: %s", error)
        raise PaymentGatewayError("Xendit could not be reached. Please try again.") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        logger.error("Xendit returned an invalid JSON response")
        raise PaymentGatewayError("Xendit returned an invalid response.") from error
    if not isinstance(result, dict):
        raise PaymentGatewayError("Xendit returned an invalid response.")
    return result


def create_xendit_invoice(payment, order):
    configuration_error = xendit_configuration_error()
    if configuration_error:
        raise PaymentGatewayError(configuration_error, 503)

    items = []
    item_total = Decimal("0.00")
    for item in order.items:
        if item.quantity <= 0 or item.unit_price < 0:
            raise PaymentGatewayError("The order contains an invalid item.", 409)
        items.append({
            "name": item.product.name if item.product else f"Product {item.product_id}",
            "price": float(item.unit_price),
            "quantity": item.quantity,
        })
        item_total += item.subtotal

    if not items:
        raise PaymentGatewayError("Cannot create an invoice for an empty order.", 409)

    delivery_amount = order.total_amount - item_total
    if delivery_amount < 0:
        raise PaymentGatewayError("The order total does not match its item prices.", 409)
    if delivery_amount:
        items.append({
            "name": "Delivery",
            "price": float(delivery_amount),
            "quantity": 1,
        })

    external_id = f"EC-ORDER-{order.id}-PAY-{payment.id}"
    payload = {
        "external_id": external_id,
        "amount": float(order.total_amount),
        "currency": "PHP",
        "description": f"EGG & CHICKEN order {order.id}",
        "invoice_duration": 86400,
        "success_redirect_url": _checkout_url("XENDIT_SUCCESS_URL", order.id),
        "failure_redirect_url": _checkout_url("XENDIT_FAILURE_URL", order.id),
        "items": items,
    }
    hosted_method = XENDIT_HOSTED_METHODS.get(payment.payment_method)
    if hosted_method:
        payload["payment_methods"] = [hosted_method]
    if order.user and order.user.email:
        payload["payer_email"] = order.user.email

    result = _provider_request("POST", XENDIT_INVOICES_API_URL, payload)
    checkout_url = result.get("invoice_url")
    parsed = urlparse(checkout_url or "")
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".xendit.co"):
        raise PaymentGatewayError("Xendit returned an invalid hosted invoice URL.")
    invoice_id = result.get("id")
    if not isinstance(invoice_id, str) or not invoice_id:
        raise PaymentGatewayError("Xendit returned an invalid invoice ID.")
    try:
        response_amount = Decimal(str(result.get("amount", "0")))
    except (TypeError, ValueError, InvalidOperation) as error:
        raise PaymentGatewayError("Xendit returned an invalid invoice amount.") from error
    response_currency = str(result.get("currency") or "PHP").upper()
    if (
        result.get("external_id") != external_id
        or response_currency != "PHP"
        or response_amount != Decimal(order.total_amount)
        or str(result.get("status", "PENDING")).upper() != "PENDING"
    ):
        raise PaymentGatewayError("Xendit returned invoice details that do not match the order.")
    return invoice_id, checkout_url


def retrieve_invoice(invoice_id):
    configuration_error = xendit_configuration_error(require_webhook=False)
    if configuration_error:
        raise PaymentGatewayError(configuration_error, 503)
    result = _provider_request(
        "GET",
        f"{XENDIT_INVOICES_API_URL}/{invoice_id}",
    )
    if not isinstance(result.get("id"), str) or result["id"] != invoice_id:
        raise PaymentGatewayError("Xendit returned an invalid invoice.")
    return result


def expire_invoice(invoice_id):
    invoice = retrieve_invoice(invoice_id)
    status = str(invoice.get("status", "")).upper()
    if status in {"EXPIRED", "PAID"}:
        return invoice
    if status != "PENDING":
        raise PaymentGatewayError("Xendit has not confirmed that this invoice can be cancelled.", 409)

    expire_url = f"https://api.xendit.co/invoices/{invoice_id}/expire!"
    try:
        _provider_request("POST", expire_url)
    except PaymentGatewayError:
        invoice = retrieve_invoice(invoice_id)
        status = str(invoice.get("status", "")).upper()
        if status not in {"EXPIRED", "PAID"}:
            raise
        return invoice
    return retrieve_invoice(invoice_id)


def verify_xendit_callback(callback_token):
    expected = (current_app.config.get("XENDIT_CALLBACK_TOKEN") or "").strip()
    if not expected or not callback_token:
        return False
    return hmac.compare_digest(expected, callback_token.strip())


def apply_invoice(invoice):
    invoice_id = invoice.get("id")
    if not isinstance(invoice_id, str):
        raise PaymentGatewayError("Xendit returned an invoice without an ID.")

    payment = db.session.execute(
        select(Payment).where(Payment.transaction_reference == invoice_id).with_for_update()
    ).scalar_one_or_none()
    if payment is None:
        raise PaymentGatewayError("No local payment matches this Xendit invoice.", 404)
    order = db.session.execute(
        select(Order).where(Order.id == payment.order_id).with_for_update()
    ).scalar_one_or_none()
    if order is None:
        raise PaymentGatewayError("The order for this Xendit invoice no longer exists.", 404)

    expected_external_id = f"EC-ORDER-{order.id}-PAY-{payment.id}"
    if invoice.get("external_id") != expected_external_id:
        raise PaymentGatewayError("The Xendit invoice reference does not match the order.", 409)

    status = str(invoice.get("status", "")).upper()
    if status == "PAID":
        try:
            received_amount = Decimal(str(invoice.get("amount")))
        except (TypeError, ValueError, InvalidOperation) as error:
            raise PaymentGatewayError("Xendit returned an invalid invoice amount.", 409) from error
        if str(invoice.get("currency") or "").upper() != "PHP" or received_amount != Decimal(order.total_amount):
            raise PaymentGatewayError("The verified Xendit amount does not match the order total.", 409)
        if order.status == "cancelled":
            raise PaymentGatewayError("Xendit reported a payment for a cancelled order.", 409)
        payment_changed = payment.payment_status != "paid"
        payment.payment_status = "paid"
        if order.status == "pending":
            order.status = "confirmed"
        if payment_changed:
            record_admin_notification(
                f"payment-{payment.id}-paid",
                "payment",
                f"Payment received for order #{order.id}",
                f"Online payment for order #{order.id} is confirmed.",
                "order",
                order.id,
            )
        db.session.commit()
        return payment

    if status == "EXPIRED":
        payment_changed = payment.payment_status != "expired"
        payment.payment_status = "expired"
        if payment_changed:
            record_admin_notification(
                f"payment-{payment.id}-expired",
                "payment",
                f"Payment expired for order #{order.id}",
                f"Online payment for order #{order.id} expired.",
                "order",
                order.id,
            )
        if order.status != "cancelled":
            cancel_order(order)
        else:
            db.session.commit()
        return payment

    if status == "FAILED":
        payment_changed = payment.payment_status != "failed"
        payment.payment_status = "failed"
        if payment_changed:
            record_admin_notification(
                f"payment-{payment.id}-failed",
                "payment",
                f"Payment failed for order #{order.id}",
                f"Online payment for order #{order.id} failed.",
                "order",
                order.id,
            )
        db.session.commit()
        return payment

    if status == "PENDING":
        payment.payment_status = "pending"
        db.session.commit()
        return payment

    return payment


def refresh_payment(payment):
    if (
        not is_xendit_payment_method(payment.payment_method)
        or not payment.transaction_reference
        or not payment.checkout_url
    ):
        return payment
    if payment.payment_status in {"paid", "expired"}:
        return payment
    invoice = retrieve_invoice(payment.transaction_reference)
    return apply_invoice(invoice)


def create_payment(user_id, order_id, payment_method, commit=True):
    order = db.session.execute(
        select(Order).where(Order.id == order_id, Order.user_id == user_id).with_for_update()
    ).scalar_one_or_none()
    if order is None:
        return None, "Order not found", 404
    if order.status == "cancelled":
        return None, "Cannot pay for a cancelled order", 409
    normalized_method = normalize_payment_method(payment_method)
    if normalized_method is None:
        return None, "payment_method must be cash_on_delivery, gcash, card, or online_payment", 422

    existing_payment = db.session.execute(
        select(Payment)
        .where(Payment.order_id == order.id)
        .order_by(Payment.id.desc())
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    if existing_payment is not None:
        if existing_payment.payment_method != normalized_method:
            return None, "A different payment method is already associated with this order", 409
        if is_xendit_payment_method(normalized_method) and not existing_payment.checkout_url:
            return None, "The hosted invoice is unavailable for this order", 409
        return existing_payment, None, 200

    if is_xendit_payment_method(normalized_method):
        configuration_error = xendit_configuration_error()
        if configuration_error:
            return None, configuration_error, 503

    payment = Payment(
        order_id=order.id,
        payment_method=normalized_method,
        payment_status="pending",
        amount=order.total_amount,
    )
    db.session.add(payment)
    db.session.flush()

    if is_xendit_payment_method(normalized_method):
        invoice_id, checkout_url = create_xendit_invoice(payment, order)
        payment.transaction_reference = invoice_id
        payment.checkout_url = checkout_url
    else:
        payment.transaction_reference = f"EC-{uuid4().hex[:20].upper()}"

    if commit:
        db.session.commit()
    return payment, None, 201