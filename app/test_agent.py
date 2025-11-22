"""
Тестовый файл для запуска и тестирования PortfolioRebalancerAgent
"""
import asyncio
import os
from app.agents.portfolio_rebalancer_agent import PortfolioRebalancerAgent
from spoon_ai.chat import ChatBot


async def test_agent():
    """Тестовая функция для проверки работы агента"""
    
    # Инициализация агента
    print("🚀 Инициализация агента...")
    agent = PortfolioRebalancerAgent(
        llm=ChatBot(
            llm_provider="openrouter",  # или "openai", "anthropic", "gemini", "deepseek"
            model_name="x-ai/grok-4.1-fast:free" 
        )
    )
    
    # Настройка агента
    agent.set_mode("consultation")  # Режим консультации
    agent.set_target_allocation({
        "BTC": 40.0,
        "ETH": 35.0,
        "USDC": 25.0
    })
    agent.set_min_profit(50.0)  # Минимальная прибыль $50
    
    print("✅ Агент готов к работе!\n")
    
    # ========== ТЕСТОВЫЕ ДАННЫЕ ==========
    # Замените на свои реальные данные для тестирования
    test_wallets = ["0xb89c49C4781Cce8e2BcEc1E7AD1B5956508E7a48"]  # Пример адреса
    test_tokens = ["BTC", "ETH", "USDC", "USDT"]
    test_chain = "42161"
    
    # ========== ВЫБЕРИТЕ ТЕСТ ==========
    # Раскомментируйте нужный тест:
    
    # Тест 1: Анализ портфеля
    print("=" * 60)
    print("ТЕСТ 1: Анализ портфеля")
    print("=" * 60)
    result = await agent.analyze_portfolio(
        wallets=test_wallets,
        tokens=test_tokens,
        chain=test_chain
    )
    print(f"\n📊 Результат анализа:\n{result.get('analysis', 'Ошибка')}\n")
    
    # Тест 2: Проверка ребалансировки
    # print("=" * 60)
    # print("ТЕСТ 2: Проверка ребалансировки")
    # print("=" * 60)
    # result = await agent.check_rebalancing(
    #     wallets=test_wallets,
    #     tokens=test_tokens,
    #     target_allocation=test_target_allocation,
    #     chain=test_chain
    # )
    # print(f"\n📋 Рекомендация:\n{result.get('recommendation', 'Ошибка')}\n")
    
    # Тест 3: Прямой запрос к агенту (можно задать любой вопрос)
    # print("=" * 60)
    # print("ТЕСТ 3: Прямой запрос к агенту")
    # print("=" * 60)
    # user_query = "Проанализируй мой портфель и скажи, нужна ли ребалансировка"
    # response = await agent.run(user_query)
    # print(f"\n💬 Ответ агента:\n{response}\n")


async def test_custom_query():
    """Тест с кастомным запросом от пользователя"""
    
    # Инициализация агента
    agent = PortfolioRebalancerAgent(
        llm=ChatBot(
            llm_provider="openrouter",
            model_name="x-ai/grok-4.1-fast:free" 
        )
    )
    
    agent.set_mode("consultation")
    agent.set_target_allocation({
        "BTC": 40.0,
        "ETH": 35.0,
        "USDC": 25.0
    })
    
    print("🤖 Агент готов! Введите ваш запрос (или 'exit' для выхода):\n")
    
    # Пример запроса
    test_query = """
    Проанализируй портфель по адресу 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb 
    на блокчейне ethereum для токенов BTC, ETH, USDC.
    Проверь, нужна ли ребалансировка для целевого распределения: 40% BTC, 35% ETH, 25% USDC.
    """
    
    print(f"📝 Запрос: {test_query}\n")
    print("⏳ Обработка...\n")
    
    response = await agent.run(test_query)
    print(f"💬 Ответ агента:\n{response}\n")


if __name__ == "__main__":
    # Запуск основного теста
    asyncio.run(test_agent())
    
    # Или запустите тест с кастомным запросом:
    # asyncio.run(test_custom_query())

