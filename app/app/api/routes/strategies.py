"""
Роуты для работы со стратегиями
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.db import get_db, get_user_id
from app.db.models import Strategy
from app.api.schemas import StrategyCreate, StrategyUpdate, StrategyResponse
from app.services.strategy_service import StrategyService

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


@router.get("", response_model=List[StrategyResponse])
async def get_strategies(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Получить список всех стратегий пользователя"""
    return StrategyService.get_strategies(db, user_id)


@router.post("", response_model=StrategyResponse, status_code=201)
async def create_strategy(
    strategy: StrategyCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Создать новую стратегию"""
    return await StrategyService.create_strategy(db, strategy, user_id)


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: str,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Получить стратегию по ID"""
    return StrategyService.get_strategy(db, strategy_id, user_id)


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: str,
    strategy_update: StrategyUpdate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Обновить стратегию"""
    return await StrategyService.update_strategy(db, strategy_id, strategy_update, user_id)


@router.delete("/{strategy_id}", status_code=204)
async def delete_strategy(
    strategy_id: str,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Удалить стратегию"""
    StrategyService.delete_strategy(db, strategy_id, user_id)
    return None


@router.post("/{strategy_id}/parse")
async def parse_strategy(
    strategy_id: str,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Парсить описание стратегии в целевое распределение"""
    strategy = StrategyService.get_strategy(db, strategy_id, user_id)
    
    # Получаем стратегию из БД для обновления
    try:
        strategy_uuid = uuid.UUID(strategy_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат ID")
    
    db_strategy = db.query(Strategy).filter(
        Strategy.id == strategy_uuid,
        Strategy.user_id == user_id
    ).first()
    
    if not db_strategy:
        raise HTTPException(status_code=404, detail="Стратегия не найдена")
    
    # Парсим описание
    target_allocation = await StrategyService.parse_strategy_description(db_strategy.description)
    
    # Обновляем стратегию
    db_strategy.target_allocation = target_allocation
    db.commit()
    db.refresh(db_strategy)
    
    return {
        "success": True,
        "target_allocation": target_allocation,
        "strategy_id": strategy_id
    }

