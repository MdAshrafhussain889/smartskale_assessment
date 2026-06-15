"""add proctoring_options and section_cutoffs to assessments

Revision ID: ee1c2d3e4f
Revises: d4e5f6a7b8c9
Create Date: 2026-06-15 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ee1c2d3e4f'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('assessments', sa.Column('proctoring_options', sa.JSON(), nullable=True))
    op.add_column('assessments', sa.Column('section_cutoffs', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('assessments', 'section_cutoffs')
    op.drop_column('assessments', 'proctoring_options')
