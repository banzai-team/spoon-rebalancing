"""
Сервис для работы со стратегиями
"""
import uuid
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
import logging

from app.db.models import Strategy, Wallet, StrategyWallet
from app.api.schemas import StrategyCreate, StrategyUpdate, StrategyResponse

logger = logging.getLogger(__name__)


class StrategyService:
    """Сервис для управления стратегиями"""
    
    @staticmethod
    async def parse_strategy_description(description: str) -> Dict[str, float]:
        """Парсит текстовое описание стратегии в целевое распределение"""
        from app.agents.portfolio_rebalancer_agent import PortfolioRebalancerAgent
        from spoon_ai.chat import ChatBot
        import os
        import json
        import re
        
        if not description or not description.strip():
            logger.warning("Пустое описание стратегии, используем дефолтные значения")
            return {"BTC": 40.0, "ETH": 35.0, "USDC": 25.0}
        
        agent = PortfolioRebalancerAgent(
            llm=ChatBot(
                llm_provider=os.getenv("LLM_PROVIDER", "openrouter"),
                model_name=os.getenv("LLM_MODEL", "x-ai/grok-4.1-fast:free")
            )
        )
        
        prompt = f"""Extract target portfolio allocation percentages from this description:

"{description}"

CRITICAL REQUIREMENTS:
1. You MUST return ONLY valid JSON, no other text
2. Format: {{"TOKEN": percentage, ...}} where percentage is 0-100
3. Token symbols should be standard: BTC, ETH, USDC, USDT, WBTC, etc.
4. If description is unclear, use reasonable defaults based on risk tolerance mentioned
5. Percentages should sum to approximately 100

Examples:
- "40% BTC, 35% ETH, 25% USDC" -> {{"BTC": 40.0, "ETH": 35.0, "USDC": 25.0}}
- "conservative" -> {{"BTC": 30.0, "ETH": 20.0, "USDC": 50.0}}
- "aggressive" -> {{"BTC": 50.0, "ETH": 40.0, "USDC": 10.0}}

Return ONLY the JSON object, nothing else."""
        
        try:
            response = await agent.run(prompt)
            
            if not response or not response.strip():
                logger.warning("Пустой ответ от агента, используем дефолтные значения")
                return {"BTC": 40.0, "ETH": 35.0, "USDC": 25.0}
            
            # Очищаем ответ от возможных markdown блоков
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            # Ищем JSON объект в ответе (поддерживаем многострочные JSON)
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            json_matches = re.findall(json_pattern, response, re.DOTALL)
            
            for json_str in json_matches:
                try:
                    parsed = json.loads(json_str)
                    if isinstance(parsed, dict) and parsed:
                        # Валидируем результат
                        validated = {}
                        total = 0.0
                        for token, value in parsed.items():
                            try:
                                percentage = float(value)
                                if 0 <= percentage <= 100:
                                    validated[str(token).upper()] = percentage
                                    total += percentage
                            except (ValueError, TypeError):
                                continue
                        
                        if validated:
                            # Нормализуем проценты, если сумма не равна 100
                            if total > 0 and abs(total - 100) > 1:
                                logger.debug(f"Сумма процентов {total}%, нормализуем до 100%")
                                validated = {k: (v / total) * 100 for k, v in validated.items()}
                            
                            logger.info(f"Успешно распарсено распределение: {validated}")
                            return validated
                except json.JSONDecodeError:
                    continue
            
            # Если не нашли JSON, пытаемся распарсить весь ответ
            try:
                parsed = json.loads(response)
                if isinstance(parsed, dict) and parsed:
                    return parsed
            except json.JSONDecodeError:
                pass
            
            # Если ничего не получилось, логируем и возвращаем дефолтные значения
            logger.warning(f"Не удалось распарсить описание стратегии. Ответ агента: {response[:200]}")
            logger.info("Используем дефолтное распределение: 40% BTC, 35% ETH, 25% USDC")
            return {"BTC": 40.0, "ETH": 35.0, "USDC": 25.0}
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге описания стратегии: {e}", exc_info=True)
            # Вместо исключения возвращаем дефолтные значения
            logger.info("Используем дефолтное распределение из-за ошибки")
            return {"BTC": 40.0, "ETH": 35.0, "USDC": 25.0}
    
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
        logger.info(f"Стратегия создана: {db_strategy.id} (name: {strategy.name}, user_id: {user_id})")
        
        # Создаем связи с кошельками
        for wallet_uuid in wallet_uuids:
            link = StrategyWallet(strategy_id=db_strategy.id, wallet_id=wallet_uuid)
            db.add(link)
        db.commit()
        if wallet_uuids:
            logger.debug(f"Стратегия {db_strategy.id} связана с {len(wallet_uuids)} кошельками")
        
        # Запускаем мониторинг стратегии
        from app.services.strategy_monitor_service import StrategyMonitorService
        await StrategyMonitorService.add_strategy_monitoring(db_strategy.id)
        logger.debug(f"Мониторинг стратегии {db_strategy.id} запущен")
        
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
    async def delete_strategy(db: Session, strategy_id: str, user_id: uuid.UUID) -> None:
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
        
        # Останавливаем мониторинг стратегии
        from app.services.strategy_monitor_service import StrategyMonitorService
        await StrategyMonitorService.remove_strategy_monitoring(strategy_uuid)
        
        db.delete(strategy)
        db.commit()

