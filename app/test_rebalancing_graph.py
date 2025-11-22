"""
Тестовый файл для проверки работы Graph System ребалансировки портфеля
"""
import asyncio
from app.graphs.rebalancing_graph import run_rebalancing_analysis


async def test_rebalancing_graph():
    """Тест Graph System для определения ребалансировки"""
    
    print("🚀 Запуск теста Graph System для ребалансировки портфеля\n")
    
    # Тестовые данные
    test_wallets = ["0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"]  # vitalik.eth (пример)
    test_tokens = ["ETH", "USDC", "DAI"]
    test_target_allocation = {
        "ETH": 60.0,
        "USDC": 25.0,
        "DAI": 15.0
    }
    
    print("=" * 60)
    print("ПАРАМЕТРЫ ТЕСТА")
    print("=" * 60)
    print(f"Кошельки: {', '.join(test_wallets)}")
    print(f"Токены: {', '.join(test_tokens)}")
    print(f"Целевое распределение: {test_target_allocation}")
    print(f"Блокчейн: Ethereum (chain_id=1)")
    print(f"Порог отклонения: 5%")
    print(f"Минимальная прибыль: $50")
    print("\n" + "=" * 60 + "\n")
    
    try:
        # Запускаем анализ через Graph System
        result = await run_rebalancing_analysis(
            wallets=test_wallets,
            tokens=test_tokens,
            target_allocation=test_target_allocation,
            chain_id=1,  # Arbitrum
            threshold_percent=5.0,
            min_profit_threshold_usd=50.0
        )
        
        # Выводим результаты
        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТ АНАЛИЗА")
        print("=" * 60)
        
        if "recommendation" in result:
            print(result["recommendation"])
        else:
            print("Рекомендация не сгенерирована")
        
        # Выводим лог выполнения
        print("\n" + "=" * 60)
        print("ЛОГ ВЫПОЛНЕНИЯ")
        print("=" * 60)
        for log_entry in result.get("execution_log", []):
            print(log_entry)
        
        # Дополнительная информация
        if "rebalancing_needed" in result:
            print(f"\n📊 Ребалансировка необходима: {result['rebalancing_needed']}")
        
        if "total_portfolio_value_usd" in result:
            print(f"💰 Общая стоимость портфеля: ${result['total_portfolio_value_usd']:,.2f}")
        
        if "suggested_trades" in result:
            trades = result["suggested_trades"]
            if isinstance(trades, dict) and "should_rebalance" in trades:
                print(f"✅ Рекомендуется ребалансировка: {trades['should_rebalance']}")
                if "net_benefit_usd" in trades:
                    print(f"💵 Чистая выгода: ${trades['net_benefit_usd']:,.2f}")
        
        print("\n" + "=" * 60)
        print("✅ ТЕСТ ЗАВЕРШЕН")
        print("=" * 60)
    
    except Exception as e:
        print(f"\n❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_rebalancing_graph())

