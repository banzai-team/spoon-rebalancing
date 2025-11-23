"""
Сервис для работы с кошельками
"""
import uuid
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.models import Wallet
from app.api.schemas import WalletCreate, WalletUpdate, WalletResponse
import logging

logger = logging.getLogger(__name__)

class WalletService:
    """Сервис для управления кошельками"""
    
    @staticmethod
    def get_wallets(db: Session, user_id: uuid.UUID) -> List[WalletResponse]:
        """Получить список всех кошельков пользователя"""
        wallets = db.query(Wallet).filter(Wallet.user_id == user_id).all()
        return [
            WalletResponse(
                id=str(w.id),
                address=w.address,
                chain=w.chain,
                label=w.label,
                tokens=w.tokens or ["BTC", "ETH", "USDC"],
                created_at=w.created_at.isoformat(),
                updated_at=w.updated_at.isoformat()
            )
            for w in wallets
        ]
    
    @staticmethod
    def get_wallet(db: Session, wallet_id: str, user_id: uuid.UUID) -> WalletResponse:
        """Получить кошелек по ID"""
        try:
            wallet_uuid = uuid.UUID(wallet_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID")
        
        wallet = db.query(Wallet).filter(
            Wallet.id == wallet_uuid,
            Wallet.user_id == user_id
        ).first()
        
        if not wallet:
            raise HTTPException(status_code=404, detail="Кошелек не найден")
        logger.info("Wallet: %s", wallet)
        wr = WalletResponse(
            id=str(wallet.id),
            address=wallet.address,
            chain=wallet.chain,
            label=wallet.label,
            tokens=list(wallet.tokens) if wallet.tokens else ["BTC", "ETH", "USDC"],
            created_at=wallet.created_at.isoformat(),
            updated_at=wallet.updated_at.isoformat()
        )
        logger.info("WalletResponse: %s", wr)
        return wr
    
    @staticmethod
    def create_wallet(db: Session, wallet: WalletCreate, user_id: uuid.UUID) -> WalletResponse:
        """Создать новый кошелек"""
        logger.info("Creating wallet: %s", wallet)
        # Проверяем, не существует ли уже кошелек с таким адресом у этого пользователя
        existing = db.query(Wallet).filter(
            Wallet.address == wallet.address,
            Wallet.user_id == user_id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Кошелек с таким адресом уже существует")
        
        db_wallet = Wallet(
            user_id=user_id,
            address=wallet.address,
            chain=wallet.chain,
            label=wallet.label,
            tokens=wallet.tokens or []
        )
        db.add(db_wallet)
        db.commit()
        db.refresh(db_wallet)
        
        return WalletResponse(
            id=str(db_wallet.id),
            address=db_wallet.address,
            chain=db_wallet.chain,
            label=db_wallet.label,
            tokens=db_wallet.tokens or [],
            created_at=db_wallet.created_at.isoformat(),
            updated_at=db_wallet.updated_at.isoformat()
        )
    
    @staticmethod
    def update_wallet(
        db: Session, 
        wallet_id: str, 
        wallet_update: WalletUpdate, 
        user_id: uuid.UUID
    ) -> WalletResponse:
        """Обновить кошелек"""
        try:
            wallet_uuid = uuid.UUID(wallet_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID")
        
        wallet = db.query(Wallet).filter(
            Wallet.id == wallet_uuid,
            Wallet.user_id == user_id
        ).first()
        
        if not wallet:
            raise HTTPException(status_code=404, detail="Кошелек не найден")
        
        if wallet_update.chain is not None:
            wallet.chain = wallet_update.chain
        if wallet_update.label is not None:
            wallet.label = wallet_update.label
        if wallet_update.tokens is not None:
            wallet.tokens = wallet_update.tokens
        
        db.commit()
        db.refresh(wallet)
        
        return WalletResponse(
            id=str(wallet.id),
            address=wallet.address,
            chain=wallet.chain,
            label=wallet.label,
            tokens=wallet.tokens or [],
            created_at=wallet.created_at.isoformat(),
            updated_at=wallet.updated_at.isoformat()
        )
    
    @staticmethod
    def delete_wallet(db: Session, wallet_id: str, user_id: uuid.UUID) -> None:
        """Удалить кошелек"""
        try:
            wallet_uuid = uuid.UUID(wallet_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID")
        
        wallet = db.query(Wallet).filter(
            Wallet.id == wallet_uuid,
            Wallet.user_id == user_id
        ).first()
        
        if not wallet:
            raise HTTPException(status_code=404, detail="Кошелек не найден")
        
        db.delete(wallet)
        db.commit()

