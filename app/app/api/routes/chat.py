"""
Роуты для работы с чатом
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

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
    limit: int = 50,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Получить историю чата пользователя"""
    return ChatService.get_chat_history(db, user_id, limit)

