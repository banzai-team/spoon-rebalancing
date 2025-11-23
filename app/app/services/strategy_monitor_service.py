"""
Сервис для мониторинга стратегий и автоматического создания рекомендаций
"""
import asyncio
import logging
import uuid
from typing import Optional, Dict
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db.models import Strategy, StrategyWallet, Wallet, Recommendation
from app.services.strategy_service import StrategyService
from app.services.recommendation_service import RecommendationService
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)

# Интервал проверки стратегии (10 минут)
CHECK_INTERVAL_SECONDS = 600


class StrategyMonitorService:
    """Сервис для мониторинга стратегий"""
    
    _running = False
    _tasks: Dict[uuid.UUID, asyncio.Task] = {}  # Словарь задач для каждой стратегии
    
    @classmethod
    async def start_monitoring_async(cls):
        """Запустить мониторинг стратегий с автоматическим получением сессии БД"""
        if cls._running:
            return
        
        cls._running = True
        
        # Загружаем все стратегии и планируем проверки
        from app.db import get_db
        db = next(get_db())
        try:
            strategies = db.query(Strategy).all()
            logger.info(f"Найдено {len(strategies)} стратегий для мониторинга")
            
            for strategy in strategies:
                await cls.schedule_strategy_check(strategy.id)
        finally:
            db.close()
        
        logger.info(f"✅ Мониторинг стратегий запущен (интервал: {CHECK_INTERVAL_SECONDS} сек для каждой стратегии)")
    
    @classmethod
    async def schedule_strategy_check(cls, strategy_id: uuid.UUID):
        """Планирует проверку стратегии на основе last_checked_at"""
        # Отменяем существующую задачу, если есть
        if strategy_id in cls._tasks:
            cls._tasks[strategy_id].cancel()
            try:
                await cls._tasks[strategy_id]
            except asyncio.CancelledError:
                pass
        
        async def strategy_monitor_loop():
            from app.db import get_db
            while cls._running:
                try:
                    db = next(get_db())
                    try:
                        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
                        if not strategy:
                            logger.warning(f"Стратегия {strategy_id} не найдена, останавливаем мониторинг")
                            break
                        
                        # Проверяем, нужно ли выполнить проверку сейчас
                        now = datetime.utcnow()
                        sleep_time = CHECK_INTERVAL_SECONDS
                        
                        if strategy.last_checked_at is None:
                            # Если никогда не проверялась, проверяем сразу
                            await cls.check_strategy(db, strategy)
                            # Обновляем дату последней проверки
                            strategy.last_checked_at = now
                            db.commit()
                            logger.debug(f"Стратегия {strategy_id}: проверка выполнена, следующая через {CHECK_INTERVAL_SECONDS} сек")
                        else:
                            # Проверяем, прошло ли 10 минут с последней проверки
                            time_since_last = now - strategy.last_checked_at
                            if time_since_last >= timedelta(seconds=CHECK_INTERVAL_SECONDS):
                                # Время пришло, выполняем проверку
                                await cls.check_strategy(db, strategy)
                                # Обновляем дату последней проверки
                                strategy.last_checked_at = now
                                db.commit()
                                logger.debug(f"Стратегия {strategy_id}: проверка выполнена, следующая через {CHECK_INTERVAL_SECONDS} сек")
                            else:
                                # Вычисляем время до следующей проверки
                                time_until_next = timedelta(seconds=CHECK_INTERVAL_SECONDS) - time_since_last
                                sleep_time = int(time_until_next.total_seconds())
                                logger.debug(f"Стратегия {strategy_id}: следующая проверка через {sleep_time} сек")
                    finally:
                        db.close()
                except Exception as e:
                    logger.error(f"Ошибка при проверке стратегии {strategy_id}: {e}", exc_info=True)
                
                # Ждем до следующей проверки
                await asyncio.sleep(sleep_time)
        
        cls._tasks[strategy_id] = asyncio.create_task(strategy_monitor_loop())
        logger.debug(f"Запланирована проверка стратегии {strategy_id}")
    
    @classmethod
    async def stop_monitoring(cls):
        """Остановить мониторинг стратегий"""
        cls._running = False
        for strategy_id, task in cls._tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        cls._tasks.clear()
        logger.info("⏹️  Мониторинг стратегий остановлен")
    
    @classmethod
    async def add_strategy_monitoring(cls, strategy_id: uuid.UUID):
        """Добавить стратегию в мониторинг (вызывается при создании стратегии)"""
        if cls._running:
            await cls.schedule_strategy_check(strategy_id)
    
    @classmethod
    async def remove_strategy_monitoring(cls, strategy_id: uuid.UUID):
        """Удалить стратегию из мониторинга (вызывается при удалении стратегии)"""
        if strategy_id in cls._tasks:
            cls._tasks[strategy_id].cancel()
            try:
                await cls._tasks[strategy_id]
            except asyncio.CancelledError:
                pass
            del cls._tasks[strategy_id]
            logger.debug(f"Мониторинг стратегии {strategy_id} остановлен")
    
    @staticmethod
    async def check_strategy(db: Session, strategy: Strategy):
        """Проверить конкретную стратегию и создать рекомендацию"""
        
        # Получаем кошельки стратегии
        wallet_links = db.query(StrategyWallet).filter(
            StrategyWallet.strategy_id == strategy.id
        ).all()
        
        if len(wallet_links) == 0:
            logger.debug(f"Стратегия {strategy.id}: нет кошельков для проверки")
            return  # Нет кошельков для проверки
        
        wallet_ids = [sw.wallet_id for sw in wallet_links]
        wallets = db.query(Wallet).filter(
            Wallet.id.in_(wallet_ids),
            Wallet.user_id == strategy.user_id
        ).all()
        
        if not wallets:
            logger.debug(f"Стратегия {strategy.id}: кошельки не найдены")
            return
        
        logger.info(f"Проверка стратегии {strategy.id}: найдено {len(wallets)} кошельков")
        
        wallet_addresses = [str(w.address) for w in wallets]
        tokens = set()
        chain: Optional[str] = None
        for wallet in wallets:
            wallet_tokens = wallet.tokens
            if wallet_tokens is not None and isinstance(wallet_tokens, list):
                tokens.update(wallet_tokens)
            if chain is None:
                chain = str(wallet.chain)
        
        # Получаем агента
        agent = AgentService.get_agent()
        
        # Парсим описание стратегии для получения целевого распределения
        strategy_description = str(strategy.description)
        logger.debug(f"Проверка стратегии {strategy.id}: парсинг описания")
        target_allocation = await StrategyService.parse_strategy_description(strategy_description)
        
        # Получаем рекомендацию
        logger.debug(f"Проверка стратегии {strategy.id}: получение рекомендации от агента")
        result = await agent.check_rebalancing(
            wallets=wallet_addresses,
            tokens=list(tokens) if tokens else ["BTC", "ETH", "USDC"],
            target_allocation=target_allocation,
            chain=chain or "ethereum"
        )
        
        recommendation_text = result.get("recommendation", "")
        
        # Если есть рекомендация, создаем Recommendation
        if recommendation_text and len(recommendation_text.strip()) > 0:
            # Формируем текст рекомендации с контекстом
            formatted_recommendation = f"""📊 Автоматическая проверка портфеля для стратегии "{strategy.name}"

{recommendation_text}

---
*Это автоматическая рекомендация, создана {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC*
"""
            
            # Создаем рекомендацию в БД
            recommendation = Recommendation(
                user_id=strategy.user_id,
                strategy_id=strategy.id,
                recommendation=formatted_recommendation,
                analysis=result  # Сохраняем весь результат анализа
            )
            db.add(recommendation)
            db.commit()
            db.refresh(recommendation)
            
            logger.info(f"✅ Создана рекомендация {recommendation.id} для стратегии {strategy.id} (user_id: {strategy.user_id})")
        else:
            logger.debug(f"Стратегия {strategy.id}: рекомендация пуста, не создаем запись")

