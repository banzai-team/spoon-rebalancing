"""
Сервис для работы с агентом
"""
import os
from typing import Optional
from sqlalchemy.orm import Session

from app.agents.portfolio_rebalancer_agent import PortfolioRebalancerAgent
from spoon_ai.chat import ChatBot
from app.db.models import Wallet, Strategy, Recommendation, ChatMessageDB


class AgentService:
    """Сервис для управления агентом"""
    
    _agent: Optional[PortfolioRebalancerAgent] = None
    
    @classmethod
    def get_agent(cls) -> PortfolioRebalancerAgent:
        """Получает или создает экземпляр агента"""
        if cls._agent is None:
            cls._agent = PortfolioRebalancerAgent(
                llm=ChatBot(
                    llm_provider=os.getenv("LLM_PROVIDER", "openrouter"),
                    model_name=os.getenv("LLM_MODEL", "qwen/qwen3-coder:free")
                )
            )
        return cls._agent
    
    @staticmethod
    def get_agent_status(db: Session, user_id) -> dict:
        """Получить текущий статус и конфигурацию агента"""
        try:
            agent = AgentService.get_agent()
            wallets_count = db.query(Wallet).filter(Wallet.user_id == user_id).count()
            strategies_count = db.query(Strategy).filter(Strategy.user_id == user_id).count()
            recommendations_count = db.query(Recommendation).filter(Recommendation.user_id == user_id).count()
            chat_messages_count = db.query(ChatMessageDB).filter(ChatMessageDB.user_id == user_id).count()
            
            return {
                "success": True,
                "status": {
                    "mode": agent.mode,
                    "min_profit_threshold_usd": agent.min_profit_threshold_usd,
                    "target_allocation": agent.target_allocation,
                    "max_steps": agent.max_steps
                },
                "statistics": {
                    "wallets_count": wallets_count,
                    "strategies_count": strategies_count,
                    "recommendations_count": recommendations_count,
                    "chat_messages_count": chat_messages_count
                }
            }
        except Exception as e:
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Ошибка при получении статуса: {str(e)}")
    
    @staticmethod
    def configure_agent(mode: Optional[str] = None, 
                       min_profit_threshold_usd: Optional[float] = None) -> dict:
        """Настроить параметры агента"""
        try:
            agent = AgentService.get_agent()
            
            if mode:
                agent.set_mode(mode)
            if min_profit_threshold_usd is not None:
                agent.set_min_profit(min_profit_threshold_usd)
            
            return {
                "success": True,
                "config": {
                    "mode": agent.mode,
                    "min_profit_threshold_usd": agent.min_profit_threshold_usd
                }
            }
        except Exception as e:
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Ошибка при настройке агента: {str(e)}")

