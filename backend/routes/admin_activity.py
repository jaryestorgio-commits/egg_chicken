from datetime import datetime, timezone

from flask import Blueprint
from sqlalchemy import func

from extensions import db
from models import AdminNotification, AdminNotificationRead, Product
from services.notification_service import record_admin_notification
from utils.auth import current_user, roles_required
from utils.responses import success_response


admin_activity_bp = Blueprint("admin_activity", __name__)


def serialize_notification(notification, read):
    destinations = {
        "order": f"orders.html?order={notification.related_id}",
        "product": f"inventory.html?product={notification.related_id}",
        "conversation": f"messages.html?customer={notification.related_id}",
    }
    return {
        "id": notification.id,
        "kind": notification.kind,
        "title": notification.title,
        "message": notification.message,
        "related_type": notification.related_type,
        "related_id": notification.related_id,
        "href": destinations[notification.related_type],
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
        "is_read": read,
    }


@admin_activity_bp.get("/notifications")
@roles_required("admin")
def list_notifications():
    low_stock_products = Product.query.filter(
        Product.is_active.is_(True), Product.stock <= 10
    ).all()
    product_ids = [product.id for product in low_stock_products]
    existing_low_stock_ids = set()
    if product_ids:
        existing_low_stock_ids = {
            row[0] for row in db.session.query(AdminNotification.related_id).filter(
                AdminNotification.kind == "low_stock",
                AdminNotification.related_type == "product",
                AdminNotification.related_id.in_(product_ids),
            ).all()
        }
    created_low_stock_notifications = False
    for product in low_stock_products:
        if product.id in existing_low_stock_ids:
            continue
        record_admin_notification(
            f"low-stock-current-{product.id}",
            "low_stock",
            "Low stock",
            f"{product.name} has {product.stock} units remaining.",
            "product",
            product.id,
        )
        created_low_stock_notifications = True
    if created_low_stock_notifications:
        db.session.commit()
    user_id = current_user().id
    rows = db.session.query(AdminNotification, AdminNotificationRead.id).outerjoin(
        AdminNotificationRead,
        (AdminNotificationRead.notification_id == AdminNotification.id)
        & (AdminNotificationRead.user_id == user_id),
    ).order_by(AdminNotification.created_at.desc()).limit(50).all()
    unread_count = db.session.query(func.count(AdminNotification.id)).outerjoin(
        AdminNotificationRead,
        (AdminNotificationRead.notification_id == AdminNotification.id)
        & (AdminNotificationRead.user_id == user_id),
    ).filter(AdminNotificationRead.id.is_(None)).scalar()
    return success_response({
        "notifications": [
            serialize_notification(notification, read_id is not None)
            for notification, read_id in rows
        ],
        "unread_count": unread_count or 0,
    })


@admin_activity_bp.patch("/notifications/read-all")
@roles_required("admin")
def mark_all_notifications_read():
    user_id = current_user().id
    existing_ids = db.session.query(AdminNotificationRead.notification_id).filter_by(user_id=user_id)
    unread = AdminNotification.query.filter(~AdminNotification.id.in_(existing_ids)).all()
    now = datetime.now(timezone.utc)
    db.session.add_all([
        AdminNotificationRead(notification_id=item.id, user_id=user_id, read_at=now)
        for item in unread
    ])
    db.session.commit()
    return success_response({"unread_count": 0}, "Notifications marked as read")


@admin_activity_bp.patch("/notifications/<int:notification_id>/read")
@roles_required("admin")
def mark_notification_read(notification_id):
    notification = AdminNotification.query.get_or_404(notification_id)
    user_id = current_user().id
    read = AdminNotificationRead.query.filter_by(
        notification_id=notification.id, user_id=user_id
    ).first()
    if read is None:
        db.session.add(AdminNotificationRead(notification_id=notification.id, user_id=user_id))
        db.session.commit()
    return success_response({}, "Notification marked as read")
