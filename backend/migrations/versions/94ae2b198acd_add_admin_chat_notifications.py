"""add admin chat and notifications

Revision ID: 94ae2b198acd
Revises: 7c10d9a8b5f2
Create Date: 2026-10-25 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "94ae2b198acd"
down_revision = "7c10d9a8b5f2"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        )
    inspector = sa.inspect(bind)
    chat_indexes = {index["name"] for index in inspector.get_indexes("chat_messages")}
    for name, columns in (
        ("ix_chat_messages_customer_id", ["customer_id"]),
        ("ix_chat_messages_sender_id", ["sender_id"]),
        ("ix_chat_messages_order_id", ["order_id"]),
        ("ix_chat_messages_customer_created", ["customer_id", "created_at"]),
    ):
        if name not in chat_indexes:
            op.create_index(name, "chat_messages", columns)

    if not inspector.has_table("admin_notifications"):
        op.create_table(
            "admin_notifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_key", sa.String(length=160), nullable=False, unique=True),
            sa.Column("kind", sa.String(length=40), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("message", sa.String(length=500), nullable=False),
            sa.Column("related_type", sa.String(length=30), nullable=False),
            sa.Column("related_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    if not inspector.has_table("admin_notification_reads"):
        op.create_table(
            "admin_notification_reads",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("notification_id", sa.Integer(), sa.ForeignKey("admin_notifications.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("notification_id", "user_id", name="uq_admin_notification_read_user"),
        )
    inspector = sa.inspect(bind)
    read_indexes = {index["name"] for index in inspector.get_indexes("admin_notification_reads")}
    for name, columns in (
        ("ix_admin_notification_reads_notification_id", ["notification_id"]),
        ("ix_admin_notification_reads_user_id", ["user_id"]),
    ):
        if name not in read_indexes:
            op.create_index(name, "admin_notification_reads", columns)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("admin_notification_reads"):
        op.drop_index("ix_admin_notification_reads_user_id", table_name="admin_notification_reads")
        op.drop_index("ix_admin_notification_reads_notification_id", table_name="admin_notification_reads")
        op.drop_table("admin_notification_reads")
    if inspector.has_table("admin_notifications"):
        op.drop_table("admin_notifications")
    if inspector.has_table("chat_messages"):
        for index_name in (
            "ix_chat_messages_customer_created",
            "ix_chat_messages_order_id",
            "ix_chat_messages_sender_id",
            "ix_chat_messages_customer_id",
        ):
            op.drop_index(index_name, table_name="chat_messages")
        op.drop_table("chat_messages")
