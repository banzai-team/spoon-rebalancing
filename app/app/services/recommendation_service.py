"""
Сервис для работы с рекомендациями
"""
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
import logging

from app.db.models import Recommendation, Strategy, StrategyWallet, Wallet
from app.api.schemas import RecommendationRequest, RecommendationResponse
from app.services.strategy_service import StrategyService

logger = logging.getLogger(__name__)


class RecommendationService:
    """Сервис для управления рекомендациями"""
    
    @staticmethod
    async def create_recommendation(
        db: Session,
        request: RecommendationRequest,
        user_id: uuid.UUID,
        get_agent_func
    ) -> RecommendationResponse:
        """Создать рекомендацию по ребалансировке для стратегии"""
        try:
            strategy_uuid = uuid.UUID(request.strategy_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID стратегии")
        
        strategy = db.query(Strategy).filter(
            Strategy.id == strategy_uuid,
            Strategy.user_id == user_id
        ).first()
        
        if not strategy:
            raise HTTPException(status_code=404, detail="Стратегия не найдена")
        
        # Получаем кошельки стратегии
        wallet_links = db.query(StrategyWallet).filter(StrategyWallet.strategy_id == strategy.id).all()
        wallet_ids = [sw.wallet_id for sw in wallet_links]
        
        # Собираем информацию о кошельках
        wallets = db.query(Wallet).filter(
            Wallet.id.in_(wallet_ids),
            Wallet.user_id == user_id
        ).all()
        
        if not wallets:
            raise HTTPException(status_code=400, detail="Нет доступных кошельков для стратегии")
        
        wallet_addresses = [w.address for w in wallets]
        tokens = set()
        chain = None
        for wallet in wallets:
            tokens.update(wallet.tokens or [])
            if chain is None:
                chain = wallet.chain
        
        # Настраиваем агента
        agent = get_agent_func()
        agent.set_min_profit(strategy.min_profit_threshold_usd)
        
        # Парсим описание стратегии для получения целевого распределения
        target_allocation = await StrategyService.parse_strategy_description(strategy.description)
        
        # Получаем рекомендацию
        logger.info(f"Создание рекомендации для стратегии {strategy.id} (user_id: {user_id})")
        result = await agent.check_rebalancing(
            wallets=wallet_addresses,
            tokens=list(tokens) if tokens else ["BTC", "ETH", "USDC"],
            target_allocation=target_allocation,
            chain=chain or "ethereum"
        )
        
        # Сохраняем рекомендацию в БД
        db_recommendation = Recommendation(
            user_id=user_id,
            strategy_id=strategy.id,
            recommendation=result.get("recommendation", ""),
            analysis=result
        )
        db.add(db_recommendation)
        db.commit()
        db.refresh(db_recommendation)
        logger.info(f"Рекомендация создана: {db_recommendation.id} для стратегии {strategy.id}")
        
        return RecommendationResponse(
            id=str(db_recommendation.id),
            strategy_id=str(db_recommendation.strategy_id),
            recommendation=db_recommendation.recommendation,
            analysis=db_recommendation.analysis,
            created_at=db_recommendation.created_at.isoformat()
        )
    
    @staticmethod
    def get_recommendation(
        db: Session,
        recommendation_id: str,
        user_id: uuid.UUID
    ) -> RecommendationResponse:
        """Получить конкретную рекомендацию по ID"""
        try:
            recommendation_uuid = uuid.UUID(recommendation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID")
        
        recommendation = db.query(Recommendation).filter(
            Recommendation.id == recommendation_uuid,
            Recommendation.user_id == user_id
        ).first()
        
        if not recommendation:
            raise HTTPException(status_code=404, detail="Рекомендация не найдена")
        
        return RecommendationResponse(
            id=str(recommendation.id),
            strategy_id=str(recommendation.strategy_id),
            recommendation=recommendation.recommendation,
            analysis=recommendation.analysis,
            created_at=recommendation.created_at.isoformat()
        )
    
    @staticmethod
    def get_recommendations(
        db: Session,
        user_id: uuid.UUID,
        strategy_id: Optional[str] = None,
        limit: int = 50
    ) -> List[RecommendationResponse]:
        """Получить историю рекомендаций пользователя"""
        query = db.query(Recommendation).filter(Recommendation.user_id == user_id)
        
        if strategy_id:
            try:
                strategy_uuid = uuid.UUID(strategy_id)
                query = query.filter(Recommendation.strategy_id == strategy_uuid)
            except ValueError:
                raise HTTPException(status_code=400, detail="Неверный формат ID стратегии")
        
        recommendations = query.order_by(Recommendation.created_at.desc()).limit(limit).all()
        
        return [
            RecommendationResponse(
                id=str(r.id),
                strategy_id=str(r.strategy_id),
                recommendation=r.recommendation,
                analysis=r.analysis,
                created_at=r.created_at.isoformat()
            )
            for r in recommendations
        ]

