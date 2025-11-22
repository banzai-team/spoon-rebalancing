"""
Роуты для работы с чатом
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import uuid
from typing import Optional

from app.db import get_db, get_user_id
from app.api.schemas import ChatMessage, ChatResponse, ChatHistoryResponse
from app.services.chat_service import ChatService
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat_with_agent(
    message: ChatMessage,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Отправить сообщение агенту"""
    return await ChatService.send_message(db, message, user_id, AgentService.get_agent)


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    strategy_id: Optional[str] = Query(None, description="Фильтр по ID стратегии"),
    limit: int = Query(50, description="Максимальное количество сообщений"),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Получить историю чата пользователя"""
    return ChatService.get_chat_history(db, user_id, limit, strategy_id)


@router.get("/new-messages", response_model=ChatHistoryResponse)
async def get_new_messages(
    strategy_id: Optional[str] = Query(None, description="ID стратегии"),
    after_message_id: Optional[str] = Query(None, description="Получить сообщения после этого ID"),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Получить новые сообщения в чате (для polling)"""
    return ChatService.get_new_messages(db, user_id, strategy_id, after_message_id)

