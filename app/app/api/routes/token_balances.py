"""
Роуты для работы с балансами токенов в кошельках
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import uuid

from app.db import get_db, get_user_id
from app.api.schemas import (
    WalletTokenBalanceCreate,
    WalletTokenBalanceUpdate,
    WalletTokenBalanceResponse
)
from app.services.token_balance_service import TokenBalanceService

router = APIRouter(prefix="/api/wallet-token-balances", tags=["token-balances"])


@router.get("", response_model=List[WalletTokenBalanceResponse])
async def get_balances(
    wallet_id: Optional[str] = Query(None, description="Фильтр по ID кошелька"),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Получить список балансов токенов пользователя"""
    return TokenBalanceService.get_balances(db, user_id, wallet_id)


@router.post("", response_model=WalletTokenBalanceResponse, status_code=201)
async def create_balance(
    balance: WalletTokenBalanceCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Создать или обновить запись о балансе токена"""
    return TokenBalanceService.create_balance(db, balance, user_id)


@router.get("/{balance_id}", response_model=WalletTokenBalanceResponse)
async def get_balance(
    balance_id: str,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Получить баланс токена по ID"""
    return TokenBalanceService.get_balance(db, balance_id, user_id)


@router.put("/{balance_id}", response_model=WalletTokenBalanceResponse)
async def update_balance(
    balance_id: str,
    balance_update: WalletTokenBalanceUpdate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Обновить баланс токена"""
    return TokenBalanceService.update_balance(db, balance_id, balance_update, user_id)


@router.delete("/{balance_id}", status_code=204)
async def delete_balance(
    balance_id: str,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Удалить запись о балансе токена"""
    TokenBalanceService.delete_balance(db, balance_id, user_id)
    return None

