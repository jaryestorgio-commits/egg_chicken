"""add hosted checkout URL to payments

Revision ID: 7c10d9a8b5f2
Revises: 341555b0d1ed
Create Date: 2026-10-18 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "7c10d9a8b5f2"
down_revision = "341555b0d1ed"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("payments"):
        columns = {column["name"] for column in inspector.get_columns("payments")}
        if "checkout_url" not in columns:
            op.add_column("payments", sa.Column("checkout_url", sa.String(length=512), nullable=True))


def downgrade():
    op.drop_column("payments", "checkout_url")
