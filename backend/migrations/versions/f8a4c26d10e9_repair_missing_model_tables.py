"""create model tables missing from databases already at the previous head

Revision ID: f8a4c26d10e9
Revises: 94ae2b198acd
Create Date: 2026-11-02
"""
from alembic import op
import models
from extensions import db


revision = "f8a4c26d10e9"
down_revision = "94ae2b198acd"
branch_labels = None
depends_on = None


def upgrade():
    db.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError("The schema repair migration is irreversible to protect existing data.")
