import pytest

from extensions import db
from models import Product, User


def create_customer(client, email="product-customer@example.com"):
    response = client.post("/api/v1/auth/register", json={
        "name": "Product Customer",
        "email": email,
        "password": "Password123!",
    })
    assert response.status_code == 201
    return response.get_json()["data"]["access_token"]


def create_admin(client, app):
    token = create_customer(client, email="product-admin@example.com")
    with app.app_context():
        user = User.query.filter_by(email="product-admin@example.com").one()
        user.role = "admin"
        db.session.commit()
    return token


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def product_payload(**overrides):
    payload = {
        "name": "Free-range eggs",
        "description": "A dozen fresh eggs",
        "price": "12.50",
        "stock_quantity": 20,
        "image_url": "https://example.com/eggs.jpg",
    }
    payload.update(overrides)
    return payload


def test_create_product_returns_compatible_stock_fields(client, app):
    token = create_admin(client, app)

    response = client.post("/api/v1/products", json=product_payload(), headers=auth_headers(token))

    assert response.status_code == 201
    product = response.get_json()["data"]["product"]
    assert product["name"] == "Free-range eggs"
    assert product["price"] == 12.5
    assert product["stock"] == 20
    assert product["stock_quantity"] == 20
    assert product["is_active"] is True
    with app.app_context():
        stored = Product.query.one()
        assert stored.stock == 20
        assert stored.stock_quantity == 20


@pytest.mark.parametrize("payload", [
    {"price": "10.00"},
    {"name": "Missing price", "stock_quantity": 1},
    product_payload(name="   "),
    product_payload(price=None),
    product_payload(price="not-a-price"),
    product_payload(price="-1.00"),
    product_payload(stock_quantity=-1),
    product_payload(stock_quantity="not-an-integer"),
    product_payload(category_id=99999),
])
def test_create_product_rejects_invalid_data(client, app, payload):
    token = create_admin(client, app)

    response = client.post("/api/v1/products", json=payload, headers=auth_headers(token))

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_create_product_requires_json_object(client, app):
    token = create_admin(client, app)

    response = client.post("/api/v1/products", data="not-json", headers=auth_headers(token))

    assert response.status_code == 400


def test_create_product_requires_admin(client, app):
    response = client.post("/api/v1/products", json=product_payload())
    customer_token = create_customer(client)
    customer_response = client.post(
        "/api/v1/products",
        json=product_payload(),
        headers=auth_headers(customer_token),
    )

    assert response.status_code == 401
    assert customer_response.status_code == 403


def test_get_products_returns_active_products_only(client, app):
    with app.app_context():
        db.session.add_all([
            Product(name="Active eggs", price="10.00", stock=4),
            Product(name="Inactive eggs", price="11.00", stock=5, is_active=False),
        ])
        db.session.commit()

    response = client.get("/api/v1/products")

    assert response.status_code == 200
    products = response.get_json()["data"]["products"]
    assert [product["name"] for product in products] == ["Active eggs"]


def test_get_empty_product_list(client):
    response = client.get("/api/v1/products")

    assert response.status_code == 200
    assert response.get_json()["data"]["products"] == []


def test_only_admin_can_list_inactive_products(client, app):
    with app.app_context():
        db.session.add(Product(name="Inactive eggs", price="11.00", stock=5, is_active=False))
        db.session.commit()

    assert client.get("/api/v1/products?is_active=false").status_code == 401
    customer_token = create_customer(client)
    assert client.get(
        "/api/v1/products?is_active=false",
        headers=auth_headers(customer_token),
    ).status_code == 403
    admin_token = create_admin(client, app)
    admin_response = client.get(
        "/api/v1/products?is_active=false",
        headers=auth_headers(admin_token),
    )

    assert admin_response.status_code == 200
    assert admin_response.get_json()["data"]["products"][0]["is_active"] is False


def test_get_product_by_id_and_invalid_ids(client, app):
    with app.app_context():
        product = Product(name="Fresh eggs", price="8.00", stock=2)
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    response = client.get(f"/api/v1/products/{product_id}")
    missing = client.get("/api/v1/products/99999")
    invalid = client.get("/api/v1/products/not-an-id")

    assert response.status_code == 200
    assert response.get_json()["data"]["product"]["id"] == product_id
    assert missing.status_code == 404
    assert invalid.status_code == 404
    assert missing.is_json and invalid.is_json


def test_update_product_with_put(client, app):
    token = create_admin(client, app)
    with app.app_context():
        product = Product(name="Fresh eggs", price="8.00", stock=2)
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    response = client.put(
        f"/api/v1/products/{product_id}",
        json={"name": "Large eggs", "price": "9.50", "stock_quantity": 7},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    product = response.get_json()["data"]["product"]
    assert product["name"] == "Large eggs"
    assert product["price"] == 9.5
    assert product["stock"] == product["stock_quantity"] == 7


@pytest.mark.parametrize("payload", [
    {"price": "-1"},
    {"price": "invalid"},
    {"stock": -1},
    {"stock": "invalid"},
])
def test_update_product_rejects_invalid_values(client, app, payload):
    token = create_admin(client, app)
    with app.app_context():
        product = Product(name="Fresh eggs", price="8.00", stock=2)
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    response = client.put(
        f"/api/v1/products/{product_id}",
        json=payload,
        headers=auth_headers(token),
    )

    assert response.status_code == 400


def test_update_product_not_found_and_requires_admin(client, app):
    admin_token = create_admin(client, app)
    missing = client.put(
        "/api/v1/products/99999",
        json={"name": "Missing"},
        headers=auth_headers(admin_token),
    )
    customer_token = create_customer(client)
    forbidden = client.put(
        "/api/v1/products/1",
        json={"name": "Not allowed"},
        headers=auth_headers(customer_token),
    )
    unauthenticated = client.put("/api/v1/products/1", json={"name": "Not allowed"})

    assert missing.status_code == 404
    assert forbidden.status_code == 403
    assert unauthenticated.status_code == 401


def test_delete_product_deactivates_without_removing_row(client, app):
    token = create_admin(client, app)
    with app.app_context():
        product = Product(name="Fresh eggs", price="8.00", stock=2)
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    response = client.delete(f"/api/v1/products/{product_id}", headers=auth_headers(token))
    missing = client.delete("/api/v1/products/99999", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.get_json()["data"]["product"]["is_active"] is False
    assert missing.status_code == 404
    assert client.get(f"/api/v1/products/{product_id}").status_code == 404
    with app.app_context():
        assert db.session.get(Product, product_id) is not None
        assert db.session.get(Product, product_id).is_active is False


def test_delete_product_requires_admin(client, app):
    customer_token = create_customer(client)
    response = client.delete("/api/v1/products/1", headers=auth_headers(customer_token))
    unauthenticated = client.delete("/api/v1/products/1")

    assert response.status_code == 403
    assert unauthenticated.status_code == 401