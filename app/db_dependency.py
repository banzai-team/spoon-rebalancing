"""
Dependency для работы с БД в FastAPI
"""
from fastapi import Depends
from sqlalchemy.orm import Session
import uuid
from database import get_session_local

# Создаем SessionLocal
SessionLocal = get_session_local()

# Фиксированный UUID для пользователя 1
USER_1_ID = uuid.UUID('00000000-0000-0000-0000-000000000001')


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

