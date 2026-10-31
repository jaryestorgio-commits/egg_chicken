from extensions import db
from models import AdminNotification


def record_admin_notification(event_key, kind, title, message, related_type, related_id):
    notification = AdminNotification.query.filter_by(event_key=event_key).first()
    if notification is None:
        notification = AdminNotification(
            event_key=event_key,
            kind=kind,
            title=title,
            message=message,
            related_type=related_type,
            related_id=related_id,
        )
        db.session.add(notification)
    return notification
