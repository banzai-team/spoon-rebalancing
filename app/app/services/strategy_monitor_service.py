"""
Сервис для мониторинга стратегий и автоматической отправки рекомендаций в чат
"""
import asyncio
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db.models import Strategy, StrategyWallet, Wallet, ChatMessageDB
from app.services.strategy_service import StrategyService
from app.services.recommendation_service import RecommendationService
from app.services.agent_service import AgentService


class StrategyMonitorService:
    """Сервис для мониторинга стратегий"""
    
    _running = False
    _task: Optional[asyncio.Task] = None
    
    @classmethod
    async def start_monitoring(cls, db: Session, check_interval_seconds: int = 3600):
        """Запустить мониторинг стратегий"""
        if cls._running:
            return
        
        cls._running = True
        
        async def monitor_loop():
            while cls._running:
                try:
                    await cls.check_all_strategies(db)
                except Exception as e:
                    print(f"Ошибка при проверке стратегий: {e}")
                
                await asyncio.sleep(check_interval_seconds)
        
        cls._task = asyncio.create_task(monitor_loop())
        print(f"✅ Мониторинг стратегий запущен (интервал: {check_interval_seconds} сек)")
    
    @classmethod
    async def start_monitoring_async(cls, check_interval_seconds: int = 3600):
        """Запустить мониторинг стратегий с автоматическим получением сессии БД"""
        if cls._running:
            return
        
        cls._running = True
        
        async def monitor_loop():
            from app.db import get_db
            while cls._running:
                try:
                    db = next(get_db())
                    try:
                        await cls.check_all_strategies(db)
                    finally:
                        db.close()
                except Exception as e:
                    print(f"Ошибка при проверке стратегий: {e}")
                
                await asyncio.sleep(check_interval_seconds)
        
        cls._task = asyncio.create_task(monitor_loop())
        print(f"✅ Мониторинг стратегий запущен (интервал: {check_interval_seconds} сек)")
    
    @classmethod
    async def stop_monitoring(cls):
        """Остановить мониторинг стратегий"""
        cls._running = False
        if cls._task:
            cls._task.cancel()
            try:
                await cls._task
            except asyncio.CancelledError:
                pass
        print("⏹️  Мониторинг стратегий остановлен")
    
    @staticmethod
    async def check_all_strategies(db: Session):
        """Проверить все стратегии и отправить рекомендации в чат"""
        strategies = db.query(Strategy).all()
        
        for strategy in strategies:
            try:
                await StrategyMonitorService.check_strategy(db, strategy)
            except Exception as e:
                print(f"Ошибка при проверке стратегии {strategy.id}: {e}")
    
    @staticmethod
    async def check_strategy(db: Session, strategy: Strategy):
        """Проверить конкретную стратегию и отправить рекомендацию в чат"""
        # Проверяем, когда последний раз проверялась стратегия
        # Получаем последнее сообщение в чате для этой стратегии
        last_message = db.query(ChatMessageDB).filter(
            ChatMessageDB.strategy_id == strategy.id,
            ChatMessageDB.user_id == strategy.user_id
        ).order_by(ChatMessageDB.created_at.desc()).first()
        
        # Если последнее сообщение было менее часа назад, пропускаем
        if last_message is not None:
            last_created_at = last_message.created_at
            if isinstance(last_created_at, datetime):
                time_since_last = datetime.utcnow() - last_created_at
                if time_since_last < timedelta(hours=1):
                    return
        
        # Получаем кошельки стратегии
        wallet_links = db.query(StrategyWallet).filter(
            StrategyWallet.strategy_id == strategy.id
        ).all()
        
        if len(wallet_links) == 0:
            return  # Нет кошельков для проверки
        
        wallet_ids = [sw.wallet_id for sw in wallet_links]
        wallets = db.query(Wallet).filter(
            Wallet.id.in_(wallet_ids),
            Wallet.user_id == strategy.user_id
        ).all()
        
        if not wallets:
            return
        
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
        target_allocation = await StrategyService.parse_strategy_description(strategy_description)
        
        # Получаем рекомендацию
        result = await agent.check_rebalancing(
            wallets=wallet_addresses,
            tokens=list(tokens) if tokens else ["BTC", "ETH", "USDC"],
            target_allocation=target_allocation,
            chain=chain or "ethereum"
        )
        
        recommendation_text = result.get("recommendation", "")
        
        # Если есть рекомендация, отправляем её в чат
        if recommendation_text and len(recommendation_text.strip()) > 0:
            # Формируем сообщение от агента
            agent_message = f"""
📊 Автоматическая проверка портфеля для стратегии "{strategy.name}"

{recommendation_text}

---
*Это автоматическое сообщение. Вы можете ответить, чтобы обновить стратегию или задать вопросы.*
"""
            
            # Сохраняем сообщение в чат
            chat_message = ChatMessageDB(
                user_id=strategy.user_id,
                user_message="",  # Пустое, так как это сообщение от агента
                agent_response=agent_message,
                strategy_id=strategy.id,
                wallet_ids=[str(wid) for wid in wallet_ids]
            )
            db.add(chat_message)
            db.commit()
            
            print(f"✅ Отправлена рекомендация для стратегии {strategy.id}")

