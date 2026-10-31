import os
from pathlib import Path

import pytest
from dotenv import dotenv_values, load_dotenv
from sqlalchemy.engine import make_url

BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")
TEST_ENV = dotenv_values(BACKEND_ROOT / ".env.test")

from app import create_app
from extensions import db


def get_test_database_url():
    database_url = (
        os.getenv("TEST_DATABASE_URL")
        or TEST_ENV.get("DATABASE_URL")
    )
    if database_url:
        url = make_url(database_url)
    else:
        main_database_url = os.getenv("DATABASE_URL")
        if not main_database_url:
            pytest.fail("Set DATABASE_URL in .env or TEST_DATABASE_URL for tests")

        main_url = make_url(main_database_url)
        if main_url.database != "egg_chicken_db":
            pytest.fail("DATABASE_URL must point to egg_chicken_db")
        url = main_url.set(database="egg_chicken_test_db")

    if url.drivername != "postgresql+psycopg":
        pytest.fail("Tests require PostgreSQL with the psycopg driver")
    if url.database != "egg_chicken_test_db":
        pytest.fail("Tests may only use egg_chicken_test_db")

    return url.render_as_string(hide_password=False)


@pytest.fixture()
def app():
    database_url = get_test_database_url()
    test_app = create_app({
        "TESTING": True,
        "SECRET_KEY": TEST_ENV.get("SECRET_KEY") or "test-secret-key-for-pytest-only-32-bytes",
        "JWT_SECRET_KEY": TEST_ENV.get("JWT_SECRET_KEY") or "test-jwt-secret-key-for-pytest-only-32-bytes",
        "SQLALCHEMY_DATABASE_URI": database_url,
        "XENDIT_SECRET_KEY": "",
        "XENDIT_CALLBACK_TOKEN": "",
        "XENDIT_SUCCESS_URL": "",
        "XENDIT_FAILURE_URL": "",
    })
    with test_app.app_context():
        db.drop_all()
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
