"""
Модели базы данных для Portfolio Rebalancer
"""
from sqlalchemy import Column, String, Float, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.db.base import Base


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
    token_balances = relationship("WalletTokenBalance", back_populates="user", cascade="all, delete-orphan")


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
    token_balances = relationship("WalletTokenBalance", back_populates="wallet", cascade="all, delete-orphan")


class Strategy(Base):
    """Модель стратегии"""
    __tablename__ = "strategies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    last_checked_at = Column(DateTime, nullable=True)  # Дата последней проверки стратегии
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


class WalletTokenBalance(Base):
    """Модель баланса токенов в кошельке"""
    __tablename__ = "wallet_token_balances"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_symbol = Column(String(50), nullable=False)  # BTC, ETH, USDC и т.д.
    balance = Column(String(255), nullable=False)  # Баланс в виде строки (для точности больших чисел)
    balance_usd = Column(Float, nullable=True)  # Баланс в USD
    chain = Column(String(50), nullable=False)  # Блокчейн
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Связи
    wallet = relationship("Wallet", back_populates="token_balances")
    user = relationship("User", back_populates="token_balances")

