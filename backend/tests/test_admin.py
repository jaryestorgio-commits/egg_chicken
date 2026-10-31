from datetime import datetime, timedelta, timezone

from extensions import db
from models import Order, OrderItem, Payment, Product, User


def create_user(client, app, email, role):
    response = client.post("/api/v1/auth/register", json={
        "name": "Admin Test User" if role == "admin" else "Customer Test User",
        "email": email,
        "password": "Password123!",
    })
    token = response.get_json()["data"]["access_token"]
    with app.app_context():
        user = User.query.filter_by(email=email).one()
        user.role = role
        db.session.commit()
        user_id = user.id
    return token, user_id


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def create_admin_order(app, customer_id):
    with app.app_context():
        product = Product(name="Free-range eggs", price=12.5, stock=8, is_active=True)
        db.session.add(product)
        db.session.flush()
        order = Order(
            user_id=customer_id,
            status="processing",
            total_amount=25,
            shipping_address="12 Farm Road",
        )
        db.session.add(order)
        db.session.flush()
        payment = Payment(
            order_id=order.id,
            payment_method="cash_on_delivery",
            payment_status="pending",
            amount=25,
            transaction_reference="private-transaction-reference",
        )
        db.session.add(payment)
        db.session.commit()
        return product.id, order.id


def test_admin_dashboard_contains_live_customer_order_and_payment_data(client, app):
    admin_token, _ = create_user(client, app, "admin@example.com", "admin")
    _, customer_id = create_user(client, app, "customer@example.com", "customer")
    create_admin_order(app, customer_id)

    response = client.get("/api/v1/admin/dashboard", headers=auth_headers(admin_token))

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["total_customers"] == 1
    assert data["active_customers"] == 1
    assert data["total_users"] == 2
    assert data["total_products"] == 1
    assert data["total_orders"] == 1
    assert data["pending_orders"] == 0
    assert data["total_sales"] == 0
    assert data["low_stock_products"] == 1
    assert data["order_statuses"]["processing"] == 1
    order = data["recent_orders"][0]
    assert order["customer"]["email"] == "customer@example.com"
    assert order["payments"][0]["payment_status"] == "pending"
    assert order["payments"][0]["payment_method"] == "cash_on_delivery"
    assert "transaction_reference" not in order["payments"][0]
    assert "password_hash" not in order["customer"]
    assert "access_token" not in order["customer"]


def test_admin_customer_search_and_order_history_are_safe(client, app):
    admin_token, _ = create_user(client, app, "admin@example.com", "admin")
    _, customer_id = create_user(client, app, "customer@example.com", "customer")
    _, order_id = create_admin_order(app, customer_id)
    headers = auth_headers(admin_token)

    customers = client.get("/api/v1/admin/users?role=customer&search=customer", headers=headers)
    history = client.get(f"/api/v1/admin/users/{customer_id}/orders", headers=headers)

    assert customers.status_code == 200
    user = customers.get_json()["data"]["users"][0]
    assert user["email"] == "customer@example.com"
    assert "password_hash" not in user
    assert "token" not in user
    assert history.status_code == 200
    assert history.get_json()["data"]["orders"][0]["id"] == order_id


def test_customer_cannot_access_or_change_admin_data(client, app):
    _, customer_id = create_user(client, app, "customer@example.com", "customer")
    product_id, _ = create_admin_order(app, customer_id)
    token = client.post("/api/v1/auth/login", json={
        "email": "customer@example.com",
        "password": "Password123!",
    }).get_json()["data"]["access_token"]
    headers = auth_headers(token)

    protected_requests = [
        client.get("/api/v1/admin/dashboard", headers=headers),
        client.get("/api/v1/admin/users", headers=headers),
        client.get("/api/v1/admin/orders", headers=headers),
        client.get(f"/api/v1/admin/users/{customer_id}/orders", headers=headers),
        client.get("/api/v1/inventory", headers=headers),
        client.patch(f"/api/v1/inventory/{product_id}", json={"quantity": 2}, headers=headers),
        client.patch("/api/v1/admin/orders/1/status", json={"status": "shipped"}, headers=headers),
        client.post("/api/v1/products", json={"name": "Unauthorized", "price": 1}, headers=headers),
    ]

    assert all(response.status_code == 403 for response in protected_requests)
    with app.app_context():
        assert Product.query.filter_by(name="Unauthorized").count() == 0


def test_admin_order_status_rejects_non_string_values(client, app):
    admin_token, _ = create_user(client, app, "admin@example.com", "admin")
    _, customer_id = create_user(client, app, "customer@example.com", "customer")
    create_admin_order(app, customer_id)

    response = client.patch(
        "/api/v1/admin/orders/1/status",
        json={"status": []},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 422


def test_admin_inventory_and_order_updates_preserve_payment_workflow(client, app):
    admin_token, _ = create_user(client, app, "admin@example.com", "admin")
    _, customer_id = create_user(client, app, "customer@example.com", "customer")
    product_id, order_id = create_admin_order(app, customer_id)
    headers = auth_headers(admin_token)

    updated_stock = client.patch(
        f"/api/v1/inventory/{product_id}",
        json={"quantity": 4},
        headers=headers,
    )
    invalid_stock = client.patch(
        f"/api/v1/inventory/{product_id}",
        json={"quantity": -1},
        headers=headers,
    )
    updated_status = client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"status": "shipped"},
        headers=headers,
    )
    details = client.get(f"/api/v1/admin/orders/{order_id}", headers=headers)
    history = client.get(f"/api/v1/admin/orders/{order_id}/history", headers=headers)

    assert updated_stock.status_code == 200
    assert updated_stock.get_json()["data"]["inventory"]["quantity"] == 4
    assert invalid_stock.status_code == 422
    assert updated_status.status_code == 200
    assert updated_status.get_json()["data"]["order"]["status"] == "shipped"
    assert details.get_json()["data"]["order"]["payments"][0]["payment_status"] == "pending"
    assert history.status_code == 200
    assert history.get_json()["data"]["history"][0]["description"] == f"Order {order_id}: processing -> shipped"


def test_admin_reports_aggregate_live_paid_sales_and_order_items(client, app):
    admin_token, _ = create_user(client, app, "reports-admin@example.com", "admin")
    _, customer_id = create_user(client, app, "reports-customer@example.com", "customer")
    product_id, order_id = create_admin_order(app, customer_id)

    with app.app_context():
        payment = Payment.query.filter_by(order_id=order_id).one()
        payment.payment_status = "paid"
        db.session.add(OrderItem(
            order_id=order_id,
            product_id=product_id,
            quantity=2,
            unit_price=12.5,
            subtotal=25,
        ))
        db.session.commit()

    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=6)
    response = client.get(
        f"/api/v1/admin/reports?start_date={start_date.isoformat()}&end_date={today.isoformat()}",
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["summary"]["revenue"] == 25
    assert data["summary"]["orders"] == 1
    assert data["summary"]["paid_orders"] == 1
    assert data["summary"]["average_paid_order"] == 25
    assert len(data["sales_by_day"]) == 7
    assert data["top_products"][0]["id"] == product_id
    assert data["top_products"][0]["units_sold"] == 2
    assert data["top_products"][0]["sales"] == 25


def test_admin_reports_validate_dates_and_require_admin_role(client, app):
    admin_token, _ = create_user(client, app, "reports-validation-admin@example.com", "admin")
    customer_token, _ = create_user(client, app, "reports-validation-customer@example.com", "customer")

    invalid = client.get(
        "/api/v1/admin/reports?start_date=not-a-date",
        headers=auth_headers(admin_token),
    )
    reversed_range = client.get(
        "/api/v1/admin/reports?start_date=2026-03-01&end_date=2026-02-01",
        headers=auth_headers(admin_token),
    )
    forbidden = client.get(
        "/api/v1/admin/reports",
        headers=auth_headers(customer_token),
    )

    assert invalid.status_code == 422
    assert reversed_range.status_code == 422
    assert forbidden.status_code == 403
