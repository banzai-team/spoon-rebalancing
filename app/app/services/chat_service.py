"""
Сервис для работы с чатом
"""
import uuid
import json
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime
import logging

from app.db.models import ChatMessageDB, Strategy, Wallet, StrategyWallet
from app.api.schemas import ChatMessage, ChatResponse, ChatHistoryResponse
from app.services.strategy_service import StrategyService

logger = logging.getLogger(__name__)


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
        is_first_message = False
        
        # Если strategy_id не указан, проверяем, есть ли уже стратегия для этого пользователя
        # Если нет - создаем новую из первого сообщения
        if not message.strategy_id:
            # Проверяем, есть ли уже активные стратегии у пользователя
            existing_strategy = db.query(Strategy).filter(
                Strategy.user_id == user_id
            ).first()
            
            if not existing_strategy:
                # Создаем новую стратегию из первого сообщения
                is_first_message = True
                strategy_name = f"Стратегия от {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
                logger.info(f"Создание новой стратегии для пользователя {user_id} из первого сообщения")
                
                # Извлекаем кошельки, если указаны
                wallet_uuids = []
                if message.wallet_ids:
                    for wallet_id in message.wallet_ids:
                        try:
                            wallet_uuid = uuid.UUID(wallet_id)
                            wallet = db.query(Wallet).filter(
                                Wallet.id == wallet_uuid,
                                Wallet.user_id == user_id
                            ).first()
                            if wallet:
                                wallet_uuids.append(wallet_uuid)
                        except ValueError:
                            pass
                
                # Создаем стратегию через сервис
                from app.api.schemas import StrategyCreate
                strategy_create = StrategyCreate(
                    name=strategy_name,
                    description=message.message,
                    wallet_ids=message.wallet_ids or []
                )
                strategy_response = await StrategyService.create_strategy(db, strategy_create, user_id)
                strategy_uuid = uuid.UUID(strategy_response.id)
                logger.info(f"Стратегия создана: {strategy_response.id} для пользователя {user_id}")
                
                context_parts.append(f"✅ New strategy created: {strategy_name}")
                context_parts.append(f"Strategy description: {message.message}")
            else:
                # Используем существующую стратегию
                strategy_uuid = existing_strategy.id
        else:
            try:
                strategy_uuid = uuid.UUID(message.strategy_id)
                strategy = db.query(Strategy).filter(
                    Strategy.id == strategy_uuid,
                    Strategy.user_id == user_id
                ).first()
                if not strategy:
                    raise HTTPException(status_code=404, detail="Стратегия не найдена")
            except ValueError:
                raise HTTPException(status_code=400, detail="Неверный формат ID стратегии")
        
        # Получаем информацию о стратегии
        strategy = db.query(Strategy).filter(
            Strategy.id == strategy_uuid,
            Strategy.user_id == user_id
        ).first()
        
        if strategy:
            context_parts.append(f"Strategy: {strategy.name}")
            context_parts.append(f"Current description: {strategy.description}")
            
            # Получаем кошельки стратегии
            wallet_links = db.query(StrategyWallet).filter(
                StrategyWallet.strategy_id == strategy.id
            ).all()
            if wallet_links:
                wallet_ids_list = [str(sw.wallet_id) for sw in wallet_links]
                wallets = db.query(Wallet).filter(
                    Wallet.id.in_([sw.wallet_id for sw in wallet_links]),
                    Wallet.user_id == user_id
                ).all()
                wallet_info = [f"{w.label or w.address} ({w.chain})" for w in wallets]
                if wallet_info:
                    context_parts.append(f"Wallets: {', '.join(wallet_info)}")
        
        # Если указаны дополнительные кошельки в сообщении
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
                context_parts.append(f"Additional wallets: {', '.join(wallet_info)}")
        
        # Формируем промпт
        if is_first_message:
            prompt = f"""
            The user is creating a new portfolio rebalancing strategy.
            Their description: "{message.message}"
            
            Confirm the strategy creation and explain that you will periodically check the portfolio and provide rebalancing recommendations.
            """
        else:
            if context_parts:
                prompt = f"Context:\n" + "\n".join(context_parts) + f"\n\nUser request: {message.message}"
            else:
                prompt = message.message
        
        # Получаем ответ от агента
        response = await agent.run(prompt)
        
        # Если пользователь обновил описание стратегии, обновляем стратегию
        if strategy and not is_first_message:
            # Проверяем, хочет ли пользователь обновить стратегию
            update_keywords = ["изменить", "обновить", "изменить стратегию", "новое описание", "измени описание"]
            if any(keyword in message.message.lower() for keyword in update_keywords):
                # Пытаемся извлечь новое описание из ответа агента или сообщения
                # Простая эвристика: если сообщение длинное и не похоже на вопрос, это новое описание
                if len(message.message) > 20 and "?" not in message.message:
                    from app.api.schemas import StrategyUpdate
                    strategy_update = StrategyUpdate(description=message.message)
                    await StrategyService.update_strategy(db, str(strategy.id), strategy_update, user_id)
        
        # Сохраняем в БД
        wallet_ids_for_db = None
        if message.wallet_ids:
            wallet_ids_for_db = [str(wid) for wid in message.wallet_ids]
        elif strategy:
            wallet_links = db.query(StrategyWallet).filter(StrategyWallet.strategy_id == strategy.id).all()
            wallet_ids_for_db = [str(sw.wallet_id) for sw in wallet_links]
        
        db_chat = ChatMessageDB(
            user_id=user_id,
            user_message=message.message,
            agent_response=response,
            strategy_id=strategy_uuid,
            wallet_ids=wallet_ids_for_db
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
        limit: int = 50,
        strategy_id: Optional[str] = None
    ) -> ChatHistoryResponse:
        """Получить историю чата пользователя"""
        query = db.query(ChatMessageDB).filter(ChatMessageDB.user_id == user_id)
        
        if strategy_id:
            try:
                strategy_uuid = uuid.UUID(strategy_id)
                query = query.filter(ChatMessageDB.strategy_id == strategy_uuid)
            except ValueError:
                pass
        
        chat_messages = query.order_by(ChatMessageDB.created_at.desc()).limit(limit).all()
        
        messages = [
            ChatResponse(
                message_id=str(msg.id),
                user_message=msg.user_message,
                agent_response=msg.agent_response,
                timestamp=msg.created_at.isoformat()
            )
            for msg in chat_messages
        ]
        
        # Переворачиваем список, чтобы старые сообщения были первыми
        messages.reverse()
        
        total = query.count()
        
        return ChatHistoryResponse(messages=messages, total=total)
    
    @staticmethod
    def get_new_messages(
        db: Session,
        user_id: uuid.UUID,
        strategy_id: Optional[str] = None,
        after_message_id: Optional[str] = None
    ) -> ChatHistoryResponse:
        """Получить новые сообщения после указанного ID"""
        query = db.query(ChatMessageDB).filter(ChatMessageDB.user_id == user_id)
        
        if strategy_id:
            try:
                strategy_uuid = uuid.UUID(strategy_id)
                query = query.filter(ChatMessageDB.strategy_id == strategy_uuid)
            except ValueError:
                pass
        
        if after_message_id:
            try:
                after_uuid = uuid.UUID(after_message_id)
                after_message = db.query(ChatMessageDB).filter(
                    ChatMessageDB.id == after_uuid
                ).first()
                if after_message:
                    query = query.filter(ChatMessageDB.created_at > after_message.created_at)
            except ValueError:
                pass
        
        chat_messages = query.order_by(ChatMessageDB.created_at.asc()).all()
        
        messages = [
            ChatResponse(
                message_id=str(msg.id),
                user_message=msg.user_message,
                agent_response=msg.agent_response,
                timestamp=msg.created_at.isoformat()
            )
            for msg in chat_messages
        ]
        
        total = query.count()
        
        return ChatHistoryResponse(messages=messages, total=total)

