"""
REST API сервер для агента ребалансировки портфеля
Расширенная версия с управлением кошельками, стратегиями и чатом
"""
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from portfolio_rebalancer_agent import PortfolioRebalancerAgent
from spoon_ai.chat import ChatBot
import uvicorn
import os
import json
import uuid


# ==================== МОДЕЛИ ДАННЫХ ====================

class WalletCreate(BaseModel):
    """Модель для создания кошелька"""
    address: str = Field(..., description="Адрес кошелька")
    chain: str = Field(..., description="Блокчейн (ethereum, arbitrum, polygon)")
    label: Optional[str] = Field(None, description="Название/метка кошелька")
    tokens: Optional[List[str]] = Field(default=[], description="Список токенов для отслеживания")


class WalletUpdate(BaseModel):
    """Модель для обновления кошелька"""
    chain: Optional[str] = Field(None, description="Блокчейн")
    label: Optional[str] = Field(None, description="Название/метка кошелька")
    tokens: Optional[List[str]] = Field(None, description="Список токенов для отслеживания")


class WalletResponse(BaseModel):
    """Модель ответа с информацией о кошельке"""
    id: str
    address: str
    chain: str
    label: Optional[str]
    tokens: List[str]
    created_at: str
    updated_at: str


class StrategyCreate(BaseModel):
    """Модель для создания стратегии"""
    name: str = Field(..., description="Название стратегии")
    description: str = Field(..., description="Текстовое описание желаемого портфеля (например: '40% BTC, 35% ETH, 25% USDC')")
    wallet_ids: List[str] = Field(..., description="Список ID кошельков для этой стратегии")
    threshold_percent: float = Field(default=5.0, description="Порог отклонения в процентах")
    min_profit_threshold_usd: float = Field(default=50.0, description="Минимальная прибыль в USD")


class StrategyUpdate(BaseModel):
    """Модель для обновления стратегии"""
    name: Optional[str] = Field(None, description="Название стратегии")
    description: Optional[str] = Field(None, description="Текстовое описание желаемого портфеля")
    wallet_ids: Optional[List[str]] = Field(None, description="Список ID кошельков")
    threshold_percent: Optional[float] = Field(None, description="Порог отклонения")
    min_profit_threshold_usd: Optional[float] = Field(None, description="Минимальная прибыль")


class StrategyResponse(BaseModel):
    """Модель ответа с информацией о стратегии"""
    id: str
    name: str
    description: str
    target_allocation: Optional[Dict[str, float]]
    wallet_ids: List[str]
    threshold_percent: float
    min_profit_threshold_usd: float
    created_at: str
    updated_at: str


class RecommendationRequest(BaseModel):
    """Модель запроса рекомендации"""
    strategy_id: str = Field(..., description="ID стратегии для анализа")


class RecommendationResponse(BaseModel):
    """Модель ответа с рекомендацией"""
    id: str
    strategy_id: str
    recommendation: str
    analysis: Optional[Dict[str, Any]]
    created_at: str


class ChatMessage(BaseModel):
    """Модель сообщения в чате"""
    message: str = Field(..., description="Текст сообщения")
    strategy_id: Optional[str] = Field(None, description="ID стратегии для контекста")
    wallet_ids: Optional[List[str]] = Field(None, description="ID кошельков для контекста")


class ChatResponse(BaseModel):
    """Модель ответа чата"""
    message_id: str
    user_message: str
    agent_response: str
    timestamp: str


class ChatHistoryResponse(BaseModel):
    """Модель истории чата"""
    messages: List[ChatResponse]
    total: int


class AgentConfigRequest(BaseModel):
    """Модель настройки агента"""
    mode: str = Field(default="consultation", description="Режим работы: 'consultation' или 'autonomous'")
    threshold_percent: Optional[float] = Field(default=None, description="Порог отклонения в процентах")
    min_profit_threshold_usd: Optional[float] = Field(default=None, description="Минимальная прибыль в USD")


# ==================== IN-MEMORY ХРАНИЛИЩЕ ====================
# В production замените на реальную БД (PostgreSQL, MongoDB и т.д.)

wallets_db: Dict[str, Dict] = {}
strategies_db: Dict[str, Dict] = {}
recommendations_db: Dict[str, Dict] = {}
chat_history: List[Dict] = []


# ==================== ИНИЦИАЛИЗАЦИЯ FASTAPI ====================

app = FastAPI(
    title="Portfolio Rebalancer API",
    description="REST API для агента автоматической ребалансировки криптопортфеля с управлением кошельками и стратегиями",
    version="2.0.0"
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


async def parse_strategy_description(description: str) -> Dict[str, float]:
    """Парсит текстовое описание стратегии в целевое распределение"""
    agent = get_agent()
    
    prompt = f"""
    Пользователь описал желаемое распределение портфеля следующим образом:
    "{description}"
    
    Извлеки из этого описания целевое распределение в процентах для каждого токена.
    Верни результат в формате JSON, где ключи - это символы токенов (BTC, ETH, USDC и т.д.),
    а значения - проценты (числа от 0 до 100).
    
    Пример ответа:
    {{
        "BTC": 40.0,
        "ETH": 35.0,
        "USDC": 25.0
    }}
    
    Если в описании указаны только токены без процентов, распредели их равномерно.
    Убедись, что сумма процентов равна 100.
    """
    
    try:
        response = await agent.run(prompt)
        
        # Пытаемся извлечь JSON из ответа
        import re
        json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
        if json_match:
            allocation = json.loads(json_match.group(0))
            # Нормализуем проценты
            total = sum(allocation.values())
            if total > 0:
                allocation = {k: (v / total) * 100 for k, v in allocation.items()}
            return allocation
        else:
            # Fallback: пытаемся найти проценты в тексте
            # Это упрощенный парсинг, в production лучше использовать более надежный метод
            return {}
    except Exception as e:
        print(f"Ошибка при парсинге описания стратегии: {e}")
        return {}


@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    print("🚀 Запуск API сервера ребалансировки портфеля...")
    get_agent()
    print("✅ Агент инициализирован")


# ==================== КОРНЕВЫЕ ENDPOINTS ====================

@app.get("/")
async def root():
    """Корневой endpoint с информацией об API"""
    return {
        "service": "Portfolio Rebalancer API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "wallets": {
                "GET /api/wallets": "Получить список кошельков",
                "POST /api/wallets": "Создать кошелек",
                "GET /api/wallets/{id}": "Получить кошелек",
                "PUT /api/wallets/{id}": "Обновить кошелек",
                "DELETE /api/wallets/{id}": "Удалить кошелек"
            },
            "strategies": {
                "GET /api/strategies": "Получить список стратегий",
                "POST /api/strategies": "Создать стратегию",
                "GET /api/strategies/{id}": "Получить стратегию",
                "PUT /api/strategies/{id}": "Обновить стратегию",
                "DELETE /api/strategies/{id}": "Удалить стратегию",
                "POST /api/strategies/{id}/parse": "Парсить описание стратегии"
            },
            "recommendations": {
                "POST /api/recommendations": "Получить рекомендацию по ребалансировке",
                "GET /api/recommendations/{id}": "Получить конкретную рекомендацию",
                "GET /api/recommendations": "Получить историю рекомендаций"
            },
            "chat": {
                "POST /api/chat": "Отправить сообщение агенту",
                "GET /api/chat/history": "Получить историю чата"
            },
            "agent": {
                "GET /api/agent/status": "Статус агента",
                "POST /api/agent/configure": "Настроить агента"
            }
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
            "mode": agent.mode if agent else None,
            "wallets_count": len(wallets_db),
            "strategies_count": len(strategies_db)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# ==================== УПРАВЛЕНИЕ КОШЕЛЬКАМИ ====================

@app.get("/api/wallets", response_model=List[WalletResponse])
async def get_wallets():
    """Получить список всех кошельков"""
    return [WalletResponse(**wallet) for wallet in wallets_db.values()]


@app.post("/api/wallets", response_model=WalletResponse, status_code=201)
async def create_wallet(wallet: WalletCreate):
    """Создать новый кошелек"""
    wallet_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    wallet_data = {
        "id": wallet_id,
        "address": wallet.address,
        "chain": wallet.chain,
        "label": wallet.label,
        "tokens": wallet.tokens or [],
        "created_at": now,
        "updated_at": now
    }
    
    wallets_db[wallet_id] = wallet_data
    return WalletResponse(**wallet_data)


@app.get("/api/wallets/{wallet_id}", response_model=WalletResponse)
async def get_wallet(wallet_id: str):
    """Получить кошелек по ID"""
    if wallet_id not in wallets_db:
        raise HTTPException(status_code=404, detail="Кошелек не найден")
    return WalletResponse(**wallets_db[wallet_id])


@app.put("/api/wallets/{wallet_id}", response_model=WalletResponse)
async def update_wallet(wallet_id: str, wallet_update: WalletUpdate):
    """Обновить кошелек"""
    if wallet_id not in wallets_db:
        raise HTTPException(status_code=404, detail="Кошелек не найден")
    
    wallet_data = wallets_db[wallet_id]
    
    if wallet_update.chain is not None:
        wallet_data["chain"] = wallet_update.chain
    if wallet_update.label is not None:
        wallet_data["label"] = wallet_update.label
    if wallet_update.tokens is not None:
        wallet_data["tokens"] = wallet_update.tokens
    
    wallet_data["updated_at"] = datetime.utcnow().isoformat()
    
    return WalletResponse(**wallet_data)


@app.delete("/api/wallets/{wallet_id}", status_code=204)
async def delete_wallet(wallet_id: str):
    """Удалить кошелек"""
    if wallet_id not in wallets_db:
        raise HTTPException(status_code=404, detail="Кошелек не найден")
    
    # Удаляем кошелек из всех стратегий
    for strategy in strategies_db.values():
        if wallet_id in strategy["wallet_ids"]:
            strategy["wallet_ids"].remove(wallet_id)
    
    del wallets_db[wallet_id]
    return None


# ==================== УПРАВЛЕНИЕ СТРАТЕГИЯМИ ====================

@app.get("/api/strategies", response_model=List[StrategyResponse])
async def get_strategies():
    """Получить список всех стратегий"""
    return [StrategyResponse(**strategy) for strategy in strategies_db.values()]


@app.post("/api/strategies", response_model=StrategyResponse, status_code=201)
async def create_strategy(strategy: StrategyCreate):
    """Создать новую стратегию"""
    # Проверяем существование кошельков
    for wallet_id in strategy.wallet_ids:
        if wallet_id not in wallets_db:
            raise HTTPException(status_code=404, detail=f"Кошелек {wallet_id} не найден")
    
    # Парсим описание стратегии
    target_allocation = await parse_strategy_description(strategy.description)
    
    strategy_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    strategy_data = {
        "id": strategy_id,
        "name": strategy.name,
        "description": strategy.description,
        "target_allocation": target_allocation,
        "wallet_ids": strategy.wallet_ids,
        "threshold_percent": strategy.threshold_percent,
        "min_profit_threshold_usd": strategy.min_profit_threshold_usd,
        "created_at": now,
        "updated_at": now
    }
    
    strategies_db[strategy_id] = strategy_data
    return StrategyResponse(**strategy_data)


@app.get("/api/strategies/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: str):
    """Получить стратегию по ID"""
    if strategy_id not in strategies_db:
        raise HTTPException(status_code=404, detail="Стратегия не найдена")
    return StrategyResponse(**strategies_db[strategy_id])


@app.put("/api/strategies/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(strategy_id: str, strategy_update: StrategyUpdate):
    """Обновить стратегию"""
    if strategy_id not in strategies_db:
        raise HTTPException(status_code=404, detail="Стратегия не найдена")
    
    strategy_data = strategies_db[strategy_id]
    
    if strategy_update.name is not None:
        strategy_data["name"] = strategy_update.name
    if strategy_update.description is not None:
        strategy_data["description"] = strategy_update.description
        # Перепарсиваем описание
        strategy_data["target_allocation"] = await parse_strategy_description(strategy_update.description)
    if strategy_update.wallet_ids is not None:
        # Проверяем существование кошельков
        for wallet_id in strategy_update.wallet_ids:
            if wallet_id not in wallets_db:
                raise HTTPException(status_code=404, detail=f"Кошелек {wallet_id} не найден")
        strategy_data["wallet_ids"] = strategy_update.wallet_ids
    if strategy_update.threshold_percent is not None:
        strategy_data["threshold_percent"] = strategy_update.threshold_percent
    if strategy_update.min_profit_threshold_usd is not None:
        strategy_data["min_profit_threshold_usd"] = strategy_update.min_profit_threshold_usd
    
    strategy_data["updated_at"] = datetime.utcnow().isoformat()
    
    return StrategyResponse(**strategy_data)


@app.delete("/api/strategies/{strategy_id}", status_code=204)
async def delete_strategy(strategy_id: str):
    """Удалить стратегию"""
    if strategy_id not in strategies_db:
        raise HTTPException(status_code=404, detail="Стратегия не найдена")
    
    del strategies_db[strategy_id]
    return None


@app.post("/api/strategies/{strategy_id}/parse")
async def parse_strategy(strategy_id: str):
    """Парсить описание стратегии в целевое распределение"""
    if strategy_id not in strategies_db:
        raise HTTPException(status_code=404, detail="Стратегия не найдена")
    
    strategy = strategies_db[strategy_id]
    target_allocation = await parse_strategy_description(strategy["description"])
    
    # Обновляем стратегию
    strategy["target_allocation"] = target_allocation
    strategy["updated_at"] = datetime.utcnow().isoformat()
    
    return {
        "success": True,
        "target_allocation": target_allocation,
        "strategy_id": strategy_id
    }


# ==================== РЕКОМЕНДАЦИИ ====================

@app.post("/api/recommendations", response_model=RecommendationResponse, status_code=201)
async def get_recommendation(request: RecommendationRequest):
    """Получить рекомендацию по ребалансировке для стратегии"""
    if request.strategy_id not in strategies_db:
        raise HTTPException(status_code=404, detail="Стратегия не найдена")
    
    strategy = strategies_db[request.strategy_id]
    
    if not strategy["target_allocation"]:
        raise HTTPException(status_code=400, detail="Целевое распределение не установлено. Используйте /api/strategies/{id}/parse для парсинга описания.")
    
    # Собираем информацию о кошельках
    wallet_addresses = []
    tokens = set()
    chain = None
    
    for wallet_id in strategy["wallet_ids"]:
        if wallet_id not in wallets_db:
            continue
        wallet = wallets_db[wallet_id]
        wallet_addresses.append(wallet["address"])
        tokens.update(wallet.get("tokens", []))
        if chain is None:
            chain = wallet["chain"]
    
    if not wallet_addresses:
        raise HTTPException(status_code=400, detail="Нет доступных кошельков для стратегии")
    
    # Настраиваем агента
    agent = get_agent()
    agent.set_threshold(strategy["threshold_percent"])
    agent.set_min_profit(strategy["min_profit_threshold_usd"])
    
    # Получаем рекомендацию
    result = await agent.check_rebalancing(
        wallets=wallet_addresses,
        tokens=list(tokens) if tokens else ["BTC", "ETH", "USDC"],
        target_allocation=strategy["target_allocation"],
        chain=chain or "ethereum"
    )
    
    # Сохраняем рекомендацию
    recommendation_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    recommendation_data = {
        "id": recommendation_id,
        "strategy_id": request.strategy_id,
        "recommendation": result.get("recommendation", ""),
        "analysis": result,
        "created_at": now
    }
    
    recommendations_db[recommendation_id] = recommendation_data
    
    return RecommendationResponse(**recommendation_data)


@app.get("/api/recommendations/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation_by_id(recommendation_id: str):
    """Получить конкретную рекомендацию по ID"""
    if recommendation_id not in recommendations_db:
        raise HTTPException(status_code=404, detail="Рекомендация не найдена")
    return RecommendationResponse(**recommendations_db[recommendation_id])


@app.get("/api/recommendations", response_model=List[RecommendationResponse])
async def get_recommendations(strategy_id: Optional[str] = None, limit: int = 50):
    """Получить историю рекомендаций"""
    recommendations = list(recommendations_db.values())
    
    if strategy_id:
        recommendations = [r for r in recommendations if r["strategy_id"] == strategy_id]
    
    # Сортируем по дате создания (новые первыми)
    recommendations.sort(key=lambda x: x["created_at"], reverse=True)
    
    return [RecommendationResponse(**r) for r in recommendations[:limit]]


# ==================== ЧАТ С АГЕНТОМ ====================

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_agent(message: ChatMessage):
    """Отправить сообщение агенту"""
    agent = get_agent()
    
    # Формируем контекст
    context_parts = []
    
    if message.strategy_id and message.strategy_id in strategies_db:
        strategy = strategies_db[message.strategy_id]
        context_parts.append(f"Стратегия: {strategy['name']}")
        context_parts.append(f"Описание: {strategy['description']}")
        if strategy.get("target_allocation"):
            context_parts.append(f"Целевое распределение: {json.dumps(strategy['target_allocation'], ensure_ascii=False)}")
    
    if message.wallet_ids:
        wallet_info = []
        for wallet_id in message.wallet_ids:
            if wallet_id in wallets_db:
                wallet = wallets_db[wallet_id]
                wallet_info.append(f"{wallet.get('label', wallet['address'])} ({wallet['chain']})")
        if wallet_info:
            context_parts.append(f"Кошельки: {', '.join(wallet_info)}")
    
    # Формируем промпт
    if context_parts:
        prompt = f"Контекст:\n" + "\n".join(context_parts) + f"\n\nЗапрос пользователя: {message.message}"
    else:
        prompt = message.message
    
    # Получаем ответ от агента
    response = await agent.run(prompt)
    
    # Сохраняем в историю
    message_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    chat_entry = {
        "message_id": message_id,
        "user_message": message.message,
        "agent_response": response,
        "timestamp": now,
        "strategy_id": message.strategy_id,
        "wallet_ids": message.wallet_ids
    }
    
    chat_history.append(chat_entry)
    
    # Ограничиваем историю последними 100 сообщениями
    if len(chat_history) > 100:
        chat_history.pop(0)
    
    return ChatResponse(
        message_id=message_id,
        user_message=message.message,
        agent_response=response,
        timestamp=now
    )


@app.get("/api/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(limit: int = 50):
    """Получить историю чата"""
    # Сортируем по времени (новые первыми)
    sorted_history = sorted(chat_history, key=lambda x: x["timestamp"], reverse=True)
    
    messages = [
        ChatResponse(
            message_id=msg["message_id"],
            user_message=msg["user_message"],
            agent_response=msg["agent_response"],
            timestamp=msg["timestamp"]
        )
        for msg in sorted_history[:limit]
    ]
    
    return ChatHistoryResponse(messages=messages, total=len(chat_history))


# ==================== УПРАВЛЕНИЕ АГЕНТОМ ====================

@app.get("/api/agent/status")
async def get_agent_status():
    """Получить текущий статус и конфигурацию агента"""
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
            },
            "statistics": {
                "wallets_count": len(wallets_db),
                "strategies_count": len(strategies_db),
                "recommendations_count": len(recommendations_db),
                "chat_messages_count": len(chat_history)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении статуса: {str(e)}")


@app.post("/api/agent/configure")
async def configure_agent(request: AgentConfigRequest):
    """Настроить параметры агента"""
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


# ==================== ЗАПУСК СЕРВЕРА ====================

if __name__ == "__main__":
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
