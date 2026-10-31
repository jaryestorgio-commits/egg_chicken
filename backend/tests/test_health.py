from sqlalchemy import text

from extensions import db


def test_test_app_starts_with_test_database(app):
    assert app.config["TESTING"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"].endswith("/egg_chicken_test_db")


def test_health_endpoint(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "message": "EGG & CHICKEN API is running",
        "data": {},
    }


def test_frontend_homepage_and_assets_are_served(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"Good food begins with a better farm." in response.data

    asset_response = client.get("/js/main.js")

    assert asset_response.status_code == 200
    assert asset_response.mimetype == "application/javascript"


def test_postgresql_test_database_connection(app):
    with app.app_context():
        database_name, version_number = db.session.execute(text(
            "SELECT current_database(), current_setting('server_version_num')"
        )).one()

    assert database_name == "egg_chicken_test_db"
    assert version_number.startswith("17")