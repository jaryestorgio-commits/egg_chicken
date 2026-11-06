"""add customer profile and notification settings

Revision ID: 32c7d52a91ef
Revises: f8a4c26d10e9
Create Date: 2026-11-06
"""
from alembic import op
import sqlalchemy as sa


revision = "32c7d52a91ef"
down_revision = "f8a4c26d10e9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("phone", sa.String(length=40), nullable=True))
    op.add_column("users", sa.Column("birthday", sa.Date(), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_order_updates", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "users",
        sa.Column("email_promotions", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("sms_order_updates", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("sms_promotions", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("users", "sms_promotions")
    op.drop_column("users", "sms_order_updates")
    op.drop_column("users", "email_promotions")
    op.drop_column("users", "email_order_updates")
    op.drop_column("users", "birthday")
    op.drop_column("users", "phone")
