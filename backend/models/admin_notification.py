from datetime import datetime, timezone

from extensions import db


class AdminNotification(db.Model):
    __tablename__ = "admin_notifications"

    id = db.Column(db.Integer, primary_key=True)
    event_key = db.Column(db.String(160), nullable=False, unique=True)
    kind = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    related_type = db.Column(db.String(30), nullable=False)
    related_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class AdminNotificationRead(db.Model):
    __tablename__ = "admin_notification_reads"
    __table_args__ = (
        db.UniqueConstraint("notification_id", "user_id", name="uq_admin_notification_read_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(
        db.Integer,
        db.ForeignKey("admin_notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    read_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
