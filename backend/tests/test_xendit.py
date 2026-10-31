import pytest

from extensions import db
from models import CartItem, Order, Payment, Product
from services import payment_service


CALLBACK_TOKEN = "test-xendit-callback-token"


def _register_customer(client):
    response = client.post("/api/v1/auth/register", json={
        "name": "Xendit Test Customer",
        "email": "xendit-customer@example.com",
        "password": "Password123!",
    })
    assert response.status_code == 201
    return response.get_json()["data"]["access_token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _enable_xendit(app):
    app.config.update({
        "XENDIT_SECRET_KEY": "xnd_development_example",
        "XENDIT_CALLBACK_TOKEN": CALLBACK_TOKEN,
        "XENDIT_SUCCESS_URL": "http://localhost:5500/pages/order-details.html?id={order_id}&payment=success",
        "XENDIT_FAILURE_URL": "http://localhost:5500/pages/order-details.html?id={order_id}&payment=failed",
    })


def _create_online_order(client, app, monkeypatch, payment_method="online_payment"):
    token = _register_customer(client)
    _enable_xendit(app)
    with app.app_context():
        product = Product(name="Test farm eggs", price="12.50", stock=5)
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    headers = _headers(token)
    assert client.post(
        "/api/v1/cart/items",
        json={"product_id": product_id, "quantity": 2},
        headers=headers,
    ).status_code == 201

    def create_invoice(method, url, payload):
        assert method == "POST"
        assert url == payment_service.XENDIT_INVOICES_API_URL
        assert payload["amount"] == 25.0
        assert payload["currency"] == "PHP"
        assert payload["items"] == [{
            "name": "Test farm eggs",
            "price": 12.5,
            "quantity": 2,
        }]
        assert payload["invoice_duration"] == 86400
        assert payload["payer_email"] == "xendit-customer@example.com"
        expected_methods = {"gcash": ["GCASH"], "card": ["CARDS"]}
        if payment_method in expected_methods:
            assert payload["payment_methods"] == expected_methods[payment_method]
        else:
            assert "payment_methods" not in payload
        external_id = payload["external_id"]
        assert external_id.startswith("EC-ORDER-")
        assert payload["success_redirect_url"].endswith("payment=success")
        assert payload["failure_redirect_url"].endswith("payment=failed")
        return {
            "id": "inv_test_123",
            "external_id": external_id,
            "amount": 25.0,
            "currency": "PHP",
            "status": "PENDING",
            "invoice_url": "https://checkout.xendit.co/web/test-invoice",
        }

    monkeypatch.setattr(payment_service, "_provider_request", create_invoice)
    response = client.post(
        "/api/v1/orders",
        json={
            "shipping_address": "Manila",
            "delivery_option": "pickup",
            "payment_method": payment_method,
        },
        headers=headers,
    )
    assert response.status_code == 201
    result = response.get_json()["data"]
    return headers, product_id, result["order"]["id"], result["payment"]["id"]


@pytest.mark.parametrize("payment_method", ["gcash", "card"])
def test_selected_xendit_method_is_saved_and_limited_in_hosted_checkout(
    client, app, monkeypatch, payment_method
):
    _, _, order_id, payment_id = _create_online_order(
        client, app, monkeypatch, payment_method=payment_method
    )

    with app.app_context():
        payment = db.session.get(Payment, payment_id)
        assert payment.order_id == order_id
        assert payment.payment_method == payment_method
        assert payment.payment_status == "pending"
        assert payment.checkout_url == "https://checkout.xendit.co/web/test-invoice"


def _provider_invoice(order_id, payment_id, *, status="PAID", amount=25.0, currency="PHP"):
    return {
        "id": "inv_test_123",
        "external_id": f"EC-ORDER-{order_id}-PAY-{payment_id}",
        "status": status,
        "amount": amount,
        "currency": currency,
    }


def _webhook_payload(order_id, payment_id, *, status="PAID", amount=25.0):
    return {
        "id": "inv_test_123",
        "external_id": f"EC-ORDER-{order_id}-PAY-{payment_id}",
        "status": status,
        "amount": amount,
        "currency": "PHP",
    }


def test_online_checkout_creates_one_pending_invoice_and_uses_server_stock(client, app, monkeypatch):
    headers, product_id, order_id, payment_id = _create_online_order(client, app, monkeypatch)
    duplicate = client.post(
        "/api/v1/orders",
        json={
            "shipping_address": "Manila",
            "delivery_option": "pickup",
            "payment_method": "online_payment",
        },
        headers=headers,
    )
    repeated_payment = client.post(
        "/api/v1/payments",
        json={"order_id": order_id, "payment_method": "online_payment"},
        headers=headers,
    )

    assert duplicate.status_code == 400
    assert repeated_payment.status_code == 200
    assert repeated_payment.get_json()["data"]["payment"]["transaction_reference"] == "inv_test_123"
    with app.app_context():
        order = db.session.get(Order, order_id)
        payment = db.session.get(Payment, payment_id)
        product = db.session.get(Product, product_id)
        assert order.status == "pending"
        assert payment.payment_status == "pending"
        assert payment.transaction_reference == "inv_test_123"
        assert payment.checkout_url == "https://checkout.xendit.co/web/test-invoice"
        assert product.stock == 3
        assert Order.query.count() == 1
        assert Payment.query.count() == 1


def test_callback_token_and_server_verification_confirm_paid_invoice_once(client, app, monkeypatch):
    auth_headers, product_id, order_id, payment_id = _create_online_order(client, app, monkeypatch)
    monkeypatch.setattr(
        payment_service,
        "retrieve_invoice",
        lambda _invoice_id: _provider_invoice(order_id, payment_id),
    )
    webhook_payload = _webhook_payload(order_id, payment_id)
    webhook_headers = {"x-callback-token": CALLBACK_TOKEN}
    first = client.post("/api/v1/payments/xendit/webhook", json=webhook_payload, headers=webhook_headers)
    replay = client.post("/api/v1/payments/xendit/webhook", json=webhook_payload, headers=webhook_headers)

    assert first.status_code == 200
    assert replay.status_code == 200
    cancellation = client.patch(f"/api/v1/orders/{order_id}/cancel", headers=auth_headers)
    assert cancellation.status_code == 409
    with app.app_context():
        assert db.session.get(Order, order_id).status == "confirmed"
        assert db.session.get(Payment, payment_id).payment_status == "paid"
        assert db.session.get(Product, product_id).stock == 3


def test_verified_failed_invoice_updates_payment_status(client, app, monkeypatch):
    _, _, order_id, payment_id = _create_online_order(
        client, app, monkeypatch, payment_method="gcash"
    )
    monkeypatch.setattr(
        payment_service,
        "retrieve_invoice",
        lambda _invoice_id: _provider_invoice(
            order_id, payment_id, status="FAILED"
        ),
    )

    response = client.post(
        "/api/v1/payments/xendit/webhook",
        json=_webhook_payload(order_id, payment_id, status="FAILED"),
        headers={"x-callback-token": CALLBACK_TOKEN},
    )

    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Order, order_id).status == "pending"
        assert db.session.get(Payment, payment_id).payment_status == "failed"


def test_invalid_callback_token_cannot_confirm_payment(client, app, monkeypatch):
    _, product_id, order_id, payment_id = _create_online_order(client, app, monkeypatch)

    response = client.post(
        "/api/v1/payments/xendit/webhook",
        json=_webhook_payload(order_id, payment_id),
        headers={"x-callback-token": "invalid"},
    )

    assert response.status_code == 401
    with app.app_context():
        assert db.session.get(Order, order_id).status == "pending"
        assert db.session.get(Payment, payment_id).payment_status == "pending"
        assert db.session.get(Product, product_id).stock == 3


def test_webhook_amount_mismatch_does_not_confirm_payment(client, app, monkeypatch):
    _, product_id, order_id, payment_id = _create_online_order(client, app, monkeypatch)
    monkeypatch.setattr(
        payment_service,
        "retrieve_invoice",
        lambda _invoice_id: _provider_invoice(order_id, payment_id, amount=24.0),
    )

    response = client.post(
        "/api/v1/payments/xendit/webhook",
        json=_webhook_payload(order_id, payment_id),
        headers={"x-callback-token": CALLBACK_TOKEN},
    )

    assert response.status_code == 409
    with app.app_context():
        assert db.session.get(Order, order_id).status == "pending"
        assert db.session.get(Payment, payment_id).payment_status == "pending"
        assert db.session.get(Product, product_id).stock == 3


def test_online_checkout_without_credentials_keeps_cart_and_stock(client, app):
    token = _register_customer(client)
    with app.app_context():
        product = Product(name="No credential eggs", price="8.00", stock=4)
        db.session.add(product)
        db.session.commit()
        product_id = product.id
    headers = _headers(token)
    assert client.post(
        "/api/v1/cart/items",
        json={"product_id": product_id, "quantity": 2},
        headers=headers,
    ).status_code == 201

    response = client.post(
        "/api/v1/orders",
        json={
            "shipping_address": "Manila",
            "delivery_option": "pickup",
            "payment_method": "online_payment",
        },
        headers=headers,
    )

    assert response.status_code == 503
    assert "XENDIT_SECRET_KEY" in response.get_json()["message"]
    with app.app_context():
        assert Order.query.count() == 0
        assert Payment.query.count() == 0
        assert db.session.get(Product, product_id).stock == 4


def test_xendit_gateway_error_rolls_back_order_payment_and_stock(client, app, monkeypatch):
    token = _register_customer(client)
    _enable_xendit(app)
    with app.app_context():
        product = Product(name="Gateway error eggs", price="8.00", stock=4)
        db.session.add(product)
        db.session.commit()
        product_id = product.id
    headers = _headers(token)
    assert client.post(
        "/api/v1/cart/items",
        json={"product_id": product_id, "quantity": 2},
        headers=headers,
    ).status_code == 201

    def fail_to_create_session(_method, _url, _payload):
        raise payment_service.PaymentGatewayError("Xendit unavailable", 502)

    monkeypatch.setattr(payment_service, "_provider_request", fail_to_create_session)
    response = client.post(
        "/api/v1/orders",
        json={
            "shipping_address": "Manila",
            "delivery_option": "pickup",
            "payment_method": "online_payment",
        },
        headers=headers,
    )

    assert response.status_code == 502
    with app.app_context():
        assert Order.query.count() == 0
        assert Payment.query.count() == 0
        assert db.session.get(Product, product_id).stock == 4
        assert CartItem.query.one().quantity == 2


def test_failed_attempt_stays_pending_and_verified_invoice_expiry_restores_stock(client, app, monkeypatch):
    headers, product_id, order_id, payment_id = _create_online_order(client, app, monkeypatch)
    monkeypatch.setattr(
        payment_service,
        "retrieve_invoice",
        lambda _invoice_id: _provider_invoice(
            order_id,
            payment_id,
            status="PENDING",
        ),
    )
    failed = client.get(f"/api/v1/payments/{payment_id}", headers=headers)
    assert failed.status_code == 200
    assert failed.get_json()["data"]["payment"]["payment_status"] == "pending"
    with app.app_context():
        assert db.session.get(Order, order_id).status == "pending"
        assert db.session.get(Product, product_id).stock == 3

    monkeypatch.setattr(
        payment_service,
        "retrieve_invoice",
        lambda _invoice_id: _provider_invoice(
            order_id,
            payment_id,
            status="EXPIRED",
        ),
    )
    expired = client.get(f"/api/v1/payments/{payment_id}", headers=headers)

    assert expired.status_code == 200
    assert expired.get_json()["data"]["payment"]["payment_status"] == "expired"
    with app.app_context():
        assert db.session.get(Order, order_id).status == "cancelled"
        assert db.session.get(Product, product_id).stock == 5


def test_customer_cancellation_expires_xendit_invoice_before_releasing_stock(client, app, monkeypatch):
    headers, product_id, order_id, payment_id = _create_online_order(client, app, monkeypatch)
    monkeypatch.setattr(
        payment_service,
        "expire_invoice",
        lambda _invoice_id: _provider_invoice(
            order_id,
            payment_id,
            status="EXPIRED",
        ),
    )

    response = client.patch(f"/api/v1/orders/{order_id}/cancel", headers=headers)

    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Order, order_id).status == "cancelled"
        assert db.session.get(Payment, payment_id).payment_status == "expired"
        assert db.session.get(Product, product_id).stock == 5


def test_xendit_invoice_expiry_uses_provider_endpoint_and_rechecks_status(app, monkeypatch):
    _enable_xendit(app)
    responses = iter([
        {"id": "inv_test_123", "status": "PENDING"},
        {},
        {"id": "inv_test_123", "status": "EXPIRED"},
    ])
    requests = []

    def provider_request(method, url, payload=None):
        requests.append((method, url, payload))
        return next(responses)

    monkeypatch.setattr(payment_service, "_provider_request", provider_request)
    with app.app_context():
        invoice = payment_service.expire_invoice("inv_test_123")

    assert invoice["status"] == "EXPIRED"
    assert requests == [
        ("GET", "https://api.xendit.co/v2/invoices/inv_test_123", None),
        ("POST", "https://api.xendit.co/invoices/inv_test_123/expire!", None),
        ("GET", "https://api.xendit.co/v2/invoices/inv_test_123", None),
    ]
