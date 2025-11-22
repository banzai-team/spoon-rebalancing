"""
Dependency для работы с БД в FastAPI
"""
from fastapi import Depends
from sqlalchemy.orm import Session
from database import get_session_local

# Создаем SessionLocal
SessionLocal = get_session_local()


def get_db():
    """Dependency для получения сессии БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

