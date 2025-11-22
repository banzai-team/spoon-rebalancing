"""
Тестовый файл для вызова GetAccountTokensTool из Chainbase
"""
import asyncio
import os
import json
from app.tools.chainbase_tools import GetAccountTokensTool


async def test_get_account_tokens():
    """Тест получения токенов аккаунта через Chainbase API"""
    
    # Проверка наличия API ключа
    api_key = os.getenv("CHAINBASE_API_KEY")
    if not api_key:
        print("⚠️  ВНИМАНИЕ: CHAINBASE_API_KEY не установлен в переменных окружения!")
        print("   Установите его перед запуском: export CHAINBASE_API_KEY='your_key'")
        return
    
    print("🚀 Инициализация GetAccountTokensTool...\n")
    
    # Создание инструмента
    tool = GetAccountTokensTool()
    
    # ========== ТЕСТОВЫЕ ДАННЫЕ ==========
    # Замените на свои реальные данные для тестирования
    
    # Chain IDs:
    # 1 = Ethereum
    # 137 = Polygon
    # 42161 = Arbitrum
    # 10 = Optimism
    # 56 = BSC
    
    test_chain_id = 1  # Ethereum
    test_address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"  # vitalik.eth (пример)
    
    # Опциональные параметры
    contract_address = None  # Можно указать конкретный контракт или None для всех токенов
    limit = 20  # Количество токенов на странице (макс. 100)
    page = 1  # Номер страницы
    
    print("=" * 60)
    print("ТЕСТ: Получение токенов аккаунта")
    print("=" * 60)
    print(f"Chain ID: {test_chain_id}")
    print(f"Address: {test_address}")
    print(f"Limit: {limit}")
    print(f"Page: {page}")
    if contract_address:
        print(f"Contract Address: {contract_address}")
    print("\n⏳ Выполнение запроса...\n")
    
    try:
        # Выполнение запроса
        result = await tool.execute(
            chain_id=test_chain_id,
            address=test_address,
            contract_address=contract_address,
            limit=limit,
            page=page
        )
        
        # Вывод результата
        if "error" in result:
            print(f"❌ Ошибка: {result['error']}\n")
        else:
            print("✅ Успешно получен результат!\n")
            print("📊 Результат:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            # Краткая сводка, если есть данные
            if "data" in result and result["data"]:
                tokens = result["data"]
                print(f"\n📈 Найдено токенов: {len(tokens)}")
                if tokens:
                    print("\n💎 Первые токены:")
                    for i, token in enumerate(tokens[:5], 1):
                        symbol = token.get("symbol", "N/A")
                        balance = token.get("balance", "N/A")
                        print(f"  {i}. {symbol}: {balance}")
    
    except Exception as e:
        print(f"❌ Исключение при выполнении: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_multiple_addresses():
    """Тест для нескольких адресов"""
    
    api_key = os.getenv("CHAINBASE_API_KEY")
    if not api_key:
        print("⚠️  CHAINBASE_API_KEY не установлен!")
        return
    
    tool = GetAccountTokensTool()
    
    # Список адресов для тестирования
    test_addresses = [
        "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",  # vitalik.eth
        "0xb89c49C4781Cce8e2BcEc1E7AD1B5956508E7a48",  # Ваш адрес из test_agent.py
    ]
    
    chain_id = 1  # Ethereum
    
    print("=" * 60)
    print("ТЕСТ: Получение токенов для нескольких адресов")
    print("=" * 60)
    
    for address in test_addresses:
        print(f"\n🔍 Проверка адреса: {address}")
        try:
            result = await tool.execute(
                chain_id=chain_id,
                address=address,
                limit=10
            )
            
            if "error" in result:
                print(f"  ❌ Ошибка: {result['error']}")
            else:
                token_count = len(result.get("data", []))
                print(f"  ✅ Найдено токенов: {token_count}")
        
        except Exception as e:
            print(f"  ❌ Исключение: {str(e)}")


async def test_different_chains():
    """Тест для разных блокчейнов"""
    
    api_key = os.getenv("CHAINBASE_API_KEY")
    if not api_key:
        print("⚠️  CHAINBASE_API_KEY не установлен!")
        return
    
    tool = GetAccountTokensTool()
    
    # Тестовый адрес (должен существовать на разных сетях)
    test_address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    
    # Разные блокчейны
    chains = {
        1: "Ethereum",
        137: "Polygon",
        42161: "Arbitrum",
        10: "Optimism",
        56: "BSC"
    }
    
    print("=" * 60)
    print("ТЕСТ: Получение токенов на разных блокчейнах")
    print("=" * 60)
    print(f"Address: {test_address}\n")
    
    for chain_id, chain_name in chains.items():
        print(f"🔗 {chain_name} (Chain ID: {chain_id})")
        try:
            result = await tool.execute(
                chain_id=chain_id,
                address=test_address,
                limit=5
            )
            
            if "error" in result:
                print(f"  ❌ Ошибка: {result['error']}")
            else:
                token_count = len(result.get("data", []))
                print(f"  ✅ Найдено токенов: {token_count}")
        
        except Exception as e:
            print(f"  ❌ Исключение: {str(e)}")
        
        print()


if __name__ == "__main__":
    # Основной тест
    asyncio.run(test_get_account_tokens())
    
    # Раскомментируйте для дополнительных тестов:
    # asyncio.run(test_multiple_addresses())
    # asyncio.run(test_different_chains())

