"""
Главный файл FastAPI приложения
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import wallets, strategies, recommendations, chat, agent

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

# Подключение роутов
app.include_router(wallets.router)
app.include_router(strategies.router)
app.include_router(recommendations.router)
app.include_router(chat.router)
app.include_router(agent.router)


@app.on_event("startup")
async def startup_event():
    """Событие при запуске приложения"""
    print("🚀 Запуск API сервера ребалансировки портфеля...")
    
    # Проверка подключения к БД (миграции применяются отдельным контейнером)
    try:
        from app.db import get_engine
        from sqlalchemy import text
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Подключение к базе данных успешно")
    except Exception as e:
        print(f"⚠️  Предупреждение при подключении к БД: {e}")
        print("   Убедитесь, что PostgreSQL запущен и миграции применены")


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "service": "Portfolio Rebalancer API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
            "wallets": "/api/wallets",
            "strategies": "/api/strategies",
            "recommendations": "/api/recommendations",
            "chat": "/api/chat",
            "agent": "/api/agent"
        }
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    try:
        from app.db import get_engine
        from sqlalchemy import text
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }

