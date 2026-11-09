"""add admin discount management

Revision ID: df5b217c8a41
Revises: 32c7d52a91ef
Create Date: 2026-11-09
"""

from alembic import op
import sqlalchemy as sa


revision = "df5b217c8a41"
down_revision = "32c7d52a91ef"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "discounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("discount_type", sa.String(length=20), nullable=False),
        sa.Column("value", sa.Numeric(10, 2), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("value > 0", name="ck_discounts_value_positive"),
        sa.CheckConstraint("discount_type IN ('percentage', 'fixed')", name="ck_discounts_type_valid"),
    )

def downgrade():
    op.drop_table("discounts")
