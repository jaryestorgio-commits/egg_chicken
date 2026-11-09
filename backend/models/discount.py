from datetime import datetime, timezone

from extensions import db


class Discount(db.Model):
    __tablename__ = "discounts"
    __table_args__ = (
        db.CheckConstraint("value > 0", name="ck_discounts_value_positive"),
        db.CheckConstraint(
            "discount_type IN ('percentage', 'fixed')",
            name="ck_discounts_type_valid",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    discount_type = db.Column(db.String(20), nullable=False)
    value = db.Column(db.Numeric(10, 2), nullable=False)
    starts_at = db.Column(db.DateTime(timezone=True))
    expires_at = db.Column(db.DateTime(timezone=True))
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
