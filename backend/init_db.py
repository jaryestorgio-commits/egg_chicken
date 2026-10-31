from app import app
from extensions import db
import models  # noqa: F401


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    print("Database tables created.")