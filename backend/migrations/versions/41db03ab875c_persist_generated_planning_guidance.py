"""persist generated task and vendor guidance

Revision ID: 41db03ab875c
Revises: 078bdffa6615
Create Date: 2026-11-01 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "41db03ab875c"
down_revision = "078bdffa6615"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("relative_timing_suggestion", sa.String(length=160), nullable=True))
    op.add_column("vendors", sa.Column("follow_up_checklist", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("vendors", "follow_up_checklist")
    op.drop_column("tasks", "relative_timing_suggestion")
