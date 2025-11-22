"""
Сервис для работы с чатом
"""
import uuid
import json
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.models import ChatMessageDB, Strategy, Wallet
from app.api.schemas import ChatMessage, ChatResponse, ChatHistoryResponse


class ChatService:
    """Сервис для управления чатом"""
    
    @staticmethod
    async def send_message(
        db: Session,
        message: ChatMessage,
        user_id: uuid.UUID,
        get_agent_func
    ) -> ChatResponse:
        """Отправить сообщение агенту"""
        agent = get_agent_func()
        
        # Формируем контекст
        context_parts = []
        strategy_uuid = None
        
        if message.strategy_id:
            try:
                strategy_uuid = uuid.UUID(message.strategy_id)
                strategy = db.query(Strategy).filter(
                    Strategy.id == strategy_uuid,
                    Strategy.user_id == user_id
                ).first()
                if strategy:
                    context_parts.append(f"Стратегия: {strategy.name}")
                    context_parts.append(f"Описание: {strategy.description}")
                    if strategy.target_allocation:
                        context_parts.append(
                            f"Целевое распределение: {json.dumps(strategy.target_allocation, ensure_ascii=False)}"
                        )
            except ValueError:
                pass
        
        if message.wallet_ids:
            wallet_info = []
            for wallet_id in message.wallet_ids:
                try:
                    wallet_uuid = uuid.UUID(wallet_id)
                    wallet = db.query(Wallet).filter(
                        Wallet.id == wallet_uuid,
                        Wallet.user_id == user_id
                    ).first()
                    if wallet:
                        wallet_info.append(f"{wallet.label or wallet.address} ({wallet.chain})")
                except ValueError:
                    pass
            if wallet_info:
                context_parts.append(f"Кошельки: {', '.join(wallet_info)}")
        
        # Формируем промпт
        if context_parts:
            prompt = f"Контекст:\n" + "\n".join(context_parts) + f"\n\nЗапрос пользователя: {message.message}"
        else:
            prompt = message.message
        
        # Получаем ответ от агента
        response = await agent.run(prompt)
        
        # Сохраняем в БД
        db_chat = ChatMessageDB(
            user_id=user_id,
            user_message=message.message,
            agent_response=response,
            strategy_id=strategy_uuid,
            wallet_ids=[uuid.UUID(wid) for wid in (message.wallet_ids or []) if wid]
        )
        db.add(db_chat)
        db.commit()
        db.refresh(db_chat)
        
        return ChatResponse(
            message_id=str(db_chat.id),
            user_message=db_chat.user_message,
            agent_response=db_chat.agent_response,
            timestamp=db_chat.created_at.isoformat()
        )
    
    @staticmethod
    def get_chat_history(
        db: Session,
        user_id: uuid.UUID,
        limit: int = 50
    ) -> ChatHistoryResponse:
        """Получить историю чата пользователя"""
        chat_messages = db.query(ChatMessageDB).filter(
            ChatMessageDB.user_id == user_id
        ).order_by(ChatMessageDB.created_at.desc()).limit(limit).all()
        
        messages = [
            ChatResponse(
                message_id=str(msg.id),
                user_message=msg.user_message,
                agent_response=msg.agent_response,
                timestamp=msg.created_at.isoformat()
            )
            for msg in chat_messages
        ]
        
        total = db.query(ChatMessageDB).filter(ChatMessageDB.user_id == user_id).count()
        
        return ChatHistoryResponse(messages=messages, total=total)

