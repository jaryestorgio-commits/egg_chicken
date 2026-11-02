"""add product active status and constraints

Revision ID: 341555b0d1ed
Revises: 
Create Date: 2026-09-30 20:47:28.043448

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '341555b0d1ed'
down_revision = "0f6a20c918b4"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("products"):
        return

    columns = {column["name"] for column in inspector.get_columns("products")}
    if "is_active" not in columns:
        op.add_column(
            "products",
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        )

    inspector = sa.inspect(op.get_bind())
    checks = {constraint["name"] for constraint in inspector.get_check_constraints("products")}
    if "ck_products_price_nonnegative" not in checks:
        op.create_check_constraint("ck_products_price_nonnegative", "products", "price >= 0")
    if "ck_products_stock_nonnegative" not in checks:
        op.create_check_constraint("ck_products_stock_nonnegative", "products", "stock >= 0")

    indexes = {index["name"] for index in inspector.get_indexes("products")}
    if "ix_products_is_active" not in indexes:
        op.create_index("ix_products_is_active", "products", ["is_active"], unique=False)


def downgrade():
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_index("ix_products_is_active")
        batch_op.drop_constraint("ck_products_stock_nonnegative", type_="check")
        batch_op.drop_constraint("ck_products_price_nonnegative", type_="check")
        batch_op.drop_column("is_active")
