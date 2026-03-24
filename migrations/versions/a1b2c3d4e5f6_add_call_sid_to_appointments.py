"""add call_sid to appointments

Revision ID: a1b2c3d4e5f6
Revises: ef5e75384a39
Create Date: 2026-03-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'ef5e75384a39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('appointments', sa.Column('call_sid', sa.Text(), nullable=True))
    op.create_index(op.f('ix_appointments_call_sid'), 'appointments', ['call_sid'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_appointments_call_sid'), table_name='appointments')
    op.drop_column('appointments', 'call_sid')
