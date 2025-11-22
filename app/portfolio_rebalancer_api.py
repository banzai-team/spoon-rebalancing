"""
REST API сервер для агента ребалансировки портфеля
Расширенная версия с управлением кошельками, стратегиями и чатом
"""
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
from portfolio_rebalancer_agent import PortfolioRebalancerAgent
from spoon_ai.chat import ChatBot
from database import User, Wallet, Strategy, StrategyWallet, Recommendation, ChatMessageDB
from db_dependency import get_db, get_user_id
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


# ==================== БАЗА ДАННЫХ ====================
# Используется PostgreSQL через SQLAlchemy


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
    
    # Проверка подключения к БД (миграции применяются отдельным контейнером)
    try:
        from database import get_engine
        from sqlalchemy import text
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Подключение к базе данных успешно")
    except Exception as e:
        print(f"⚠️  Предупреждение при подключении к БД: {e}")
        print("   Убедитесь, что PostgreSQL запущен и миграции применены")
    
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
async def health_check(db: Session = Depends(get_db)):
    """Проверка здоровья сервиса"""
    try:
        agent = get_agent()
        wallets_count = db.query(Wallet).count()
        strategies_count = db.query(Strategy).count()
        return {
            "status": "healthy",
            "agent_initialized": agent is not None,
            "mode": agent.mode if agent else None,
            "wallets_count": wallets_count,
            "strategies_count": strategies_count
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# ==================== УПРАВЛЕНИЕ КОШЕЛЬКАМИ ====================

@app.get("/api/wallets", response_model=List[WalletResponse])
async def get_wallets(db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
    """Получить список всех кошельков пользователя"""
    wallets = db.query(Wallet).filter(Wallet.user_id == user_id).all()
    return [
        WalletResponse(
            id=str(w.id),
            address=w.address,
            chain=w.chain,
            label=w.label,
            tokens=w.tokens or [],
            created_at=w.created_at.isoformat(),
            updated_at=w.updated_at.isoformat()
        )
        for w in wallets
    ]


@app.post("/api/wallets", response_model=WalletResponse, status_code=201)
async def create_wallet(wallet: WalletCreate, db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
    """Создать новый кошелек"""
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


@app.get("/api/wallets/{wallet_id}", response_model=WalletResponse)
async def get_wallet(wallet_id: str, db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
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
    
    return WalletResponse(
        id=str(wallet.id),
        address=wallet.address,
        chain=wallet.chain,
        label=wallet.label,
        tokens=wallet.tokens or [],
        created_at=wallet.created_at.isoformat(),
        updated_at=wallet.updated_at.isoformat()
    )


@app.put("/api/wallets/{wallet_id}", response_model=WalletResponse)
async def update_wallet(wallet_id: str, wallet_update: WalletUpdate, db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
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


@app.delete("/api/wallets/{wallet_id}", status_code=204)
async def delete_wallet(wallet_id: str, db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
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
    
    # Удаляем связи со стратегиями (cascade удалит их автоматически)
    db.delete(wallet)
    db.commit()
    return None


# ==================== УПРАВЛЕНИЕ СТРАТЕГИЯМИ ====================

@app.get("/api/strategies", response_model=List[StrategyResponse])
async def get_strategies(db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
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
            target_allocation=s.target_allocation,
            wallet_ids=wallet_ids,
            threshold_percent=s.threshold_percent,
            min_profit_threshold_usd=s.min_profit_threshold_usd,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat()
        ))
    return result


@app.post("/api/strategies", response_model=StrategyResponse, status_code=201)
async def create_strategy(strategy: StrategyCreate, db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
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
    
    # Парсим описание стратегии
    target_allocation = await parse_strategy_description(strategy.description)
    
    # Создаем стратегию
    db_strategy = Strategy(
        user_id=user_id,
        name=strategy.name,
        description=strategy.description,
        target_allocation=target_allocation,
        threshold_percent=strategy.threshold_percent,
        min_profit_threshold_usd=strategy.min_profit_threshold_usd
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
        target_allocation=db_strategy.target_allocation,
        wallet_ids=strategy.wallet_ids,
        threshold_percent=db_strategy.threshold_percent,
        min_profit_threshold_usd=db_strategy.min_profit_threshold_usd,
        created_at=db_strategy.created_at.isoformat(),
        updated_at=db_strategy.updated_at.isoformat()
    )


@app.get("/api/strategies/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: str, db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
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
        target_allocation=strategy.target_allocation,
        wallet_ids=wallet_ids,
        threshold_percent=strategy.threshold_percent,
        min_profit_threshold_usd=strategy.min_profit_threshold_usd,
        created_at=strategy.created_at.isoformat(),
        updated_at=strategy.updated_at.isoformat()
    )


@app.put("/api/strategies/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(strategy_id: str, strategy_update: StrategyUpdate, db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
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
        # Перепарсиваем описание
        strategy.target_allocation = await parse_strategy_description(strategy_update.description)
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
    if strategy_update.threshold_percent is not None:
        strategy.threshold_percent = strategy_update.threshold_percent
    if strategy_update.min_profit_threshold_usd is not None:
        strategy.min_profit_threshold_usd = strategy_update.min_profit_threshold_usd
    
    db.commit()
    db.refresh(strategy)
    
    wallet_links = db.query(StrategyWallet).filter(StrategyWallet.strategy_id == strategy.id).all()
    wallet_ids = [str(sw.wallet_id) for sw in wallet_links]
    
    return StrategyResponse(
        id=str(strategy.id),
        name=strategy.name,
        description=strategy.description,
        target_allocation=strategy.target_allocation,
        wallet_ids=wallet_ids,
        threshold_percent=strategy.threshold_percent,
        min_profit_threshold_usd=strategy.min_profit_threshold_usd,
        created_at=strategy.created_at.isoformat(),
        updated_at=strategy.updated_at.isoformat()
    )


@app.delete("/api/strategies/{strategy_id}", status_code=204)
async def delete_strategy(strategy_id: str, db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
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
    return None


@app.post("/api/strategies/{strategy_id}/parse")
async def parse_strategy(strategy_id: str, db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
    """Парсить описание стратегии в целевое распределение"""
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
    
    target_allocation = await parse_strategy_description(strategy.description)
    strategy.target_allocation = target_allocation
    db.commit()
    
    return {
        "success": True,
        "target_allocation": target_allocation,
        "strategy_id": strategy_id
    }


# ==================== РЕКОМЕНДАЦИИ ====================

@app.post("/api/recommendations", response_model=RecommendationResponse, status_code=201)
async def get_recommendation(request: RecommendationRequest, db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
    """Получить рекомендацию по ребалансировке для стратегии"""
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
    
    if not strategy.target_allocation:
        raise HTTPException(status_code=400, detail="Целевое распределение не установлено. Используйте /api/strategies/{id}/parse для парсинга описания.")
    
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
    agent = get_agent()
    agent.set_threshold(strategy.threshold_percent)
    agent.set_min_profit(strategy.min_profit_threshold_usd)
    
    # Получаем рекомендацию
    result = await agent.check_rebalancing(
        wallets=wallet_addresses,
        tokens=list(tokens) if tokens else ["BTC", "ETH", "USDC"],
        target_allocation=strategy.target_allocation,
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
    
    return RecommendationResponse(
        id=str(db_recommendation.id),
        strategy_id=str(db_recommendation.strategy_id),
        recommendation=db_recommendation.recommendation,
        analysis=db_recommendation.analysis,
        created_at=db_recommendation.created_at.isoformat()
    )


@app.get("/api/recommendations/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation_by_id(recommendation_id: str, db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
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


@app.get("/api/recommendations", response_model=List[RecommendationResponse])
async def get_recommendations(strategy_id: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
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


# ==================== ЧАТ С АГЕНТОМ ====================

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_agent(message: ChatMessage, db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
    """Отправить сообщение агенту"""
    agent = get_agent()
    
    # Формируем контекст
    context_parts = []
    strategy_uuid = None
    
    if message.strategy_id:
        try:
            strategy_uuid = uuid.UUID(message.strategy_id)
            strategy = db.query(Strategy).filter(
                Strategy.id == strategy_uuid,
                Strategy.user_id == user_id
            ).first()
            if strategy:
                context_parts.append(f"Стратегия: {strategy.name}")
                context_parts.append(f"Описание: {strategy.description}")
                if strategy.target_allocation:
                    context_parts.append(f"Целевое распределение: {json.dumps(strategy.target_allocation, ensure_ascii=False)}")
        except ValueError:
            pass
    
    if message.wallet_ids:
        wallet_info = []
        for wallet_id in message.wallet_ids:
            try:
                wallet_uuid = uuid.UUID(wallet_id)
                wallet = db.query(Wallet).filter(
                    Wallet.id == wallet_uuid,
                    Wallet.user_id == user_id
                ).first()
                if wallet:
                    wallet_info.append(f"{wallet.label or wallet.address} ({wallet.chain})")
            except ValueError:
                pass
        if wallet_info:
            context_parts.append(f"Кошельки: {', '.join(wallet_info)}")
    
    # Формируем промпт
    if context_parts:
        prompt = f"Контекст:\n" + "\n".join(context_parts) + f"\n\nЗапрос пользователя: {message.message}"
    else:
        prompt = message.message
    
    # Получаем ответ от агента
    response = await agent.run(prompt)
    
    # Сохраняем в БД
    db_chat = ChatMessageDB(
        user_id=user_id,
        user_message=message.message,
        agent_response=response,
        strategy_id=strategy_uuid,
        wallet_ids=[uuid.UUID(wid) for wid in (message.wallet_ids or []) if wid]
    )
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    
    return ChatResponse(
        message_id=str(db_chat.id),
        user_message=db_chat.user_message,
        agent_response=db_chat.agent_response,
        timestamp=db_chat.created_at.isoformat()
    )


@app.get("/api/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(limit: int = 50, db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
    """Получить историю чата пользователя"""
    chat_messages = db.query(ChatMessageDB).filter(
        ChatMessageDB.user_id == user_id
    ).order_by(ChatMessageDB.created_at.desc()).limit(limit).all()
    
    messages = [
        ChatResponse(
            message_id=str(msg.id),
            user_message=msg.user_message,
            agent_response=msg.agent_response,
            timestamp=msg.created_at.isoformat()
        )
        for msg in chat_messages
    ]
    
    total = db.query(ChatMessageDB).filter(ChatMessageDB.user_id == user_id).count()
    
    return ChatHistoryResponse(messages=messages, total=total)


# ==================== УПРАВЛЕНИЕ АГЕНТОМ ====================

@app.get("/api/agent/status")
async def get_agent_status(db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_user_id)):
    """Получить текущий статус и конфигурацию агента"""
    try:
        agent = get_agent()
        wallets_count = db.query(Wallet).filter(Wallet.user_id == user_id).count()
        strategies_count = db.query(Strategy).filter(Strategy.user_id == user_id).count()
        recommendations_count = db.query(Recommendation).filter(Recommendation.user_id == user_id).count()
        chat_messages_count = db.query(ChatMessageDB).filter(ChatMessageDB.user_id == user_id).count()
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
                "wallets_count": wallets_count,
                "strategies_count": strategies_count,
                "recommendations_count": recommendations_count,
                "chat_messages_count": chat_messages_count
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
