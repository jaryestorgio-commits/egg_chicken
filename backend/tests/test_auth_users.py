import pytest
from werkzeug.security import check_password_hash

from extensions import db
from models import User


def register(client, email="person@example.com", password="Password123!"):
    return client.post("/api/v1/auth/register", json={
        "name": "Test Person",
        "email": email,
        "password": password,
    })


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_registration_normalizes_email_and_hashes_password(client, app):
    response = register(client, email=" Person@Example.COM ")

    assert response.status_code == 201
    user_data = response.get_json()["data"]["user"]
    assert user_data["email"] == "person@example.com"
    assert user_data["role"] == "customer"
    assert "password_hash" not in user_data
    with app.app_context():
        user = User.query.filter_by(email="person@example.com").one()
        assert user.password_hash != "Password123!"
        assert check_password_hash(user.password_hash, "Password123!")


def test_duplicate_registration_returns_conflict(client):
    assert register(client).status_code == 201

    response = register(client, email="PERSON@example.com")

    assert response.status_code == 409
    assert response.get_json()["success"] is False


@pytest.mark.parametrize("payload", [
    {"email": "person@example.com", "password": "Password123!"},
    {"name": "Test Person", "email": "not-an-email", "password": "Password123!"},
    {"name": "Test Person", "email": "person@example.com", "password": "short"},
])
def test_invalid_registration_returns_bad_request(client, payload):
    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_login_returns_access_token_and_safe_user(client):
    register(client)

    response = client.post("/api/v1/auth/login", json={
        "email": " PERSON@EXAMPLE.COM ",
        "password": "Password123!",
    })

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["access_token"]
    assert data["user"]["email"] == "person@example.com"
    assert "password_hash" not in data["user"]


def test_admin_login_returns_admin_role_and_authorizes_dashboard(client, app):
    register(client)
    with app.app_context():
        user = User.query.filter_by(email="person@example.com").one()
        user.role = "admin"
        db.session.commit()

    response = client.post("/api/v1/auth/login", json={
        "email": "person@example.com",
        "password": "Password123!",
    })

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["user"]["role"] == "admin"
    assert "password_hash" not in data["user"]
    dashboard = client.get("/api/v1/admin/dashboard", headers=auth_headers(data["access_token"]))
    assert dashboard.status_code == 200


def test_login_rejects_invalid_password(client):
    register(client)

    response = client.post("/api/v1/auth/login", json={
        "email": "person@example.com",
        "password": "WrongPassword123!",
    })

    assert response.status_code == 401


def test_login_rejects_nonexistent_email(client):
    response = client.post("/api/v1/auth/login", json={
        "email": "missing@example.com",
        "password": "Password123!",
    })

    assert response.status_code == 401


def test_current_user_accepts_valid_token(client):
    token = register(client).get_json()["data"]["access_token"]

    response = client.get("/api/v1/auth/me", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.get_json()["data"]["user"]["email"] == "person@example.com"
    assert "password_hash" not in response.get_json()["data"]["user"]


def test_current_user_requires_token(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_current_user_rejects_invalid_token(client):
    response = client.get("/api/v1/auth/me", headers=auth_headers("invalid-token"))

    assert response.status_code == 401


def test_profile_retrieval_and_update(client):
    token = register(client).get_json()["data"]["access_token"]
    headers = auth_headers(token)

    retrieved = client.get("/api/v1/users/me", headers=headers)
    updated = client.put("/api/v1/users/me", json={
        "name": "Updated Person",
        "email": "UPDATED@example.com",
        "role": "admin",
    }, headers=headers)

    assert retrieved.status_code == 200
    assert retrieved.get_json()["data"]["user"]["email"] == "person@example.com"
    assert updated.status_code == 200
    updated_user = updated.get_json()["data"]["user"]
    assert updated_user["name"] == "Updated Person"
    assert updated_user["email"] == "updated@example.com"
    assert updated_user["role"] == "customer"
    assert "password_hash" not in updated_user


def test_profile_update_rejects_duplicate_email(client):
    first_token = register(client, email="first@example.com").get_json()["data"]["access_token"]
    register(client, email="second@example.com")

    response = client.put("/api/v1/users/me", json={
        "email": "SECOND@example.com",
    }, headers=auth_headers(first_token))

    assert response.status_code == 409
    assert response.get_json()["success"] is False


def test_profile_supports_phone_and_birthday(client):
    token = register(client).get_json()["data"]["access_token"]
    headers = auth_headers(token)

    updated = client.patch("/api/v1/users/me", json={
        "phone": "+63 912 345 6789",
        "birthday": "1994-06-15",
    }, headers=headers)

    assert updated.status_code == 200
    assert updated.get_json()["data"]["user"]["phone"] == "+63 912 345 6789"
    assert updated.get_json()["data"]["user"]["birthday"] == "1994-06-15"


@pytest.mark.parametrize("payload", [
    {"phone": "not a phone"},
    {"birthday": "not-a-date"},
    {"birthday": "2999-01-01"},
])
def test_profile_rejects_invalid_contact_details(client, payload):
    token = register(client).get_json()["data"]["access_token"]

    response = client.patch("/api/v1/users/me", json=payload, headers=auth_headers(token))

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_notification_preferences_are_private_and_persisted(client):
    first_token = register(client, email="first@example.com").get_json()["data"]["access_token"]
    second_token = register(client, email="second@example.com").get_json()["data"]["access_token"]
    first_headers = auth_headers(first_token)

    defaults = client.get("/api/v1/users/me/preferences", headers=first_headers)
    updated = client.patch("/api/v1/users/me/preferences", json={
        "email_promotions": True,
        "sms_order_updates": True,
    }, headers=first_headers)
    second_preferences = client.get("/api/v1/users/me/preferences", headers=auth_headers(second_token))

    assert defaults.status_code == 200
    assert defaults.get_json()["data"]["preferences"]["email_order_updates"] is True
    assert updated.status_code == 200
    assert updated.get_json()["data"]["preferences"]["email_promotions"] is True
    assert second_preferences.get_json()["data"]["preferences"]["email_promotions"] is False


@pytest.mark.parametrize("payload", [
    {"sms_promotions": "yes"},
    {"card_number": "4111111111111111"},
])
def test_notification_preferences_reject_invalid_or_unsupported_fields(client, payload):
    token = register(client).get_json()["data"]["access_token"]

    response = client.patch("/api/v1/users/me/preferences", json=payload, headers=auth_headers(token))

    assert response.status_code == 422
    assert response.get_json()["success"] is False


def test_notification_preferences_require_authentication(client):
    response = client.get("/api/v1/users/me/preferences")

    assert response.status_code == 401


def test_address_default_is_validated_and_reassigned_after_delete(client):
    token = register(client).get_json()["data"]["access_token"]
    headers = auth_headers(token)
    address_data = {
        "full_name": "Test Person",
        "phone": "+63 912 345 6789",
        "address_line": "12 Farm Road",
        "city": "Manila",
        "province": "Metro Manila",
        "postal_code": "1000",
    }

    invalid = client.post(
        "/api/v1/users/me/addresses",
        json={**address_data, "is_default": "false"},
        headers=headers,
    )
    first = client.post(
        "/api/v1/users/me/addresses",
        json={**address_data, "is_default": True},
        headers=headers,
    )
    second = client.post(
        "/api/v1/users/me/addresses",
        json={**address_data, "address_line": "24 Market Street"},
        headers=headers,
    )
    deleted = client.delete(
        f"/api/v1/users/me/addresses/{first.get_json()['data']['address']['id']}",
        headers=headers,
    )
    remaining = client.get("/api/v1/users/me/addresses", headers=headers)

    assert invalid.status_code == 422
    assert first.status_code == 201
    assert second.status_code == 201
    assert deleted.status_code == 200
    addresses = remaining.get_json()["data"]["addresses"]
    assert len(addresses) == 1
    assert addresses[0]["id"] == second.get_json()["data"]["address"]["id"]
    assert addresses[0]["is_default"] is True


def test_password_change_requires_current_password_and_replaces_hash(client, app):
    token = register(client).get_json()["data"]["access_token"]
    headers = auth_headers(token)

    missing_current = client.put("/api/v1/users/me/password", json={
        "new_password": "NewPassword456!",
    }, headers=headers)
    wrong_current = client.put("/api/v1/users/me/password", json={
        "current_password": "WrongPassword123!",
        "new_password": "NewPassword456!",
    }, headers=headers)
    changed = client.put("/api/v1/users/me/password", json={
        "current_password": "Password123!",
        "new_password": "NewPassword456!",
    }, headers=headers)

    assert missing_current.status_code == 400
    assert wrong_current.status_code == 401
    assert changed.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="person@example.com").one()
        assert check_password_hash(user.password_hash, "NewPassword456!")
        assert not user.check_password("Password123!")

    old_password_login = client.post("/api/v1/auth/login", json={
        "email": "person@example.com",
        "password": "Password123!",
    })
    new_password_login = client.post("/api/v1/auth/login", json={
        "email": "person@example.com",
        "password": "NewPassword456!",
    })
    assert old_password_login.status_code == 401
    assert new_password_login.status_code == 200


def test_admin_route_rejects_customer_and_accepts_admin(client, app):
    token = register(client).get_json()["data"]["access_token"]

    customer_response = client.get("/api/v1/admin/users", headers=auth_headers(token))

    with app.app_context():
        user = User.query.filter_by(email="person@example.com").one()
        user.role = "admin"
        db.session.commit()
    admin_response = client.get("/api/v1/admin/users", headers=auth_headers(token))

    assert customer_response.status_code == 403
    assert customer_response.get_json()["message"] == "Admin access required"
    assert admin_response.status_code == 200