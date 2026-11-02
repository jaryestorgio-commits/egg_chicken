import os
from dotenv import load_dotenv

load_dotenv()

database_url = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres@localhost:5432/egg_chicken_db",
)
if database_url.startswith("postgres://"):
    database_url = "postgresql+psycopg://" + database_url.removeprefix("postgres://")
elif database_url.startswith("postgresql://"):
    database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql://")

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

    XENDIT_SECRET_KEY = os.getenv("XENDIT_SECRET_KEY", "")
    XENDIT_CALLBACK_TOKEN = os.getenv("XENDIT_CALLBACK_TOKEN", "")
    XENDIT_SUCCESS_URL = os.getenv("XENDIT_SUCCESS_URL", "")
    XENDIT_FAILURE_URL = os.getenv("XENDIT_FAILURE_URL", "")

    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_TOKEN_LOCATION = ["headers"]
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000,http://127.0.0.1:8000,https://egg-chicken.onrender.com",
        ).split(",")
        if origin.strip()
    ]
