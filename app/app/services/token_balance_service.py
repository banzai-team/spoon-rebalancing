"""
Сервис для работы с балансами токенов в кошельках
"""
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.models import WalletTokenBalance, Wallet
from app.api.schemas import (
    WalletTokenBalanceCreate,
    WalletTokenBalanceUpdate,
    WalletTokenBalanceResponse
)


class TokenBalanceService:
    """Сервис для управления балансами токенов"""
    
    @staticmethod
    def get_balances(
        db: Session,
        user_id: uuid.UUID,
        wallet_id: Optional[str] = None
    ) -> List[WalletTokenBalanceResponse]:
        """Получить список балансов токенов пользователя"""
        query = db.query(WalletTokenBalance).filter(WalletTokenBalance.user_id == user_id)
        
        if wallet_id:
            try:
                wallet_uuid = uuid.UUID(wallet_id)
                query = query.filter(WalletTokenBalance.wallet_id == wallet_uuid)
            except ValueError:
                raise HTTPException(status_code=400, detail="Неверный формат ID кошелька")
        
        balances = query.all()
        
        return [
            WalletTokenBalanceResponse(
                id=str(b.id),
                wallet_id=str(b.wallet_id),
                user_id=str(b.user_id),
                token_symbol=b.token_symbol,
                balance=b.balance,
                balance_usd=b.balance_usd,
                chain=b.chain,
                created_at=b.created_at.isoformat(),
                updated_at=b.updated_at.isoformat()
            )
            for b in balances
        ]
    
    @staticmethod
    def get_balance(
        db: Session,
        balance_id: str,
        user_id: uuid.UUID
    ) -> WalletTokenBalanceResponse:
        """Получить баланс токена по ID"""
        try:
            balance_uuid = uuid.UUID(balance_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID")
        
        balance = db.query(WalletTokenBalance).filter(
            WalletTokenBalance.id == balance_uuid,
            WalletTokenBalance.user_id == user_id
        ).first()
        
        if not balance:
            raise HTTPException(status_code=404, detail="Баланс токена не найден")
        
        return WalletTokenBalanceResponse(
            id=str(balance.id),
            wallet_id=str(balance.wallet_id),
            user_id=str(balance.user_id),
            token_symbol=balance.token_symbol,
            balance=balance.balance,
            balance_usd=balance.balance_usd,
            chain=balance.chain,
            created_at=balance.created_at.isoformat(),
            updated_at=balance.updated_at.isoformat()
        )
    
    @staticmethod
    def create_balance(
        db: Session,
        balance: WalletTokenBalanceCreate,
        user_id: uuid.UUID
    ) -> WalletTokenBalanceResponse:
        """Создать или обновить запись о балансе токена"""
        try:
            wallet_uuid = uuid.UUID(balance.wallet_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID кошелька")
        
        # Проверяем, что кошелек принадлежит пользователю
        wallet = db.query(Wallet).filter(
            Wallet.id == wallet_uuid,
            Wallet.user_id == user_id
        ).first()
        
        if not wallet:
            raise HTTPException(status_code=404, detail="Кошелек не найден")
        
        # Проверяем, существует ли уже запись для этого кошелька и токена
        existing = db.query(WalletTokenBalance).filter(
            WalletTokenBalance.wallet_id == wallet_uuid,
            WalletTokenBalance.token_symbol == balance.token_symbol,
            WalletTokenBalance.user_id == user_id
        ).first()
        
        if existing:
            # Обновляем существующую запись
            existing.balance = balance.balance
            existing.balance_usd = balance.balance_usd
            existing.chain = balance.chain
            db.commit()
            db.refresh(existing)
            
            return WalletTokenBalanceResponse(
                id=str(existing.id),
                wallet_id=str(existing.wallet_id),
                user_id=str(existing.user_id),
                token_symbol=existing.token_symbol,
                balance=existing.balance,
                balance_usd=existing.balance_usd,
                chain=existing.chain,
                created_at=existing.created_at.isoformat(),
                updated_at=existing.updated_at.isoformat()
            )
        else:
            # Создаем новую запись
            db_balance = WalletTokenBalance(
                wallet_id=wallet_uuid,
                user_id=user_id,
                token_symbol=balance.token_symbol,
                balance=balance.balance,
                balance_usd=balance.balance_usd,
                chain=balance.chain
            )
            db.add(db_balance)
            db.commit()
            db.refresh(db_balance)
            
            return WalletTokenBalanceResponse(
                id=str(db_balance.id),
                wallet_id=str(db_balance.wallet_id),
                user_id=str(db_balance.user_id),
                token_symbol=db_balance.token_symbol,
                balance=db_balance.balance,
                balance_usd=db_balance.balance_usd,
                chain=db_balance.chain,
                created_at=db_balance.created_at.isoformat(),
                updated_at=db_balance.updated_at.isoformat()
            )
    
    @staticmethod
    def update_balance(
        db: Session,
        balance_id: str,
        balance_update: WalletTokenBalanceUpdate,
        user_id: uuid.UUID
    ) -> WalletTokenBalanceResponse:
        """Обновить баланс токена"""
        try:
            balance_uuid = uuid.UUID(balance_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID")
        
        balance = db.query(WalletTokenBalance).filter(
            WalletTokenBalance.id == balance_uuid,
            WalletTokenBalance.user_id == user_id
        ).first()
        
        if not balance:
            raise HTTPException(status_code=404, detail="Баланс токена не найден")
        
        if balance_update.balance is not None:
            balance.balance = balance_update.balance
        if balance_update.balance_usd is not None:
            balance.balance_usd = balance_update.balance_usd
        
        db.commit()
        db.refresh(balance)
        
        return WalletTokenBalanceResponse(
            id=str(balance.id),
            wallet_id=str(balance.wallet_id),
            user_id=str(balance.user_id),
            token_symbol=balance.token_symbol,
            balance=balance.balance,
            balance_usd=balance.balance_usd,
            chain=balance.chain,
            created_at=balance.created_at.isoformat(),
            updated_at=balance.updated_at.isoformat()
        )
    
    @staticmethod
    def delete_balance(db: Session, balance_id: str, user_id: uuid.UUID) -> None:
        """Удалить запись о балансе токена"""
        try:
            balance_uuid = uuid.UUID(balance_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID")
        
        balance = db.query(WalletTokenBalance).filter(
            WalletTokenBalance.id == balance_uuid,
            WalletTokenBalance.user_id == user_id
        ).first()
        
        if not balance:
            raise HTTPException(status_code=404, detail="Баланс токена не найден")
        
        db.delete(balance)
        db.commit()

