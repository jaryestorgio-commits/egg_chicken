from decimal import Decimal

from extensions import db
from models import Order, Payment, Product, User
from services.payment_service import apply_invoice


def _register_customer(client, email="support-customer@example.com"):
    response = client.post("/api/v1/auth/register", json={
        "name": "Support Customer",
        "email": email,
        "password": "Password123!",
    })
    assert response.status_code == 201
    return response.get_json()["data"]["access_token"]


def _create_admin(client, app):
    with app.app_context():
        admin = User(name="Store Admin", email="support-admin@example.com", role="admin")
        admin.set_password("Password123!")
        db.session.add(admin)
        db.session.commit()
    response = client.post("/api/v1/auth/login", json={
        "email": "support-admin@example.com",
        "password": "Password123!",
    })
    assert response.status_code == 200
    return response.get_json()["data"]["access_token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_customer_chat_admin_reply_unread_counts_and_notification(client, app):
    customer_token = _register_customer(client)
    admin_token = _create_admin(client, app)
    customer_headers = _headers(customer_token)
    admin_headers = _headers(admin_token)

    denied = client.get("/api/v1/admin/chat/conversations", headers=customer_headers)
    assert denied.status_code == 403

    sent = client.post(
        "/api/v1/chat/messages",
        json={"message": "Can you help with my order?"},
        headers=customer_headers,
    )
    assert sent.status_code == 201

    conversations = client.get("/api/v1/admin/chat/conversations", headers=admin_headers)
    conversation = conversations.get_json()["data"]["conversations"][0]
    assert conversation["latest_message"]["body"] == "Can you help with my order?"
    assert conversation["unread_count"] == 1

    customer_id = conversation["customer_id"]
    history = client.get(
        f"/api/v1/admin/chat/conversations/{customer_id}/messages",
        headers=admin_headers,
    )
    assert history.status_code == 200
    assert client.get("/api/v1/admin/chat/conversations", headers=admin_headers).get_json()["data"]["conversations"][0]["unread_count"] == 0

    reply = client.post(
        f"/api/v1/admin/chat/conversations/{customer_id}/messages",
        json={"message": "We are happy to help."},
        headers=admin_headers,
    )
    assert reply.status_code == 201
    customer_history = client.get("/api/v1/chat/messages", headers=customer_headers)
    messages = customer_history.get_json()["data"]["messages"]
    assert messages[-1]["body"] == "We are happy to help."
    assert messages[-1]["sender_role"] == "admin"
    assert messages[-1]["read_at"]

    notifications = client.get("/api/v1/admin/notifications", headers=admin_headers)
    data = notifications.get_json()["data"]
    assert data["unread_count"] == 1
    assert data["notifications"][0]["kind"] == "message"
    assert data["notifications"][0]["href"] == f"messages.html?customer={customer_id}"


def test_customer_can_only_delete_their_own_chat_messages(client, app):
    customer_token = _register_customer(client, "delete-customer@example.com")
    other_customer_token = _register_customer(client, "other-delete-customer@example.com")
    admin_token = _create_admin(client, app)
    customer_headers = _headers(customer_token)
    other_customer_headers = _headers(other_customer_token)
    admin_headers = _headers(admin_token)

    own_message = client.post(
        "/api/v1/chat/messages",
        json={"message": "Please remove this message."},
        headers=customer_headers,
    ).get_json()["data"]["message"]
    other_message = client.post(
        "/api/v1/chat/messages",
        json={"message": "This belongs to another customer."},
        headers=other_customer_headers,
    ).get_json()["data"]["message"]
    admin_reply = client.post(
        f"/api/v1/admin/chat/conversations/{own_message['customer_id']}/messages",
        json={"message": "This is a support reply."},
        headers=admin_headers,
    ).get_json()["data"]["message"]

    assert client.delete(
        f"/api/v1/chat/messages/{other_message['id']}",
        headers=customer_headers,
    ).status_code == 404
    assert client.delete(
        f"/api/v1/chat/messages/{admin_reply['id']}",
        headers=customer_headers,
    ).status_code == 404
    deleted = client.delete(
        f"/api/v1/chat/messages/{own_message['id']}",
        headers=customer_headers,
    )
    assert deleted.status_code == 200
    remaining = client.get("/api/v1/chat/messages", headers=customer_headers)
    assert all(
        message["id"] != own_message["id"]
        for message in remaining.get_json()["data"]["messages"]
    )


def test_order_low_stock_and_payment_events_create_readable_notifications(client, app):
    customer_token = _register_customer(client, "events-customer@example.com")
    admin_token = _create_admin(client, app)
    with app.app_context():
        product = Product(name="Farm eggs", price=Decimal("10.00"), stock=12)
        initially_low = Product(name="Chicken cuts", price=Decimal("20.00"), stock=4)
        db.session.add_all([product, initially_low])
        db.session.commit()
        product_id = product.id
        initially_low_id = initially_low.id

    customer_headers = _headers(customer_token)
    assert client.post(
        "/api/v1/cart/items",
        json={"product_id": product_id, "quantity": 2},
        headers=customer_headers,
    ).status_code == 201
    order_response = client.post(
        "/api/v1/orders",
        json={"shipping_address": "Manila", "delivery_option": "pickup"},
        headers=customer_headers,
    )
    assert order_response.status_code == 201
    order_id = order_response.get_json()["data"]["order"]["id"]

    with app.app_context():
        order = db.session.get(Order, order_id)
        payment = Payment(
            order_id=order.id,
            payment_method="online_payment",
            payment_status="pending",
            amount=order.total_amount,
            transaction_reference="test-invoice",
        )
        db.session.add(payment)
        db.session.flush()
        payment_id = payment.id
        db.session.commit()
        apply_invoice({
            "id": "test-invoice",
            "external_id": f"EC-ORDER-{order_id}-PAY-{payment_id}",
            "status": "FAILED",
        })

    admin_headers = _headers(admin_token)
    response = client.get("/api/v1/admin/notifications", headers=admin_headers)
    data = response.get_json()["data"]
    kinds = {item["kind"] for item in data["notifications"]}
    assert {"order", "low_stock", "payment"} <= kinds
    assert any(item["href"] == f"orders.html?order={order_id}" for item in data["notifications"])
    assert any(item["href"] == f"inventory.html?product={product_id}" for item in data["notifications"])
    assert any(item["href"] == f"inventory.html?product={initially_low_id}" for item in data["notifications"])

    repeated = client.get("/api/v1/admin/notifications", headers=admin_headers)
    low_stock_events = [
        item for item in repeated.get_json()["data"]["notifications"]
        if item["related_type"] == "product"
    ]
    assert len(low_stock_events) == 2

    marked = client.patch("/api/v1/admin/notifications/read-all", headers=admin_headers)
    assert marked.status_code == 200
    refreshed = client.get("/api/v1/admin/notifications", headers=admin_headers)
    assert refreshed.get_json()["data"]["unread_count"] == 0
    with app.app_context():
        assert db.session.get(Product, product_id).stock == 10
