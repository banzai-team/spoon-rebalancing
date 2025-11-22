"""Add index on strategy_id in chat_messages

Revision ID: add_chat_strategy_index
Revises: 81223512a850
Create Date: 2025-11-22 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_chat_strategy_index'
down_revision: Union[str, None] = '81223512a850'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Проверяем существование таблицы и индекса
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    if 'chat_messages' in inspector.get_table_names():
        indexes = [idx['name'] for idx in inspector.get_indexes('chat_messages')]
        
        # Добавляем индекс на strategy_id для оптимизации запросов
        if 'ix_chat_messages_strategy_id' not in indexes:
            op.create_index('ix_chat_messages_strategy_id', 'chat_messages', ['strategy_id'])
        
        # Добавляем индекс на created_at для сортировки
        if 'ix_chat_messages_created_at' not in indexes:
            op.create_index('ix_chat_messages_created_at', 'chat_messages', ['created_at'])


def downgrade() -> None:
    # Удаляем индексы
    op.drop_index('ix_chat_messages_created_at', table_name='chat_messages')
    op.drop_index('ix_chat_messages_strategy_id', table_name='chat_messages')

