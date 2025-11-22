"""Add wallet_token_balances table

Revision ID: 42a2f391f505
Revises: 7fbc40bbe4c3
Create Date: 2025-11-22 19:40:36.669469

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '42a2f391f505'
down_revision: Union[str, None] = '7fbc40bbe4c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create wallet_token_balances table
    op.create_table(
        'wallet_token_balances',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('wallet_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('token_symbol', sa.String(length=50), nullable=False),
        sa.Column('balance', sa.String(length=255), nullable=False),
        sa.Column('balance_usd', sa.Float(), nullable=True),
        sa.Column('chain', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['wallet_id'], ['wallets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for better query performance
    op.create_index('ix_wallet_token_balances_wallet_id', 'wallet_token_balances', ['wallet_id'])
    op.create_index('ix_wallet_token_balances_user_id', 'wallet_token_balances', ['user_id'])
    op.create_index('ix_wallet_token_balances_token_symbol', 'wallet_token_balances', ['token_symbol'])
    op.create_index('ix_wallet_token_balances_wallet_token', 'wallet_token_balances', ['wallet_id', 'token_symbol'], unique=True)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_wallet_token_balances_wallet_token', table_name='wallet_token_balances')
    op.drop_index('ix_wallet_token_balances_token_symbol', table_name='wallet_token_balances')
    op.drop_index('ix_wallet_token_balances_user_id', table_name='wallet_token_balances')
    op.drop_index('ix_wallet_token_balances_wallet_id', table_name='wallet_token_balances')
    
    # Drop table
    op.drop_table('wallet_token_balances')
