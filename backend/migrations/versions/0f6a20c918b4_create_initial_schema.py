"""create the initial schema for all registered models

Revision ID: 0f6a20c918b4
Revises:
Create Date: 2026-11-02
"""
from alembic import op
import sqlalchemy as sa


revision = "0f6a20c918b4"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(bind, name):
    return sa.inspect(bind).has_table(name)


def upgrade():
    bind = op.get_bind()

    if not _has_table(bind, "admin_notifications"):
        op.create_table(
            "admin_notifications",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("event_key", sa.String(length=160), nullable=False),
            sa.Column("kind", sa.String(length=40), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("message", sa.String(length=500), nullable=False),
            sa.Column("related_type", sa.String(length=30), nullable=False),
            sa.Column("related_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_key"),
        )
    if not _has_table(bind, "categories"):
        op.create_table(
            "categories",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
    if not _has_table(bind, "token_blocklist"):
        op.create_table(
            "token_blocklist",
            sa.Column("jti", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("jti"),
        )
    if not _has_table(bind, "users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("email", sa.String(length=120), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=30), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)
    if not _has_table(bind, "addresses"):
        op.create_table(
            "addresses",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("full_name", sa.String(length=150), nullable=False),
            sa.Column("phone", sa.String(length=40), nullable=False),
            sa.Column("address_line", sa.String(length=300), nullable=False),
            sa.Column("city", sa.String(length=120), nullable=False),
            sa.Column("province", sa.String(length=120), nullable=False),
            sa.Column("postal_code", sa.String(length=20), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_addresses_user_id", "addresses", ["user_id"], unique=False)
    if not _has_table(bind, "admin_notification_reads"):
        op.create_table(
            "admin_notification_reads",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("notification_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["notification_id"],
                ["admin_notifications.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "notification_id",
                "user_id",
                name="uq_admin_notification_read_user",
            ),
        )
        op.create_index(
            "ix_admin_notification_reads_notification_id",
            "admin_notification_reads",
            ["notification_id"],
            unique=False,
        )
        op.create_index(
            "ix_admin_notification_reads_user_id",
            "admin_notification_reads",
            ["user_id"],
            unique=False,
        )
    if not _has_table(bind, "audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_table(bind, "carts"):
        op.create_table(
            "carts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )
    if not _has_table(bind, "orders"):
        op.create_table(
            "orders",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("total_amount", sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column("shipping_address", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_table(bind, "products"):
        op.create_table(
            "products",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column("stock", sa.Integer(), nullable=False),
            sa.Column("image_url", sa.String(length=500), nullable=True),
            sa.Column("category_id", sa.Integer(), nullable=True),
            sa.Column(
                "is_active",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("price >= 0", name="ck_products_price_nonnegative"),
            sa.CheckConstraint("stock >= 0", name="ck_products_stock_nonnegative"),
            sa.ForeignKeyConstraint(
                ["category_id"],
                ["categories.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_products_is_active", "products", ["is_active"], unique=False)
    if not _has_table(bind, "cart_items"):
        op.create_table(
            "cart_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("cart_id", sa.Integer(), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["cart_id"], ["carts.id"]),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_table(bind, "chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("customer_id", sa.Integer(), nullable=False),
            sa.Column("sender_id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["customer_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["order_id"],
                ["orders.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["sender_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_chat_messages_customer_created",
            "chat_messages",
            ["customer_id", "created_at"],
            unique=False,
        )
        op.create_index(
            "ix_chat_messages_customer_id",
            "chat_messages",
            ["customer_id"],
            unique=False,
        )
        op.create_index(
            "ix_chat_messages_order_id",
            "chat_messages",
            ["order_id"],
            unique=False,
        )
        op.create_index(
            "ix_chat_messages_sender_id",
            "chat_messages",
            ["sender_id"],
            unique=False,
        )
    if not _has_table(bind, "inventory"):
        op.create_table(
            "inventory",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["product_id"],
                ["products.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("product_id"),
        )
    if not _has_table(bind, "order_items"):
        op.create_table(
            "order_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("unit_price", sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column("subtotal", sa.Numeric(precision=10, scale=2), nullable=False),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_table(bind, "payments"):
        op.create_table(
            "payments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("payment_method", sa.String(length=40), nullable=False),
            sa.Column("payment_status", sa.String(length=30), nullable=False),
            sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column("transaction_reference", sa.String(length=120), nullable=True),
            sa.Column("checkout_url", sa.String(length=512), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("transaction_reference"),
        )
        op.create_index("ix_payments_order_id", "payments", ["order_id"], unique=False)


def downgrade():
    raise RuntimeError("The initial schema migration is irreversible to protect existing data.")
