"""Initial migration with users and user_id support

Revision ID: 7fbc40bbe4c3
Revises: 
Create Date: 2025-11-22 18:16:15.619701

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


# revision identifiers, used by Alembic.
revision: str = '7fbc40bbe4c3'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if tables already exist (for idempotency)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    def index_exists(table_name: str, index_name: str) -> bool:
        """Check if index exists on table"""
        if table_name not in existing_tables:
            return False
        indexes = inspector.get_indexes(table_name)
        return any(idx['name'] == index_name for idx in indexes)
    
    # Create users table
    if 'users' not in existing_tables:
        op.create_table(
            'users',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('username', sa.String(255), nullable=False, unique=True),
            sa.Column('email', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
        )

        user1_id = uuid.UUID('00000000-0000-0000-0000-000000000001')
        from datetime import datetime
        now = datetime.utcnow()
        op.execute(
            sa.text("""
                INSERT INTO users (id, username, email, created_at, updated_at)
                VALUES (:id, 'user1', 'user1@example.com', :created_at, :updated_at)
                ON CONFLICT (id) DO NOTHING
            """).bindparams(
                id=user1_id,
                created_at=now,
                updated_at=now
            )
        )
    
    # Create wallets table
    if 'wallets' not in existing_tables:
        op.create_table(
            'wallets',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('address', sa.String(255), nullable=False),
            sa.Column('chain', sa.String(50), nullable=False),
            sa.Column('label', sa.String(255), nullable=True),
            sa.Column('tokens', postgresql.JSON, nullable=False, server_default='[]'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        )
        if not index_exists('wallets', 'ix_wallets_user_id'):
            op.create_index('ix_wallets_user_id', 'wallets', ['user_id'])
        if not index_exists('wallets', 'ix_wallets_user_address'):
            op.create_index('ix_wallets_user_address', 'wallets', ['user_id', 'address'], unique=True)
    
    # Create strategies table
    if 'strategies' not in existing_tables:
        op.create_table(
            'strategies',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('target_allocation', postgresql.JSON, nullable=True),
            sa.Column('threshold_percent', sa.Float(), nullable=False, server_default='5.0'),
            sa.Column('min_profit_threshold_usd', sa.Float(), nullable=False, server_default='50.0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        )
        if not index_exists('strategies', 'ix_strategies_user_id'):
            op.create_index('ix_strategies_user_id', 'strategies', ['user_id'])
    
    # Create strategy_wallets table (many-to-many)
    if 'strategy_wallets' not in existing_tables:
        op.create_table(
            'strategy_wallets',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('strategy_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('wallet_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id'], ),
            sa.ForeignKeyConstraint(['wallet_id'], ['wallets.id'], ),
        )
        if not index_exists('strategy_wallets', 'ix_strategy_wallets_strategy_id'):
            op.create_index('ix_strategy_wallets_strategy_id', 'strategy_wallets', ['strategy_id'])
        if not index_exists('strategy_wallets', 'ix_strategy_wallets_wallet_id'):
            op.create_index('ix_strategy_wallets_wallet_id', 'strategy_wallets', ['wallet_id'])
    
    # Create recommendations table
    if 'recommendations' not in existing_tables:
        op.create_table(
            'recommendations',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('strategy_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('recommendation', sa.Text(), nullable=False),
            sa.Column('analysis', postgresql.JSON, nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id'], ),
        )
        if not index_exists('recommendations', 'ix_recommendations_user_id'):
            op.create_index('ix_recommendations_user_id', 'recommendations', ['user_id'])
        if not index_exists('recommendations', 'ix_recommendations_strategy_id'):
            op.create_index('ix_recommendations_strategy_id', 'recommendations', ['strategy_id'])
    
    # Create chat_messages table
    if 'chat_messages' not in existing_tables:
        op.create_table(
            'chat_messages',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_message', sa.Text(), nullable=False),
            sa.Column('agent_response', sa.Text(), nullable=False),
            sa.Column('strategy_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('wallet_ids', postgresql.JSON, nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id'], ),
        )
        if not index_exists('chat_messages', 'ix_chat_messages_user_id'):
            op.create_index('ix_chat_messages_user_id', 'chat_messages', ['user_id'])
    
        


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('chat_messages')
    op.drop_table('recommendations')
    op.drop_table('strategy_wallets')
    op.drop_table('strategies')
    op.drop_table('wallets')
    op.drop_table('users')
