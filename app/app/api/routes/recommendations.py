"""
Роуты для работы с рекомендациями
"""
from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from app.db import get_db, get_user_id
from app.api.schemas import RecommendationRequest, RecommendationResponse
from app.services.recommendation_service import RecommendationService
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.post("", response_model=RecommendationResponse, status_code=201)
async def create_recommendation(
    request: RecommendationRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Получить рекомендацию по ребалансировке для стратегии"""
    return await RecommendationService.create_recommendation(
        db, request, user_id, AgentService.get_agent
    )


@router.get("/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation(
    recommendation_id: str,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Получить конкретную рекомендацию по ID"""
    return RecommendationService.get_recommendation(db, recommendation_id, user_id)


@router.get("", response_model=List[RecommendationResponse])
async def get_recommendations(
    strategy_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Получить историю рекомендаций пользователя"""
    return RecommendationService.get_recommendations(db, user_id, strategy_id, limit)

