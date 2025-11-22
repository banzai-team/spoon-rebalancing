"""
Сервис для работы со стратегиями
"""
import uuid
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.models import Strategy, Wallet, StrategyWallet
from app.api.schemas import StrategyCreate, StrategyUpdate, StrategyResponse


class StrategyService:
    """Сервис для управления стратегиями"""
    
    @staticmethod
    async def parse_strategy_description(description: str) -> Dict[str, float]:
        """Парсит текстовое описание стратегии в целевое распределение"""
        from app.agents.portfolio_rebalancer_agent import PortfolioRebalancerAgent
        from spoon_ai.chat import ChatBot
        import os
        
        agent = PortfolioRebalancerAgent(
            llm=ChatBot(
                llm_provider=os.getenv("LLM_PROVIDER", "openrouter"),
                model_name=os.getenv("LLM_MODEL", "x-ai/grok-4.1-fast:free")
            )
        )
        
        prompt = f"""
        The user described their desired portfolio allocation as follows:
        "{description}"
        
        Extract the target allocation percentages for each token from this description.
        Return the result in JSON format, where keys are token symbols (BTC, ETH, USDC, etc.),
        and values are percentages (numbers from 0 to 100).
        
        Example response:
        {{"BTC": 40.0, "ETH": 35.0, "USDC": 25.0}}
        
        Return only JSON, without additional comments.
        """
        
        response = await agent.run(prompt)
        
        # Пытаемся извлечь JSON из ответа
        import json
        import re
        
        # Ищем JSON в ответе
        json_match = re.search(r'\{[^}]+\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Если не нашли, пытаемся распарсить весь ответ
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail=f"Не удалось распарсить описание стратегии. Ответ агента: {response}"
            )
    
    @staticmethod
    def get_strategies(db: Session, user_id: uuid.UUID) -> List[StrategyResponse]:
        """Получить список всех стратегий пользователя"""
        strategies = db.query(Strategy).filter(Strategy.user_id == user_id).all()
        result = []
        for s in strategies:
            wallet_links = db.query(StrategyWallet).filter(StrategyWallet.strategy_id == s.id).all()
            wallet_ids = [str(sw.wallet_id) for sw in wallet_links]
            result.append(StrategyResponse(
                id=str(s.id),
                name=s.name,
                description=s.description,
                wallet_ids=wallet_ids,
                created_at=s.created_at.isoformat(),
                updated_at=s.updated_at.isoformat()
            ))
        return result
    
    @staticmethod
    def get_strategy(db: Session, strategy_id: str, user_id: uuid.UUID) -> StrategyResponse:
        """Получить стратегию по ID"""
        try:
            strategy_uuid = uuid.UUID(strategy_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID")
        
        strategy = db.query(Strategy).filter(
            Strategy.id == strategy_uuid,
            Strategy.user_id == user_id
        ).first()
        
        if not strategy:
            raise HTTPException(status_code=404, detail="Стратегия не найдена")
        
        wallet_links = db.query(StrategyWallet).filter(StrategyWallet.strategy_id == strategy.id).all()
        wallet_ids = [str(sw.wallet_id) for sw in wallet_links]
        
        return StrategyResponse(
            id=str(strategy.id),
            name=strategy.name,
            description=strategy.description,
            wallet_ids=wallet_ids,
            created_at=strategy.created_at.isoformat(),
            updated_at=strategy.updated_at.isoformat()
        )
    
    @staticmethod
    async def create_strategy(
        db: Session,
        strategy: StrategyCreate,
        user_id: uuid.UUID
    ) -> StrategyResponse:
        """Создать новую стратегию"""
        # Проверяем существование кошельков пользователя
        wallet_uuids = []
        for wallet_id in strategy.wallet_ids:
            try:
                wallet_uuid = uuid.UUID(wallet_id)
                wallet = db.query(Wallet).filter(
                    Wallet.id == wallet_uuid,
                    Wallet.user_id == user_id
                ).first()
                if not wallet:
                    raise HTTPException(status_code=404, detail=f"Кошелек {wallet_id} не найден")
                wallet_uuids.append(wallet_uuid)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Неверный формат ID кошелька: {wallet_id}")
        
        # Создаем стратегию
        db_strategy = Strategy(
            user_id=user_id,
            name=strategy.name,
            description=strategy.description,
        )
        db.add(db_strategy)
        db.commit()
        db.refresh(db_strategy)
        
        # Создаем связи с кошельками
        for wallet_uuid in wallet_uuids:
            link = StrategyWallet(strategy_id=db_strategy.id, wallet_id=wallet_uuid)
            db.add(link)
        db.commit()
        
        return StrategyResponse(
            id=str(db_strategy.id),
            name=db_strategy.name,
            description=db_strategy.description,
            wallet_ids=strategy.wallet_ids,
            created_at=db_strategy.created_at.isoformat(),
            updated_at=db_strategy.updated_at.isoformat()
        )
    
    @staticmethod
    async def update_strategy(
        db: Session,
        strategy_id: str,
        strategy_update: StrategyUpdate,
        user_id: uuid.UUID
    ) -> StrategyResponse:
        """Обновить стратегию"""
        try:
            strategy_uuid = uuid.UUID(strategy_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID")
        
        strategy = db.query(Strategy).filter(
            Strategy.id == strategy_uuid,
            Strategy.user_id == user_id
        ).first()
        
        if not strategy:
            raise HTTPException(status_code=404, detail="Стратегия не найдена")
        
        if strategy_update.name is not None:
            strategy.name = strategy_update.name
        if strategy_update.description is not None:
            strategy.description = strategy_update.description
        if strategy_update.wallet_ids is not None:
            # Удаляем старые связи
            db.query(StrategyWallet).filter(StrategyWallet.strategy_id == strategy.id).delete()
            # Проверяем и создаем новые связи
            wallet_uuids = []
            for wallet_id in strategy_update.wallet_ids:
                try:
                    wallet_uuid = uuid.UUID(wallet_id)
                    wallet = db.query(Wallet).filter(
                        Wallet.id == wallet_uuid,
                        Wallet.user_id == user_id
                    ).first()
                    if not wallet:
                        raise HTTPException(status_code=404, detail=f"Кошелек {wallet_id} не найден")
                    wallet_uuids.append(wallet_uuid)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Неверный формат ID кошелька: {wallet_id}")
            
            for wallet_uuid in wallet_uuids:
                link = StrategyWallet(strategy_id=strategy.id, wallet_id=wallet_uuid)
                db.add(link)
        
        db.commit()
        db.refresh(strategy)
        
        wallet_links = db.query(StrategyWallet).filter(StrategyWallet.strategy_id == strategy.id).all()
        wallet_ids = [str(sw.wallet_id) for sw in wallet_links]
        
        return StrategyResponse(
            id=str(strategy.id),
            name=strategy.name,
            description=strategy.description,
            wallet_ids=wallet_ids,
            created_at=strategy.created_at.isoformat(),
            updated_at=strategy.updated_at.isoformat()
        )
    
    @staticmethod
    def delete_strategy(db: Session, strategy_id: str, user_id: uuid.UUID) -> None:
        """Удалить стратегию"""
        try:
            strategy_uuid = uuid.UUID(strategy_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID")
        
        strategy = db.query(Strategy).filter(
            Strategy.id == strategy_uuid,
            Strategy.user_id == user_id
        ).first()
        
        if not strategy:
            raise HTTPException(status_code=404, detail="Стратегия не найдена")
        
        db.delete(strategy)
        db.commit()

