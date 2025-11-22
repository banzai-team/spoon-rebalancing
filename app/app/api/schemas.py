"""
Pydantic схемы для API
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any


# ==================== WALLET SCHEMAS ====================

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


# ==================== STRATEGY SCHEMAS ====================

class StrategyCreate(BaseModel):
    """Модель для создания стратегии"""
    name: str = Field(..., description="Название стратегии")
    description: str = Field(..., description="Текстовое описание желаемого портфеля (например: '40% BTC, 35% ETH, 25% USDC')")
    wallet_ids: List[str] = Field(..., description="Список ID кошельков для этой стратегии")


class StrategyUpdate(BaseModel):
    """Модель для обновления стратегии"""
    name: Optional[str] = Field(None, description="Название стратегии")
    description: Optional[str] = Field(None, description="Текстовое описание желаемого портфеля")
    wallet_ids: Optional[List[str]] = Field(None, description="Список ID кошельков")


class StrategyResponse(BaseModel):
    """Модель ответа с информацией о стратегии"""
    id: str
    name: str
    description: str
    wallet_ids: List[str]
    created_at: str
    updated_at: str


# ==================== RECOMMENDATION SCHEMAS ====================

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


# ==================== CHAT SCHEMAS ====================

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


# ==================== AGENT SCHEMAS ====================

class AgentConfigRequest(BaseModel):
    """Модель настройки агента"""
    mode: str = Field(default="consultation", description="Режим работы: 'consultation' или 'autonomous'")


# ==================== WALLET TOKEN BALANCE SCHEMAS ====================

class WalletTokenBalanceCreate(BaseModel):
    """Модель для создания записи о балансе токена"""
    wallet_id: str = Field(..., description="ID кошелька")
    token_symbol: str = Field(..., description="Символ токена (BTC, ETH, USDC и т.д.)")
    balance: str = Field(..., description="Баланс в виде строки")
    balance_usd: Optional[float] = Field(None, description="Баланс в USD")
    chain: str = Field(..., description="Блокчейн")


class WalletTokenBalanceUpdate(BaseModel):
    """Модель для обновления записи о балансе токена"""
    balance: Optional[str] = Field(None, description="Баланс в виде строки")
    balance_usd: Optional[float] = Field(None, description="Баланс в USD")


class WalletTokenBalanceResponse(BaseModel):
    """Модель ответа с информацией о балансе токена"""
    id: str
    wallet_id: str
    user_id: str
    token_symbol: str
    balance: str
    balance_usd: Optional[float]
    chain: str
    created_at: str
    updated_at: str

