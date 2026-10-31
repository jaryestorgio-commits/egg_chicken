from datetime import datetime, timezone
from extensions import db


class Address(db.Model):
    __tablename__ = "addresses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    address_line = db.Column(db.String(300), nullable=False)
    city = db.Column(db.String(120), nullable=False)
    province = db.Column(db.String(120), nullable=False)
    postal_code = db.Column(db.String(20), nullable=False)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="addresses")

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "phone": self.phone,
            "address_line": self.address_line,
            "city": self.city,
            "province": self.province,
            "postal_code": self.postal_code,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }