"""
REST API сервер для агента ребалансировки портфеля
"""
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from portfolio_rebalancer_agent import PortfolioRebalancerAgent
from spoon_ai.chat import ChatBot
import uvicorn
import os


# Модели данных для API
class WalletRequest(BaseModel):
    wallets: List[str] = Field(..., description="Список адресов кошельков")
    tokens: List[str] = Field(..., description="Список токенов для отслеживания")
    chain: str = Field(default="ethereum", description="Блокчейн (ethereum, arbitrum, polygon)")


class TargetAllocation(BaseModel):
    allocation: Dict[str, float] = Field(..., description="Целевое распределение в процентах (например, {'BTC': 40, 'ETH': 35, 'USDC': 25})")


class RebalancingRequest(BaseModel):
    wallets: List[str] = Field(..., description="Список адресов кошельков")
    tokens: List[str] = Field(..., description="Список токенов для отслеживания")
    target_allocation: Dict[str, float] = Field(..., description="Целевое распределение в процентах")
    chain: str = Field(default="ethereum", description="Блокчейн")
    threshold_percent: float = Field(default=5.0, description="Порог отклонения в процентах")
    min_profit_threshold_usd: float = Field(default=50.0, description="Минимальная прибыль в USD для выполнения")


class AgentConfigRequest(BaseModel):
    mode: str = Field(default="consultation", description="Режим работы: 'consultation' или 'autonomous'")
    threshold_percent: Optional[float] = Field(default=None, description="Порог отклонения в процентах")
    min_profit_threshold_usd: Optional[float] = Field(default=None, description="Минимальная прибыль в USD")


class ChatRequest(BaseModel):
    message: str = Field(..., description="Сообщение для агента")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Дополнительный контекст")


# Инициализация FastAPI приложения
app = FastAPI(
    title="Portfolio Rebalancer API",
    description="REST API для агента автоматической ребалансировки криптопортфеля",
    version="1.0.0"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальный экземпляр агента
agent: Optional[PortfolioRebalancerAgent] = None


def get_agent() -> PortfolioRebalancerAgent:
    """Получает или создает экземпляр агента"""
    global agent
    if agent is None:
        agent = PortfolioRebalancerAgent(
            llm=ChatBot(
                llm_provider=os.getenv("LLM_PROVIDER", "openrouter"),
                model_name=os.getenv("LLM_MODEL", "x-ai/grok-4.1-fast:free")
            )
        )
    return agent


@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    print("🚀 Запуск API сервера ребалансировки портфеля...")
    get_agent()
    print("✅ Агент инициализирован")


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "service": "Portfolio Rebalancer API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "GET /health": "Проверка здоровья сервиса",
            "GET /portfolio/analyze": "Анализ текущего состояния портфеля",
            "POST /portfolio/rebalance": "Проверка и предложение ребалансировки",
            "POST /agent/configure": "Настройка параметров агента",
            "POST /agent/chat": "Чат с агентом"
        }
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    try:
        agent = get_agent()
        return {
            "status": "healthy",
            "agent_initialized": agent is not None,
            "mode": agent.mode if agent else None
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.post("/portfolio/analyze")
async def analyze_portfolio(request: WalletRequest):
    """Анализирует текущее состояние портфеля"""
    try:
        agent = get_agent()
        result = await agent.analyze_portfolio(
            wallets=request.wallets,
            tokens=request.tokens,
            chain=request.chain
        )
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при анализе портфеля: {str(e)}")


@app.post("/portfolio/rebalance")
async def check_rebalancing(request: RebalancingRequest):
    """Проверяет необходимость ребалансировки и предлагает действия"""
    try:
        agent = get_agent()
        
        # Настраиваем параметры агента
        if request.threshold_percent:
            agent.set_threshold(request.threshold_percent)
        if request.min_profit_threshold_usd:
            agent.set_min_profit(request.min_profit_threshold_usd)
        
        result = await agent.check_rebalancing(
            wallets=request.wallets,
            tokens=request.tokens,
            target_allocation=request.target_allocation,
            chain=request.chain
        )
        
        return {
            "success": True,
            "data": result,
            "config": {
                "mode": agent.mode,
                "threshold_percent": agent.threshold_percent,
                "min_profit_threshold_usd": agent.min_profit_threshold_usd
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при проверке ребалансировки: {str(e)}")


@app.post("/agent/configure")
async def configure_agent(request: AgentConfigRequest):
    """Настраивает параметры агента"""
    try:
        agent = get_agent()
        
        if request.mode:
            agent.set_mode(request.mode)
        if request.threshold_percent is not None:
            agent.set_threshold(request.threshold_percent)
        if request.min_profit_threshold_usd is not None:
            agent.set_min_profit(request.min_profit_threshold_usd)
        
        return {
            "success": True,
            "config": {
                "mode": agent.mode,
                "threshold_percent": agent.threshold_percent,
                "min_profit_threshold_usd": agent.min_profit_threshold_usd,
                "target_allocation": agent.target_allocation
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка при настройке агента: {str(e)}")


@app.post("/agent/chat")
async def chat_with_agent(request: ChatRequest):
    """Чат с агентом (универсальный endpoint для любых запросов)"""
    try:
        agent = get_agent()
        
        # Формируем промпт с контекстом если есть
        prompt = request.message
        if request.context:
            context_str = "\n".join([f"{k}: {v}" for k, v in request.context.items()])
            prompt = f"Контекст:\n{context_str}\n\nЗапрос пользователя: {request.message}"
        
        response = await agent.run(prompt)
        
        return {
            "success": True,
            "response": response,
            "mode": agent.mode
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке запроса: {str(e)}")


@app.get("/agent/status")
async def get_agent_status():
    """Получает текущий статус и конфигурацию агента"""
    try:
        agent = get_agent()
        return {
            "success": True,
            "status": {
                "mode": agent.mode,
                "threshold_percent": agent.threshold_percent,
                "min_profit_threshold_usd": agent.min_profit_threshold_usd,
                "target_allocation": agent.target_allocation,
                "max_steps": agent.max_steps
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении статуса: {str(e)}")


if __name__ == "__main__":
    # Запуск сервера
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"🚀 Запуск API сервера на http://{host}:{port}")
    print(f"📚 Документация API: http://{host}:{port}/docs")
    print(f"🔍 Альтернативная документация: http://{host}:{port}/redoc")
    
    uvicorn.run(
        "portfolio_rebalancer_api:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )

