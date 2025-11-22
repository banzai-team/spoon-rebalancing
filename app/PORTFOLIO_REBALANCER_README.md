# Портфельный ребалансировщик на SpoonOS

AI-агент для автоматической ребалансировки криптопортфеля на основе рыночных условий и допустимого уровня риска.

## Описание

Агент мониторит криптовалютные позиции по нескольким кошелькам и биржам, анализирует рыночные тренды и шаблоны волатильности. Когда распределение активов отклоняется от целевых процентов (например, биткоин вырастает с 40% до 60% от портфеля), он выполняет сделки для восстановления желаемой структуры.

### Основные возможности

- ✅ Мониторинг балансов по нескольким кошелькам
- ✅ Анализ текущего распределения портфеля
- ✅ Расчет отклонений от целевого распределения
- ✅ Оценка комиссий за газ
- ✅ Предложение конкретных сделок для ребалансировки
- ✅ Режим консультации (предложения) и автономный режим
- ✅ REST API для взаимодействия
- ✅ Учет комиссий и выполнение ребалансировки только при целесообразности

## Установка

1. Установите `uv` (если еще не установлен):
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Или через pip
pip install uv
```

2. Установите зависимости проекта:
```bash
uv pip install -e .
```

2. Настройте переменные окружения:
```bash
export OPENROUTER_API_KEY="your-api-key-here"
# или
export OPENAI_API_KEY="your-api-key-here"
```

## Использование

### 1. Запуск REST API сервера

```bash
python portfolio_rebalancer_api.py
```

Сервер запустится на `http://localhost:8000`

Документация API доступна по адресам:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 2. Использование через Python

```python
import asyncio
from portfolio_rebalancer_agent import PortfolioRebalancerAgent
from spoon_ai.chat import ChatBot

async def main():
    # Инициализация агента
    agent = PortfolioRebalancerAgent(
        llm=ChatBot(
            llm_provider="openrouter",
            model_name="tngtech/deepseek-r1t2-chimera"
        )
    )
    
    # Настройка
    agent.set_mode("consultation")
    agent.set_target_allocation({
        "BTC": 40.0,
        "ETH": 35.0,
        "USDC": 25.0
    })
    
    # Проверка ребалансировки
    result = await agent.check_rebalancing(
        wallets=["0x..."],
        tokens=["BTC", "ETH", "USDC"],
        target_allocation={"BTC": 40.0, "ETH": 35.0, "USDC": 25.0}
    )
    
    print(result)

asyncio.run(main())
```

## REST API Endpoints

### GET `/`
Информация о сервисе и доступных endpoints

### GET `/health`
Проверка здоровья сервиса

### POST `/portfolio/analyze`
Анализ текущего состояния портфеля

**Запрос:**
```json
{
  "wallets": ["0x..."],
  "tokens": ["BTC", "ETH", "USDC"],
  "chain": "ethereum"
}
```

### POST `/portfolio/rebalance`
Проверка необходимости ребалансировки и получение рекомендаций

**Запрос:**
```json
{
  "wallets": ["0x..."],
  "tokens": ["BTC", "ETH", "USDC"],
  "target_allocation": {
    "BTC": 40.0,
    "ETH": 35.0,
    "USDC": 25.0
  },
  "chain": "ethereum",
  "threshold_percent": 5.0,
  "min_profit_threshold_usd": 50.0
}
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "recommendation": "Анализ портфеля...",
    "mode": "consultation"
  },
  "config": {
    "mode": "consultation",
    "threshold_percent": 5.0,
    "min_profit_threshold_usd": 50.0
  }
}
```

### POST `/agent/configure`
Настройка параметров агента

**Запрос:**
```json
{
  "mode": "consultation",
  "threshold_percent": 5.0,
  "min_profit_threshold_usd": 50.0
}
```

### POST `/agent/chat`
Универсальный чат с агентом

**Запрос:**
```json
{
  "message": "Проанализируй мой портфель",
  "context": {
    "wallets": ["0x..."],
    "tokens": ["BTC", "ETH"]
  }
}
```

### GET `/agent/status`
Получение текущего статуса и конфигурации агента

## Примеры использования API

### cURL

```bash
# Анализ портфеля
curl -X POST "http://localhost:8000/portfolio/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "wallets": ["0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"],
    "tokens": ["BTC", "ETH", "USDC"],
    "chain": "ethereum"
  }'

# Проверка ребалансировки
curl -X POST "http://localhost:8000/portfolio/rebalance" \
  -H "Content-Type: application/json" \
  -d '{
    "wallets": ["0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"],
    "tokens": ["BTC", "ETH", "USDC"],
    "target_allocation": {
      "BTC": 40.0,
      "ETH": 35.0,
      "USDC": 25.0
    },
    "threshold_percent": 5.0,
    "min_profit_threshold_usd": 50.0
  }'
```

### Python requests

```python
import requests

# Анализ портфеля
response = requests.post(
    "http://localhost:8000/portfolio/analyze",
    json={
        "wallets": ["0x..."],
        "tokens": ["BTC", "ETH", "USDC"],
        "chain": "ethereum"
    }
)
print(response.json())

# Проверка ребалансировки
response = requests.post(
    "http://localhost:8000/portfolio/rebalance",
    json={
        "wallets": ["0x..."],
        "tokens": ["BTC", "ETH", "USDC"],
        "target_allocation": {
            "BTC": 40.0,
            "ETH": 35.0,
            "USDC": 25.0
        },
        "threshold_percent": 5.0,
        "min_profit_threshold_usd": 50.0
    }
)
print(response.json())
```

## Режимы работы

### Режим консультации (consultation)
Агент анализирует портфель и предлагает конкретные сделки, но не выполняет их автоматически. Пользователь может просмотреть рекомендации и принять решение.

### Автономный режим (autonomous)
Агент автоматически выполняет сделки для ребалансировки портфеля. **Внимание:** В текущей версии это демо-режим, реальные транзакции не выполняются.

## Конфигурация

Используйте файл `portfolio_config.py` для настройки:

```python
from portfolio_config import PortfolioConfig

config = PortfolioConfig()
config.set_target_allocation({
    "BTC": 40.0,
    "ETH": 35.0,
    "USDC": 25.0
})
config.threshold_percent = 5.0
config.min_profit_threshold_usd = 50.0
config.mode = "consultation"
```

## Инструменты агента

Агент использует следующие инструменты:

1. **GetPortfolioBalanceTool** - Получение балансов из кошельков
2. **GetTokenPricesTool** - Получение текущих цен токенов
3. **CalculateRebalancingTool** - Расчет необходимых действий
4. **EstimateGasFeesTool** - Оценка комиссий за газ
5. **SuggestRebalancingTradesTool** - Предложение конкретных сделок

## Безопасность

⚠️ **Важно:**
- В production версии необходимо добавить аутентификацию для API
- Приватные ключи кошельков должны храниться в безопасном хранилище
- Автономный режим должен быть тщательно протестирован перед использованием с реальными средствами
- Всегда проверяйте рекомендации агента перед выполнением транзакций

## Поддерживаемые блокчейны

- Ethereum
- Arbitrum
- Polygon

## Требования

- Python 3.8+
- API ключ для LLM провайдера (OpenRouter, OpenAI, Anthropic и т.д.)
- Интернет соединение для подключения к RPC и API

## Лицензия

Этот проект является демонстрационным примером использования SpoonOS.

