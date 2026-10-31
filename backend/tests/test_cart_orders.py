from extensions import db
from models import CartItem, Order, Payment, Product


def _register_customer(client, email="cart-customer@example.com"):
    response = client.post("/api/v1/auth/register", json={
        "name": "Cart Customer",
        "email": email,
        "password": "Password123!",
    })
    assert response.status_code == 201
    return response.get_json()["data"]["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_cart_quantity_update_and_remove(client, app):
    token = _register_customer(client)
    with app.app_context():
        product = Product(name="Fresh eggs", price="12.50", stock=4)
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    headers = _auth_headers(token)
    added = client.post(
        "/api/v1/cart/items",
        json={"product_id": product_id, "quantity": 2},
        headers=headers,
    )
    assert added.status_code == 201
    item_id = added.get_json()["data"]["cart"]["items"][0]["id"]

    updated = client.patch(
        f"/api/v1/cart/items/{item_id}",
        json={"quantity": 3},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["cart"]["items"][0]["quantity"] == 3

    rejected = client.patch(
        f"/api/v1/cart/items/{item_id}",
        json={"quantity": 5},
        headers=headers,
    )
    assert rejected.status_code == 409

    removed = client.delete(f"/api/v1/cart/items/{item_id}", headers=headers)
    assert removed.status_code == 200
    assert removed.get_json()["data"]["cart"]["items"] == []


def test_inactive_product_cannot_be_added_to_cart(client, app):
    token = _register_customer(client)
    with app.app_context():
        product = Product(name="Discontinued eggs", price="10.00", stock=5, is_active=False)
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    response = client.post(
        "/api/v1/cart/items",
        json={"product_id": product_id, "quantity": 1},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404
    with app.app_context():
        assert CartItem.query.count() == 0


def test_checkout_rejects_stock_shortage_without_creating_order(client, app):
    token = _register_customer(client)
    with app.app_context():
        product = Product(name="Chicken breast", price="190.00", stock=3)
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    headers = _auth_headers(token)
    assert client.post(
        "/api/v1/cart/items",
        json={"product_id": product_id, "quantity": 3},
        headers=headers,
    ).status_code == 201
    with app.app_context():
        db.session.get(Product, product_id).stock = 2
        db.session.commit()

    response = client.post(
        "/api/v1/orders",
        json={"shipping_address": "Manila", "delivery_option": "pickup"},
        headers=headers,
    )

    assert response.status_code == 409
    with app.app_context():
        assert Order.query.count() == 0
        assert db.session.get(Product, product_id).stock == 2
        assert CartItem.query.one().quantity == 3


def test_checkout_rejects_product_deactivated_after_adding_to_cart(client, app):
    token = _register_customer(client)
    with app.app_context():
        product = Product(name="Chicken thighs", price="155.00", stock=4)
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    headers = _auth_headers(token)
    assert client.post(
        "/api/v1/cart/items",
        json={"product_id": product_id, "quantity": 2},
        headers=headers,
    ).status_code == 201
    with app.app_context():
        db.session.get(Product, product_id).is_active = False
        db.session.commit()

    response = client.post(
        "/api/v1/orders",
        json={"shipping_address": "Manila", "delivery_option": "pickup"},
        headers=headers,
    )

    assert response.status_code == 409
    with app.app_context():
        assert Order.query.count() == 0
        assert db.session.get(Product, product_id).stock == 4
        assert CartItem.query.one().quantity == 2


def test_customer_checkout_creates_cash_on_delivery_order(client, app):
    token = _register_customer(client)
    with app.app_context():
        product = Product(name="Farm eggs", price="120.00", stock=5)
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    headers = _auth_headers(token)
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
            "payment_method": "cash_on_delivery",
        },
        headers=headers,
    )

    assert response.status_code == 201
    result = response.get_json()["data"]
    assert result["order"]["status"] == "pending"
    assert result["payment"]["payment_method"] == "cash_on_delivery"
    assert result["payment"]["payment_status"] == "pending"
    assert not result.get("checkout_url")
    with app.app_context():
        assert db.session.get(Product, product_id).stock == 3
        assert CartItem.query.count() == 0


def test_online_payment_rejects_missing_xendit_configuration(client, app):
    token = _register_customer(client)
    with app.app_context():
        product = Product(name="Chicken wings", price="145.00", stock=3)
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    headers = _auth_headers(token)
    assert client.post(
        "/api/v1/cart/items",
        json={"product_id": product_id, "quantity": 1},
        headers=headers,
    ).status_code == 201
    order_response = client.post(
        "/api/v1/orders",
        json={"shipping_address": "Manila", "delivery_option": "pickup"},
        headers=headers,
    )
    order_id = order_response.get_json()["data"]["order"]["id"]

    payment_response = client.post(
        "/api/v1/payments",
        json={"order_id": order_id, "payment_method": "online_payment"},
        headers=headers,
    )

    assert payment_response.status_code == 503
    assert "XENDIT_SECRET_KEY" in payment_response.get_json()["message"]
    with app.app_context():
        assert Payment.query.count() == 0
