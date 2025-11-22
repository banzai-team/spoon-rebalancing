# Быстрый старт: Портфельный ребалансировщик

## Шаг 1: Установка зависимостей

```bash
pip install -r requirements.txt
```

## Шаг 2: Настройка API ключа

```bash
export OPENROUTER_API_KEY="your-api-key-here"
```

Или создайте файл `.env`:
```
OPENROUTER_API_KEY=your-api-key-here
```

## Шаг 3: Запуск API сервера

```bash
python portfolio_rebalancer_api.py
```

Сервер запустится на `http://localhost:8000`

## Шаг 4: Откройте документацию API

Откройте в браузере: http://localhost:8000/docs

## Шаг 5: Протестируйте API

### Пример 1: Анализ портфеля

В Swagger UI или через curl:

```bash
curl -X POST "http://localhost:8000/portfolio/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "wallets": ["0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"],
    "tokens": ["BTC", "ETH", "USDC"],
    "chain": "ethereum"
  }'
```

### Пример 2: Проверка ребалансировки

```bash
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

## Альтернатива: Использование через Python

```python
import asyncio
from portfolio_rebalancer_agent import PortfolioRebalancerAgent
from spoon_ai.chat import ChatBot

async def main():
    agent = PortfolioRebalancerAgent(
        llm=ChatBot(
            llm_provider="openrouter",
            model_name="tngtech/deepseek-r1t2-chimera"
        )
    )
    
    agent.set_mode("consultation")
    agent.set_target_allocation({
        "BTC": 40.0,
        "ETH": 35.0,
        "USDC": 25.0
    })
    
    result = await agent.check_rebalancing(
        wallets=["0x..."],
        tokens=["BTC", "ETH", "USDC"],
        target_allocation={"BTC": 40.0, "ETH": 35.0, "USDC": 25.0}
    )
    
    print(result)

asyncio.run(main())
```

## Тестирование

Запустите тестовый скрипт:

```bash
python test_portfolio_rebalancer.py
```

## Структура проекта

```
demo1/
├── portfolio_rebalancer_tools.py    # Инструменты для ребалансировки
├── portfolio_rebalancer_agent.py    # AI агент
├── portfolio_rebalancer_api.py      # REST API сервер
├── portfolio_config.py              # Конфигурация
├── test_portfolio_rebalancer.py     # Тестовый скрипт
├── PORTFOLIO_REBALANCER_README.md   # Полная документация
└── QUICKSTART.md                    # Этот файл
```

## Следующие шаги

1. Настройте свои кошельки в `portfolio_config.py`
2. Установите целевое распределение портфеля
3. Выберите режим работы (consultation или autonomous)
4. Начните мониторинг и ребалансировку!

## Полезные ссылки

- Полная документация: `PORTFOLIO_REBALANCER_README.md`
- API документация: http://localhost:8000/docs (после запуска сервера)
- SpoonOS документация: `cookbook/llm.txt`

