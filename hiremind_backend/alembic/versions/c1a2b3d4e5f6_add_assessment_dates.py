"""add assessment start/end dates

Revision ID: c1a2b3d4e5f6
Revises: b17c2d4e6f90
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, None] = "b17c2d4e6f90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assessments", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("assessments", sa.Column("end_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("assessments", "end_date")
    op.drop_column("assessments", "start_date")
