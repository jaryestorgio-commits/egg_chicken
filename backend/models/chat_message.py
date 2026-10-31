from datetime import datetime, timezone

from extensions import db


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    __table_args__ = (
        db.Index("ix_chat_messages_customer_created", "customer_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="SET NULL"), index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    read_at = db.Column(db.DateTime(timezone=True))

    customer = db.relationship("User", foreign_keys=[customer_id])
    sender = db.relationship("User", foreign_keys=[sender_id])
    order = db.relationship("Order")
