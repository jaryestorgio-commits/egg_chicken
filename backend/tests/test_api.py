from werkzeug.security import check_password_hash

from extensions import db
from models import Product, User


def register(client, email="customer@example.com"):
    response = client.post("/api/v1/auth/register", json={
        "name": "Juan Dela Cruz",
        "email": email,
        "password": "password123",
    })
    assert response.status_code == 201
    payload = response.get_json()["data"]
    return payload["user"], payload["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_health_check(client):
    root_response = client.get("/")
    response = client.get("/api/v1/health")

    assert root_response.status_code == 200
    assert root_response.get_json()["message"] == "EGG & CHICKEN API is running"
    assert response.status_code == 200
    assert response.get_json()["message"] == "EGG & CHICKEN API is running"


def test_registration_and_login(client, app):
    user, _token = register(client)
    assert user["email"] == "customer@example.com"
    with app.app_context():
        stored = User.query.filter_by(email="customer@example.com").one()
        assert check_password_hash(stored.password_hash, "password123")
        assert stored.password_hash != "password123"
    response = client.post("/api/v1/auth/login", json={
        "email": "customer@example.com",
        "password": "password123",
    })
    assert response.status_code == 200
    assert response.get_json()["data"]["access_token"]


def test_invalid_login(client):
    response = client.post("/api/v1/auth/login", json={
        "email": "missing@example.com",
        "password": "wrong-password",
    })
    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_product_listing_and_admin_creation(client, app):
    _user, token = register(client)
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    assert response.get_json()["data"]["pagination"]["total"] == 0
    assert client.post("/api/v1/products", json={
        "name": "Free-range eggs",
        "price": "12.50",
        "stock": 10,
    }, headers=auth_headers(token)).status_code == 403
    with app.app_context():
        user = User.query.filter_by(email="customer@example.com").one()
        user.role = "admin"
        db.session.commit()
    login = client.post("/api/v1/auth/login", json={
        "email": "customer@example.com",
        "password": "password123",
    }).get_json()["data"]
    created = client.post("/api/v1/products", json={
        "name": "Free-range eggs",
        "price": "12.50",
        "stock": 10,
    }, headers=auth_headers(login["access_token"]))
    assert created.status_code == 201
    assert created.get_json()["data"]["product"]["stock"] == 10


def test_cart_checkout_and_inventory(client, app):
    _user, token = register(client)
    with app.app_context():
        product = Product(name="Chicken eggs", price="5.25", stock=8)
        db.session.add(product)
        db.session.commit()
        product_id = product.id
    headers = auth_headers(token)
    added = client.post("/api/v1/cart/items", json={
        "product_id": product_id,
        "quantity": 2,
    }, headers=headers)
    assert added.status_code == 201
    order_response = client.post("/api/v1/orders", json={
        "shipping_address": "1 Sample Street, Manila",
        "delivery_option": "standard",
    }, headers=headers)
    assert order_response.status_code == 201
    order = order_response.get_json()["data"]["order"]
    assert order["total_amount"] == 60.5
    assert order["shipping_fee"] == 50
    assert order["items"][0]["unit_price"] == 5.25
    with app.app_context():
        assert db.session.get(Product, product_id).stock == 6
    assert client.get("/api/v1/cart", headers=headers).get_json()["data"]["cart"]["items"] == []


def test_unauthorized_cart_access(client):
    response = client.get("/api/v1/cart")
    assert response.status_code == 401


def test_logout_revokes_token(client):
    _user, token = register(client)
    headers = auth_headers(token)
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401