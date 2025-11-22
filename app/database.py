"""
Модели базы данных для Portfolio Rebalancer
"""
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, JSON, ForeignKey, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import os

Base = declarative_base()


class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), nullable=False, unique=True)
    email = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Связи
    wallets = relationship("Wallet", back_populates="user", cascade="all, delete-orphan")
    strategies = relationship("Strategy", back_populates="user", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessageDB", back_populates="user", cascade="all, delete-orphan")


class Wallet(Base):
    """Модель кошелька"""
    __tablename__ = "wallets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    address = Column(String(255), nullable=False)
    chain = Column(String(50), nullable=False)
    label = Column(String(255), nullable=True)
    tokens = Column(JSON, nullable=False, default=list)  # Список токенов
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Связи
    user = relationship("User", back_populates="wallets")
    strategies = relationship("StrategyWallet", back_populates="wallet", cascade="all, delete-orphan")


class Strategy(Base):
    """Модель стратегии"""
    __tablename__ = "strategies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    target_allocation = Column(JSON, nullable=True)  # {"BTC": 40.0, "ETH": 35.0, ...}
    threshold_percent = Column(Float, nullable=False, default=5.0)
    min_profit_threshold_usd = Column(Float, nullable=False, default=50.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Связи
    user = relationship("User", back_populates="strategies")
    wallet_links = relationship("StrategyWallet", back_populates="strategy", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="strategy", cascade="all, delete-orphan")


class StrategyWallet(Base):
    """Связующая таблица между стратегиями и кошельками (many-to-many)"""
    __tablename__ = "strategy_wallets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=False)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Связи
    strategy = relationship("Strategy", back_populates="wallet_links")
    wallet = relationship("Wallet", back_populates="strategies")


class Recommendation(Base):
    """Модель рекомендации"""
    __tablename__ = "recommendations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=False)
    recommendation = Column(Text, nullable=False)
    analysis = Column(JSON, nullable=True)  # Дополнительные данные анализа
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Связи
    user = relationship("User", back_populates="recommendations")
    strategy = relationship("Strategy", back_populates="recommendations")


class ChatMessageDB(Base):
    """Модель сообщения в чате"""
    __tablename__ = "chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    user_message = Column(Text, nullable=False)
    agent_response = Column(Text, nullable=False)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=True)
    wallet_ids = Column(JSON, nullable=True)  # Список UUID кошельков
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Связи
    user = relationship("User", back_populates="chat_messages")
    strategy = relationship("Strategy", foreign_keys=[strategy_id])


# Настройка подключения к БД
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


def init_db():
    """
    Инициализирует БД, создавая все таблицы и создавая пользователя 1.
    
    ВНИМАНИЕ: Эта функция использует create_all для обратной совместимости.
    Для production рекомендуется использовать миграции Alembic через init_db.py
    """

    print("✅ База данных инициализирована")


def drop_db():
    """Удаляет все таблицы из БД"""
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    print("✅ Все таблицы удалены")

