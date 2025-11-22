"""
Настройка подключения к БД и зависимости для FastAPI
"""
import os
import uuid
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base import Base

# Фиксированный UUID для пользователя 1
USER_1_ID = uuid.UUID('00000000-0000-0000-0000-000000000001')


def get_database_url():
    """Получает URL подключения к БД из переменных окружения"""
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "portfolio_rebalancer")
    
    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


def get_engine():
    """Создает engine для подключения к БД"""
    database_url = get_database_url()
    return create_engine(database_url, echo=os.getenv("DB_ECHO", "False").lower() == "true")


def get_session_local():
    """Создает SessionLocal для работы с БД"""
    engine = get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Создаем SessionLocal
SessionLocal = get_session_local()


def get_db():
    """Dependency для получения сессии БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_id() -> uuid.UUID:
    """
    Dependency для получения ID пользователя.
    Пока возвращает фиксированный ID пользователя 1.
    В будущем здесь можно добавить логику получения user_id из токена/сессии.
    """
    return USER_1_ID

