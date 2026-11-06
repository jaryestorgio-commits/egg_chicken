from datetime import datetime, timezone
from sqlalchemy.orm import validates
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(40))
    birthday = db.Column(db.Date)
    email_order_updates = db.Column(db.Boolean, nullable=False, default=True)
    email_promotions = db.Column(db.Boolean, nullable=False, default=False)
    sms_order_updates = db.Column(db.Boolean, nullable=False, default=False)
    sms_promotions = db.Column(db.Boolean, nullable=False, default=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="customer")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    addresses = db.relationship("Address", back_populates="user", cascade="all, delete-orphan")
    orders = db.relationship("Order", back_populates="user")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    @validates("email")
    def normalize_email(self, _key, email):
        return email.strip().lower()

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "birthday": self.birthday.isoformat() if self.birthday else None,
            "email_order_updates": self.email_order_updates,
            "email_promotions": self.email_promotions,
            "sms_order_updates": self.sms_order_updates,
            "sms_promotions": self.sms_promotions,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
