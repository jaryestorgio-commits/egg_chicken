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
    op.create_index("ix_chat_messages_customer_id", "chat_messages", ["customer_id"])
    op.create_index("ix_chat_messages_sender_id", "chat_messages", ["sender_id"])
    op.create_index("ix_chat_messages_order_id", "chat_messages", ["order_id"])
    op.create_index("ix_chat_messages_customer_created", "chat_messages", ["customer_id", "created_at"])
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
    op.create_table(
        "admin_notification_reads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("notification_id", sa.Integer(), sa.ForeignKey("admin_notifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("notification_id", "user_id", name="uq_admin_notification_read_user"),
    )
    op.create_index("ix_admin_notification_reads_notification_id", "admin_notification_reads", ["notification_id"])
    op.create_index("ix_admin_notification_reads_user_id", "admin_notification_reads", ["user_id"])


def downgrade():
    op.drop_index("ix_admin_notification_reads_user_id", table_name="admin_notification_reads")
    op.drop_index("ix_admin_notification_reads_notification_id", table_name="admin_notification_reads")
    op.drop_table("admin_notification_reads")
    op.drop_table("admin_notifications")
    op.drop_index("ix_chat_messages_customer_created", table_name="chat_messages")
    op.drop_index("ix_chat_messages_order_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_sender_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_customer_id", table_name="chat_messages")
    op.drop_table("chat_messages")
