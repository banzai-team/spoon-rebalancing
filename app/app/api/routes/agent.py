"""
Роуты для работы с агентом
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from app.db import get_db, get_user_id
from app.api.schemas import AgentConfigRequest
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/status")
async def get_agent_status(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Получить текущий статус и конфигурацию агента"""
    return AgentService.get_agent_status(db, user_id)


@router.post("/configure")
async def configure_agent(
    request: AgentConfigRequest,
    db: Session = Depends(get_db)
):
    """Настроить параметры агента"""
    return AgentService.configure_agent(
        mode=request.mode,
        min_profit_threshold_usd=request.min_profit_threshold_usd
    )

