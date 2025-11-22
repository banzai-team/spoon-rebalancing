"""Add last_checked_at to strategy

Revision ID: 0005_add_last_checked
Revises: 0004_add_chat_messages_idx
Create Date: 2025-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = '0005_add_last_checked'
down_revision: Union[str, None] = '0004_add_chat_messages_idx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add last_checked_at column to strategies table
    op.add_column('strategies', sa.Column('last_checked_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove last_checked_at column from strategies table
    op.drop_column('strategies', 'last_checked_at')

