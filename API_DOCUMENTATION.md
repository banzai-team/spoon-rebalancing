# API Документация: Portfolio Rebalancer API v2.0

Полная документация REST API для веб-приложения ребалансировки криптопортфеля.

## Базовый URL

```
http://localhost:8000
```

## Аутентификация

В текущей версии аутентификация не требуется. В production рекомендуется добавить JWT токены или API ключи.

## Структура API

### 1. Управление кошельками (`/api/wallets`)

#### GET `/api/wallets`
Получить список всех кошельков

**Ответ:**
```json
[
  {
    "id": "uuid",
    "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
    "chain": "ethereum",
    "label": "Мой основной кошелек",
    "tokens": ["BTC", "ETH", "USDC"],
    "created_at": "2024-01-01T12:00:00",
    "updated_at": "2024-01-01T12:00:00"
  }
]
```

#### POST `/api/wallets`
Создать новый кошелек

**Запрос:**
```json
{
  "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
  "chain": "ethereum",
  "label": "Мой основной кошелек",
  "tokens": ["BTC", "ETH", "USDC"]
}
```

**Ответ:** 201 Created
```json
{
  "id": "uuid",
  "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
  "chain": "ethereum",
  "label": "Мой основной кошелек",
  "tokens": ["BTC", "ETH", "USDC"],
  "created_at": "2024-01-01T12:00:00",
  "updated_at": "2024-01-01T12:00:00"
}
```

#### GET `/api/wallets/{wallet_id}`
Получить кошелек по ID

**Ответ:**
```json
{
  "id": "uuid",
  "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
  "chain": "ethereum",
  "label": "Мой основной кошелек",
  "tokens": ["BTC", "ETH", "USDC"],
  "created_at": "2024-01-01T12:00:00",
  "updated_at": "2024-01-01T12:00:00"
}
```

#### PUT `/api/wallets/{wallet_id}`
Обновить кошелек

**Запрос:**
```json
{
  "label": "Обновленное название",
  "tokens": ["BTC", "ETH", "USDC", "ARB"]
}
```

#### DELETE `/api/wallets/{wallet_id}`
Удалить кошелек

**Ответ:** 204 No Content

---

### 2. Управление стратегиями (`/api/strategies`)

#### GET `/api/strategies`
Получить список всех стратегий

**Ответ:**
```json
[
  {
    "id": "uuid",
    "name": "Консервативный портфель",
    "description": "40% BTC, 35% ETH, 25% USDC",
    "target_allocation": {
      "BTC": 40.0,
      "ETH": 35.0,
      "USDC": 25.0
    },
    "wallet_ids": ["wallet-uuid-1", "wallet-uuid-2"],
    "threshold_percent": 5.0,
    "min_profit_threshold_usd": 50.0,
    "created_at": "2024-01-01T12:00:00",
    "updated_at": "2024-01-01T12:00:00"
  }
]
```

#### POST `/api/strategies`
Создать новую стратегию

**Запрос:**
```json
{
  "name": "Консервативный портфель",
  "description": "Хочу чтобы 40% было в биткоине, 35% в эфириуме, и 25% в стейблкоинах USDC",
  "wallet_ids": ["wallet-uuid-1", "wallet-uuid-2"],
  "threshold_percent": 5.0,
  "min_profit_threshold_usd": 50.0
}
```

**Описание стратегии** может быть в свободной текстовой форме. Агент автоматически парсит его и извлекает целевое распределение.

**Ответ:** 201 Created
```json
{
  "id": "uuid",
  "name": "Консервативный портфель",
  "description": "Хочу чтобы 40% было в биткоине...",
  "target_allocation": {
    "BTC": 40.0,
    "ETH": 35.0,
    "USDC": 25.0
  },
  "wallet_ids": ["wallet-uuid-1", "wallet-uuid-2"],
  "threshold_percent": 5.0,
  "min_profit_threshold_usd": 50.0,
  "created_at": "2024-01-01T12:00:00",
  "updated_at": "2024-01-01T12:00:00"
}
```

#### GET `/api/strategies/{strategy_id}`
Получить стратегию по ID

#### PUT `/api/strategies/{strategy_id}`
Обновить стратегию

**Запрос:**
```json
{
  "description": "Обновленное описание: 50% BTC, 30% ETH, 20% USDC",
  "threshold_percent": 7.0
}
```

#### DELETE `/api/strategies/{strategy_id}`
Удалить стратегию

#### POST `/api/strategies/{strategy_id}/parse`
Парсить описание стратегии в целевое распределение

Используйте этот endpoint, если хотите перепарсить описание стратегии после его изменения.

**Ответ:**
```json
{
  "success": true,
  "target_allocation": {
    "BTC": 40.0,
    "ETH": 35.0,
    "USDC": 25.0
  },
  "strategy_id": "uuid"
}
```

---

### 3. Рекомендации (`/api/recommendations`)

#### POST `/api/recommendations`
Получить рекомендацию по ребалансировке для стратегии

**Запрос:**
```json
{
  "strategy_id": "strategy-uuid"
}
```

**Ответ:** 201 Created
```json
{
  "id": "recommendation-uuid",
  "strategy_id": "strategy-uuid",
  "recommendation": "Анализ портфеля показал...",
  "analysis": {
    "recommendation": "...",
    "mode": "consultation"
  },
  "created_at": "2024-01-01T12:00:00"
}
```

#### GET `/api/recommendations/{recommendation_id}`
Получить конкретную рекомендацию по ID

#### GET `/api/recommendations`
Получить историю рекомендаций

**Query параметры:**
- `strategy_id` (optional) - фильтр по стратегии
- `limit` (optional, default: 50) - максимальное количество результатов

**Пример:**
```
GET /api/recommendations?strategy_id=uuid&limit=10
```

---

### 4. Чат с агентом (`/api/chat`)

#### POST `/api/chat`
Отправить сообщение агенту

**Запрос:**
```json
{
  "message": "Проанализируй мой портфель и дай рекомендации",
  "strategy_id": "strategy-uuid",
  "wallet_ids": ["wallet-uuid-1"]
}
```

**Ответ:**
```json
{
  "message_id": "uuid",
  "user_message": "Проанализируй мой портфель...",
  "agent_response": "Анализ показал, что...",
  "timestamp": "2024-01-01T12:00:00"
}
```

#### GET `/api/chat/history`
Получить историю чата

**Query параметры:**
- `limit` (optional, default: 50) - максимальное количество сообщений

**Ответ:**
```json
{
  "messages": [
    {
      "message_id": "uuid",
      "user_message": "...",
      "agent_response": "...",
      "timestamp": "2024-01-01T12:00:00"
    }
  ],
  "total": 10
}
```

---

### 5. Управление агентом (`/api/agent`)

#### GET `/api/agent/status`
Получить статус и конфигурацию агента

**Ответ:**
```json
{
  "success": true,
  "status": {
    "mode": "consultation",
    "threshold_percent": 5.0,
    "min_profit_threshold_usd": 50.0,
    "target_allocation": null,
    "max_steps": 10
  },
  "statistics": {
    "wallets_count": 3,
    "strategies_count": 2,
    "recommendations_count": 15,
    "chat_messages_count": 42
  }
}
```

#### POST `/api/agent/configure`
Настроить параметры агента

**Запрос:**
```json
{
  "mode": "consultation",
  "threshold_percent": 5.0,
  "min_profit_threshold_usd": 50.0
}
```

**Ответ:**
```json
{
  "success": true,
  "config": {
    "mode": "consultation",
    "threshold_percent": 5.0,
    "min_profit_threshold_usd": 50.0,
    "target_allocation": null
  }
}
```

---

## Примеры использования

### Пример 1: Создание кошелька и стратегии

```bash
# 1. Создать кошелек
curl -X POST "http://localhost:8000/api/wallets" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
    "chain": "ethereum",
    "label": "Мой основной кошелек",
    "tokens": ["BTC", "ETH", "USDC"]
  }'

# 2. Создать стратегию
curl -X POST "http://localhost:8000/api/strategies" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Консервативный портфель",
    "description": "40% биткоин, 35% эфириум, 25% стейблкоины USDC",
    "wallet_ids": ["wallet-uuid"],
    "threshold_percent": 5.0,
    "min_profit_threshold_usd": 50.0
  }'
```

### Пример 2: Получение рекомендации

```bash
curl -X POST "http://localhost:8000/api/recommendations" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": "strategy-uuid"
  }'
```

### Пример 3: Чат с агентом

```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Какое текущее распределение моего портфеля?",
    "strategy_id": "strategy-uuid"
  }'
```

### Пример 4: Python requests

```python
import requests

BASE_URL = "http://localhost:8000"

# Создать кошелек
wallet_response = requests.post(
    f"{BASE_URL}/api/wallets",
    json={
        "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
        "chain": "ethereum",
        "label": "Мой кошелек",
        "tokens": ["BTC", "ETH", "USDC"]
    }
)
wallet = wallet_response.json()
wallet_id = wallet["id"]

# Создать стратегию
strategy_response = requests.post(
    f"{BASE_URL}/api/strategies",
    json={
        "name": "Моя стратегия",
        "description": "50% BTC, 30% ETH, 20% USDC",
        "wallet_ids": [wallet_id],
        "threshold_percent": 5.0
    }
)
strategy = strategy_response.json()
strategy_id = strategy["id"]

# Получить рекомендацию
recommendation_response = requests.post(
    f"{BASE_URL}/api/recommendations",
    json={"strategy_id": strategy_id}
)
recommendation = recommendation_response.json()
print(recommendation["recommendation"])
```

---

## Поддерживаемые блокчейны

- `ethereum` - Ethereum Mainnet
- `arbitrum` - Arbitrum One
- `polygon` - Polygon

## Коды ошибок

- `200` - Успешный запрос
- `201` - Ресурс создан
- `204` - Успешное удаление (нет тела ответа)
- `400` - Неверный запрос
- `404` - Ресурс не найден
- `500` - Внутренняя ошибка сервера

## Примечания

1. **In-Memory хранилище**: Текущая версия использует in-memory хранилище. При перезапуске сервера все данные будут потеряны. В production рекомендуется использовать PostgreSQL, MongoDB или другую БД.

2. **Парсинг стратегий**: Агент использует LLM для парсинга текстового описания стратегии. Результат может варьироваться в зависимости от формулировки.

3. **Режимы работы**:
   - `consultation` - агент только дает рекомендации
   - `autonomous` - агент может выполнять транзакции (в текущей версии - демо режим)

4. **История чата**: Ограничена последними 100 сообщениями в памяти.

## Swagger UI

Интерактивная документация доступна по адресу:
- http://localhost:8000/docs
- http://localhost:8000/redoc

