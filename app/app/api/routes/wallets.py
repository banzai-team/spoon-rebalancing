"""
Роуты для работы с кошельками
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
import logging
from app.db import get_db, get_user_id
from app.api.schemas import WalletCreate, WalletUpdate, WalletResponse
from app.services.wallet_service import WalletService

router = APIRouter(prefix="/api/wallets", tags=["wallets"])

logger = logging.getLogger(__name__)


@router.get("", response_model=List[WalletResponse])
async def get_wallets(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Получить список всех кошельков пользователя"""
    return WalletService.get_wallets(db, user_id)


@router.post("", response_model=WalletResponse, status_code=201)
async def create_wallet(
    wallet: WalletCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Создать новый кошелек"""
    logger.info("Creating wallet: %s", wallet)
    return WalletService.create_wallet(db, wallet, user_id)


@router.get("/{wallet_id}", response_model=WalletResponse)
async def get_wallet(
    wallet_id: str,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Получить кошелек по ID"""
    logger.info("Getting wallet: %s", wallet_id)
    return WalletService.get_wallet(db, wallet_id, user_id)


@router.put("/{wallet_id}", response_model=WalletResponse)
async def update_wallet(
    wallet_id: str,
    wallet_update: WalletUpdate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Обновить кошелек"""
    return WalletService.update_wallet(db, wallet_id, wallet_update, user_id)


@router.delete("/{wallet_id}", status_code=204)
async def delete_wallet(
    wallet_id: str,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id)
):
    """Удалить кошелек"""
    WalletService.delete_wallet(db, wallet_id, user_id)
    return None

