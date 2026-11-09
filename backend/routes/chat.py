from datetime import datetime, timezone

from flask import Blueprint, request
from sqlalchemy import func

from extensions import db
from models import ChatMessage, Order, User
from services.notification_service import record_admin_notification
from sqlalchemy.orm import joinedload

from utils.auth import current_user, roles_required
from utils.responses import error_response, success_response
from utils.validators import parse_positive_int, request_data, required_string


chat_bp = Blueprint("chat", __name__)
admin_chat_bp = Blueprint("admin_chat", __name__)


def serialize_message(message):
    return {
        "id": message.id,
        "customer_id": message.customer_id,
        "sender_id": message.sender_id,
        "sender_name": message.sender.name,
        "sender_role": message.sender.role,
        "order_id": message.order_id,
        "body": message.body,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "read_at": message.read_at.isoformat() if message.read_at else None,
    }


def _message_body(data):
    return required_string(data, "message", max_length=4000)


@chat_bp.get("/messages")
@roles_required("customer")
def get_customer_messages():
    customer = current_user()
    messages = ChatMessage.query.options(joinedload(ChatMessage.sender)).filter_by(customer_id=customer.id).order_by(
        ChatMessage.created_at.desc(), ChatMessage.id.desc()
    ).limit(200).all()
    now = datetime.now(timezone.utc)
    changed = False
    for message in messages:
        if message.sender.role == "admin" and message.read_at is None:
            message.read_at = now
            changed = True
    if changed:
        db.session.commit()
    messages.reverse()
    return success_response({"messages": [serialize_message(message) for message in messages]})


@chat_bp.delete("/messages/<int:message_id>")
@roles_required("customer")
def delete_customer_message(message_id):
    customer = current_user()
    message = ChatMessage.query.filter_by(
        id=message_id,
        customer_id=customer.id,
        sender_id=customer.id,
    ).first_or_404()
    db.session.delete(message)
    db.session.commit()
    return success_response({}, "Message deleted")


@chat_bp.post("/messages")
@roles_required("customer")
def send_customer_message():
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    body, error = _message_body(data)
    if error:
        return error_response("Validation failed", {"message": error}, 422)
    customer = current_user()
    order_id = None
    if data.get("order_id") not in (None, ""):
        order_id, error = parse_positive_int(data.get("order_id"), "order_id")
        if error:
            return error_response("Validation failed", {"order_id": error}, 422)
        if Order.query.filter_by(id=order_id, user_id=customer.id).first() is None:
            return error_response("Order not found", status=404)
    message = ChatMessage(customer_id=customer.id, sender_id=customer.id, order_id=order_id, body=body)
    db.session.add(message)
    db.session.flush()
    order_suffix = f" about order #{order_id}" if order_id else ""
    record_admin_notification(
        f"chat-message-{message.id}",
        "message",
        f"New message from {customer.name}",
        f"{customer.name} sent a message{order_suffix}.",
        "conversation",
        customer.id,
    )
    db.session.commit()
    return success_response({"message": serialize_message(message)}, "Message sent", 201)


@admin_chat_bp.get("/chat/conversations")
@roles_required("admin")
def list_admin_conversations():
    latest = db.session.query(
        ChatMessage.customer_id.label("customer_id"),
        func.max(ChatMessage.id).label("latest_message_id"),
    ).group_by(ChatMessage.customer_id).subquery()
    rows = db.session.query(User, ChatMessage).options(joinedload(ChatMessage.sender)).join(
        latest, latest.c.customer_id == User.id
    ).join(
        ChatMessage, ChatMessage.id == latest.c.latest_message_id
    ).order_by(ChatMessage.created_at.desc()).all()
    unread_rows = db.session.query(
        ChatMessage.customer_id, func.count(ChatMessage.id)
    ).join(
        User, ChatMessage.sender_id == User.id
    ).filter(
        User.role == "customer",
        ChatMessage.read_at.is_(None),
    ).group_by(ChatMessage.customer_id).all()
    unread_counts = dict(unread_rows)
    return success_response({
        "conversations": [
            {
                "customer_id": customer.id,
                "customer_name": customer.name,
                "customer_email": customer.email,
                "latest_message": serialize_message(message),
                "unread_count": unread_counts.get(customer.id, 0),
            }
            for customer, message in rows
        ]
    })


@admin_chat_bp.get("/chat/conversations/<int:customer_id>/messages")
@roles_required("admin")
def get_admin_conversation(customer_id):
    customer = User.query.filter_by(id=customer_id, role="customer").first_or_404()
    messages = ChatMessage.query.options(joinedload(ChatMessage.sender)).filter_by(customer_id=customer.id).order_by(
        ChatMessage.created_at.desc(), ChatMessage.id.desc()
    ).limit(200).all()
    now = datetime.now(timezone.utc)
    changed = False
    for message in messages:
        if message.sender.role == "customer" and message.read_at is None:
            message.read_at = now
            changed = True
    if changed:
        db.session.commit()
    messages.reverse()
    return success_response({
        "customer": {"id": customer.id, "name": customer.name, "email": customer.email},
        "messages": [serialize_message(message) for message in messages],
    })


@admin_chat_bp.post("/chat/conversations/<int:customer_id>/messages")
@roles_required("admin")
def send_admin_message(customer_id):
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    body, error = _message_body(data)
    if error:
        return error_response("Validation failed", {"message": error}, 422)
    customer = User.query.filter_by(id=customer_id, role="customer").first_or_404()
    order_id = None
    if data.get("order_id") not in (None, ""):
        order_id, error = parse_positive_int(data.get("order_id"), "order_id")
        if error:
            return error_response("Validation failed", {"order_id": error}, 422)
        if Order.query.filter_by(id=order_id, user_id=customer.id).first() is None:
            return error_response("Order not found", status=404)
    message = ChatMessage(
        customer_id=customer.id,
        sender_id=current_user().id,
        order_id=order_id,
        body=body,
    )
    db.session.add(message)
    db.session.commit()
    return success_response({"message": serialize_message(message)}, "Reply sent", 201)
