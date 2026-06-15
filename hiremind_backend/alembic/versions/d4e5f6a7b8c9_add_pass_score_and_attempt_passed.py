"""add pass_score and attempt.passed

Revision ID: d4e5f6a7b8c9
Revises: c1a2b3d4e5f6
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c1a2b3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assessments", sa.Column("pass_score", sa.Integer(), nullable=True, server_default="70"))
    op.add_column("assessment_attempts", sa.Column("passed", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("assessment_attempts", "passed")
    op.drop_column("assessments", "pass_score")
