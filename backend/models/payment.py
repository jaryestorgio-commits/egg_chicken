from datetime import datetime, timezone
from extensions import db


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_method = db.Column(db.String(40), nullable=False)
    payment_status = db.Column(db.String(30), nullable=False, default="pending")
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    transaction_reference = db.Column(db.String(120), unique=True)
    checkout_url = db.Column(db.String(512))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    order = db.relationship("Order", back_populates="payments")

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "payment_method": self.payment_method,
            "payment_status": self.payment_status,
            "amount": float(self.amount),
            "transaction_reference": self.transaction_reference,
            "checkout_url": self.checkout_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }