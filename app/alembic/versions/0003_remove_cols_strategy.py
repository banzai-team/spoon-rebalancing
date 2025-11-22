"""Remove target_allocation and threshold_percent columns

Revision ID: 0003_remove_cols_strategy
Revises: 0002_add_token_balances_table
Create Date: 2025-11-22 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_remove_cols_strategy'
down_revision: Union[str, None] = '0002_add_token_balances_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if columns exist before dropping
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    if 'strategies' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('strategies')]
        
        if 'target_allocation' in columns:
            op.drop_column('strategies', 'target_allocation')
        
        if 'threshold_percent' in columns:
            op.drop_column('strategies', 'threshold_percent')
        
        if 'min_profit_threshold_usd' in columns:
            op.drop_column('strategies', 'min_profit_threshold_usd')


def downgrade() -> None:
    # Re-add columns if needed
    op.add_column('strategies', sa.Column('target_allocation', sa.JSON(), nullable=True))
    op.add_column('strategies', sa.Column('threshold_percent', sa.Float(), nullable=False, server_default='5.0'))
    op.add_column('strategies', sa.Column('min_profit_threshold_usd', sa.Float(), nullable=False, server_default='50.0'))
