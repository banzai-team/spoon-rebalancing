"""
Пример использования Portfolio Rebalancer API
Демонстрирует основные сценарии работы с API
"""
import requests
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8000"


def print_response(title: str, response: requests.Response):
    """Красиво выводит ответ API"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except:
        print(response.text)


def example_1_create_wallet():
    """Пример 1: Создание кошелька"""
    print("\n📝 Пример 1: Создание кошелька")
    
    response = requests.post(
        f"{BASE_URL}/api/wallets",
        json={
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "chain": "ethereum",
            "label": "Мой основной кошелек",
            "tokens": ["BTC", "ETH", "USDC"]
        }
    )
    
    print_response("Создание кошелька", response)
    
    if response.status_code == 201:
        return response.json()["id"]
    return None


def example_2_create_strategy(wallet_id: str):
    """Пример 2: Создание стратегии"""
    print("\n📝 Пример 2: Создание стратегии")
    
    response = requests.post(
        f"{BASE_URL}/api/strategies",
        json={
            "name": "Консервативный портфель",
            "description": "Хочу чтобы 40% было в биткоине, 35% в эфириуме, и 25% в стейблкоинах USDC",
            "wallet_ids": [wallet_id],
            "threshold_percent": 5.0,
            "min_profit_threshold_usd": 50.0
        }
    )
    
    print_response("Создание стратегии", response)
    
    if response.status_code == 201:
        return response.json()["id"]
    return None


def example_3_get_recommendation(strategy_id: str):
    """Пример 3: Получение рекомендации"""
    print("\n📝 Пример 3: Получение рекомендации по ребалансировке")
    
    response = requests.post(
        f"{BASE_URL}/api/recommendations",
        json={
            "strategy_id": strategy_id
        }
    )
    
    print_response("Рекомендация", response)
    
    if response.status_code == 201:
        return response.json()["id"]
    return None


def example_4_chat_with_agent(strategy_id: str):
    """Пример 4: Чат с агентом"""
    print("\n📝 Пример 4: Чат с агентом")
    
    response = requests.post(
        f"{BASE_URL}/api/chat",
        json={
            "message": "Объясни мне текущее состояние моего портфеля простыми словами",
            "strategy_id": strategy_id
        }
    )
    
    print_response("Ответ агента", response)


def example_5_list_wallets():
    """Пример 5: Получение списка кошельков"""
    print("\n📝 Пример 5: Список всех кошельков")
    
    response = requests.get(f"{BASE_URL}/api/wallets")
    print_response("Список кошельков", response)


def example_6_list_strategies():
    """Пример 6: Получение списка стратегий"""
    print("\n📝 Пример 6: Список всех стратегий")
    
    response = requests.get(f"{BASE_URL}/api/strategies")
    print_response("Список стратегий", response)


def example_7_agent_status():
    """Пример 7: Статус агента"""
    print("\n📝 Пример 7: Статус и статистика агента")
    
    response = requests.get(f"{BASE_URL}/api/agent/status")
    print_response("Статус агента", response)


def example_8_chat_history():
    """Пример 8: История чата"""
    print("\n📝 Пример 8: История чата")
    
    response = requests.get(f"{BASE_URL}/api/chat/history?limit=5")
    print_response("История чата", response)


def main():
    """Запуск всех примеров"""
    print("🚀 Примеры использования Portfolio Rebalancer API")
    print("=" * 60)
    
    try:
        # Проверка доступности API
        health = requests.get(f"{BASE_URL}/health")
        if health.status_code != 200:
            print(f"❌ API недоступен. Убедитесь, что сервер запущен на {BASE_URL}")
            return
        
        print("✅ API доступен")
        
        # Пример 1: Создание кошелька
        wallet_id = example_1_create_wallet()
        if not wallet_id:
            print("❌ Не удалось создать кошелек")
            return
        
        # Пример 2: Создание стратегии
        strategy_id = example_2_create_strategy(wallet_id)
        if not strategy_id:
            print("❌ Не удалось создать стратегию")
            return
        
        # Пример 3: Получение рекомендации
        recommendation_id = example_3_get_recommendation(strategy_id)
        
        # Пример 4: Чат с агентом
        example_4_chat_with_agent(strategy_id)
        
        # Пример 5: Список кошельков
        example_5_list_wallets()
        
        # Пример 6: Список стратегий
        example_6_list_strategies()
        
        # Пример 7: Статус агента
        example_7_agent_status()
        
        # Пример 8: История чата
        example_8_chat_history()
        
        print("\n" + "=" * 60)
        print("✅ Все примеры выполнены!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Не удалось подключиться к API на {BASE_URL}")
        print("Убедитесь, что сервер запущен:")
        print("  python portfolio_rebalancer_api.py")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")


if __name__ == "__main__":
    main()

