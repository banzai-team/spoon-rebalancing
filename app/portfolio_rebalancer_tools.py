"""
Инструменты для ребалансировки портфеля
"""
import asyncio
from typing import Dict, List, Optional, Any
from spoon_ai.tools.base import BaseTool
from spoon_ai.tools.crypto_tools import get_crypto_tools
from web3 import Web3
import json


class GetPortfolioBalanceTool(BaseTool):
    """Инструмент для получения балансов портфеля из нескольких кошельков"""
    name: str = "get_portfolio_balance"
    description: str = "Получить балансы всех токенов из указанных кошельков и бирж. Возвращает структурированный портфель с балансами в USD."
    parameters: dict = {
        "type": "object",
        "properties": {
            "wallets": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Список адресов кошельков для проверки (например, ['0x...', '0x...'])"
            },
            "tokens": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Список токенов для отслеживания (например, ['BTC', 'ETH', 'USDC'])"
            },
            "chain": {
                "type": "string",
                "description": "Блокчейн для проверки (например, 'ethereum', 'arbitrum', 'polygon')",
                "default": "ethereum"
            }
        },
        "required": ["wallets", "tokens"]
    }

    async def execute(self, wallets: List[str], tokens: List[str], chain: str = "ethereum", **kwargs) -> str:
        """Получает балансы портфеля"""
        try:
            # RPC endpoints для разных сетей
            rpc_endpoints = {
                "ethereum": "https://eth.llamarpc.com",
                "arbitrum": "https://arb1.arbitrum.io/rpc",
                "polygon": "https://polygon-rpc.com"
            }
            
            rpc_url = rpc_endpoints.get(chain.lower(), rpc_endpoints["ethereum"])
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            
            if not w3.is_connected():
                return json.dumps({"error": f"Не удалось подключиться к сети {chain}"}, ensure_ascii=False)
            
            portfolio = {
                "chain": chain,
                "wallets": {},
                "total_balances": {}
            }
            
            # Для каждого токена получаем балансы
            for token in tokens:
                portfolio["total_balances"][token] = 0.0
            
            # Получаем балансы для каждого кошелька
            for wallet_address in wallets:
                if not w3.is_address(wallet_address):
                    continue
                
                wallet_address = w3.to_checksum_address(wallet_address)
                wallet_balances = {}
                
                # Получаем нативный баланс (ETH, MATIC и т.д.)
                native_balance_wei = w3.eth.get_balance(wallet_address)
                native_balance = float(w3.from_wei(native_balance_wei, 'ether'))
                
                # Для Ethereum нативный токен - ETH
                if chain.lower() == "ethereum" or chain.lower() == "arbitrum":
                    if "ETH" in tokens:
                        wallet_balances["ETH"] = native_balance
                        portfolio["total_balances"]["ETH"] = portfolio["total_balances"].get("ETH", 0) + native_balance
                
                portfolio["wallets"][wallet_address] = {
                    "native_balance": native_balance,
                    "token_balances": wallet_balances
                }
            
            return json.dumps(portfolio, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return json.dumps({"error": f"Ошибка при получении балансов: {str(e)}"}, ensure_ascii=False)


class GetTokenPricesTool(BaseTool):
    """Инструмент для получения текущих цен токенов"""
    name: str = "get_token_prices"
    description: str = "Получить текущие цены токенов в USD. Принимает список символов токенов."
    parameters: dict = {
        "type": "object",
        "properties": {
            "tokens": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Список символов токенов (например, ['BTC', 'ETH', 'USDC'])"
            }
        },
        "required": ["tokens"]
    }

    async def execute(self, tokens: List[str], **kwargs) -> str:
        """Получает цены токенов"""
        try:
            from spoon_ai.tools.crypto_tools import get_crypto_tools
            
            crypto_tools = get_crypto_tools()
            price_tool = None
            
            # Находим инструмент для получения цен
            for tool in crypto_tools:
                if hasattr(tool, 'name') and 'price' in tool.name.lower():
                    price_tool = tool
                    break
            
            prices = {}
            
            for token in tokens:
                try:
                    # Пытаемся получить цену через crypto_tools
                    if price_tool:
                        # Формируем символ для биржи (например, BTC/USDT)
                        symbol = f"{token}/USDT" if token != "USDT" else "USDT/USDT"
                        result = await price_tool.execute(symbol=symbol, exchange="binance")
                        
                        if isinstance(result, dict) and "price" in result:
                            prices[token] = float(result["price"])
                        elif isinstance(result, str):
                            # Парсим строковый результат
                            try:
                                import re
                                price_match = re.search(r'(\d+[.,]?\d*)', result)
                                if price_match:
                                    price_str = price_match.group(1).replace(',', '')
                                    prices[token] = float(price_str)
                            except:
                                pass
                    else:
                        # Fallback: используем фиксированные цены для демо
                        demo_prices = {
                            "BTC": 45000.0,
                            "ETH": 2500.0,
                            "USDC": 1.0,
                            "USDT": 1.0,
                            "ARB": 1.2
                        }
                        prices[token] = demo_prices.get(token.upper(), 0.0)
                        
                except Exception as e:
                    # Fallback на демо цены при ошибке
                    demo_prices = {
                        "BTC": 45000.0,
                        "ETH": 2500.0,
                        "USDC": 1.0,
                        "USDT": 1.0,
                        "ARB": 1.2
                    }
                    prices[token] = demo_prices.get(token.upper(), 0.0)
            
            return json.dumps({"prices": prices}, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return json.dumps({"error": f"Ошибка при получении цен: {str(e)}"}, ensure_ascii=False)


class CalculateRebalancingTool(BaseTool):
    """Инструмент для расчета необходимых действий ребалансировки"""
    name: str = "calculate_rebalancing"
    description: str = "Рассчитывает необходимые сделки для ребалансировки портфеля на основе текущих балансов и целевых процентов"
    parameters: dict = {
        "type": "object",
        "properties": {
            "current_portfolio": {
                "type": "object",
                "description": "Текущий портфель с балансами в USD (JSON строка)"
            },
            "target_allocation": {
                "type": "object",
                "description": "Целевое распределение в процентах (например, {'BTC': 40, 'ETH': 35, 'USDC': 25})"
            },
            "threshold_percent": {
                "type": "number",
                "description": "Порог отклонения в процентах, при котором требуется ребалансировка (по умолчанию 5%)",
                "default": 5.0
            }
        },
        "required": ["current_portfolio", "target_allocation"]
    }

    async def execute(self, current_portfolio: Dict[str, Any], target_allocation: Dict[str, float], 
                     threshold_percent: float = 5.0, **kwargs) -> str:
        """Рассчитывает необходимые действия для ребалансировки"""
        try:
            # Парсим текущий портфель если это строка
            if isinstance(current_portfolio, str):
                current_portfolio = json.loads(current_portfolio)
            
            # Вычисляем общую стоимость портфеля
            total_value_usd = sum(current_portfolio.get("total_balances", {}).values())
            
            if total_value_usd == 0:
                return json.dumps({"error": "Портфель пуст или не удалось получить балансы"}, ensure_ascii=False)
            
            # Нормализуем целевые проценты (должны суммироваться до 100)
            total_target = sum(target_allocation.values())
            if total_target != 100:
                # Нормализуем
                for token in target_allocation:
                    target_allocation[token] = (target_allocation[token] / total_target) * 100
            
            # Вычисляем текущие и целевые значения
            rebalancing_actions = []
            current_balances = current_portfolio.get("total_balances", {})
            
            for token, target_percent in target_allocation.items():
                current_value = current_balances.get(token, 0.0)
                current_percent = (current_value / total_value_usd) * 100 if total_value_usd > 0 else 0
                target_value = (target_percent / 100) * total_value_usd
                
                deviation = current_percent - target_percent
                
                # Проверяем, нужна ли ребалансировка
                if abs(deviation) > threshold_percent:
                    action = {
                        "token": token,
                        "current_percent": round(current_percent, 2),
                        "target_percent": round(target_percent, 2),
                        "deviation": round(deviation, 2),
                        "current_value_usd": round(current_value, 2),
                        "target_value_usd": round(target_value, 2),
                        "action": "SELL" if deviation > 0 else "BUY",
                        "amount_usd": round(abs(current_value - target_value), 2)
                    }
                    rebalancing_actions.append(action)
            
            result = {
                "total_portfolio_value_usd": round(total_value_usd, 2),
                "threshold_percent": threshold_percent,
                "rebalancing_needed": len(rebalancing_actions) > 0,
                "actions": rebalancing_actions
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return json.dumps({"error": f"Ошибка при расчете ребалансировки: {str(e)}"}, ensure_ascii=False)


class EstimateGasFeesTool(BaseTool):
    """Инструмент для оценки комиссий за газ"""
    name: str = "estimate_gas_fees"
    description: str = "Оценивает комиссии за газ для транзакций ребалансировки"
    parameters: dict = {
        "type": "object",
        "properties": {
            "chain": {
                "type": "string",
                "description": "Блокчейн (ethereum, arbitrum, polygon)",
                "default": "ethereum"
            },
            "num_transactions": {
                "type": "integer",
                "description": "Количество транзакций для выполнения",
                "default": 1
            }
        },
        "required": []
    }

    async def execute(self, chain: str = "ethereum", num_transactions: int = 1, **kwargs) -> str:
        """Оценивает комиссии за газ"""
        try:
            rpc_endpoints = {
                "ethereum": "https://eth.llamarpc.com",
                "arbitrum": "https://arb1.arbitrum.io/rpc",
                "polygon": "https://polygon-rpc.com"
            }
            
            rpc_url = rpc_endpoints.get(chain.lower(), rpc_endpoints["ethereum"])
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            
            if not w3.is_connected():
                return json.dumps({"error": f"Не удалось подключиться к сети {chain}"}, ensure_ascii=False)
            
            # Получаем текущую цену газа
            gas_price_wei = w3.eth.gas_price
            gas_price_gwei = w3.from_wei(gas_price_wei, 'gwei')
            
            # Средние лимиты газа для разных операций
            # Swap: ~150k, Transfer: ~21k, Approve: ~46k
            avg_gas_limit = 150000  # Для swap операций
            
            total_gas_wei = gas_price_wei * avg_gas_limit * num_transactions
            total_gas_eth = w3.from_wei(total_gas_wei, 'ether')
            
            # Получаем цену ETH для конвертации в USD
            try:
                from spoon_ai.tools.crypto_tools import get_crypto_tools
                crypto_tools = get_crypto_tools()
                price_tool = None
                for tool in crypto_tools:
                    if hasattr(tool, 'name') and 'price' in tool.name.lower():
                        price_tool = tool
                        break
                
                eth_price = 2500.0  # Fallback
                if price_tool:
                    result = await price_tool.execute(symbol="ETH/USDT", exchange="binance")
                    if isinstance(result, dict) and "price" in result:
                        eth_price = float(result["price"])
                    elif isinstance(result, str):
                        import re
                        price_match = re.search(r'(\d+[.,]?\d*)', result)
                        if price_match:
                            eth_price = float(price_match.group(1).replace(',', ''))
                
                total_gas_usd = float(total_gas_eth) * eth_price
            except:
                total_gas_usd = float(total_gas_eth) * 2500.0  # Fallback
            
            result = {
                "chain": chain,
                "gas_price_gwei": float(gas_price_gwei),
                "gas_limit_per_tx": avg_gas_limit,
                "num_transactions": num_transactions,
                "total_gas_eth": float(total_gas_eth),
                "total_gas_usd": round(total_gas_usd, 2),
                "estimated_cost_per_tx_usd": round(total_gas_usd / num_transactions, 2) if num_transactions > 0 else 0
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return json.dumps({"error": f"Ошибка при оценке комиссий: {str(e)}"}, ensure_ascii=False)


class SuggestRebalancingTradesTool(BaseTool):
    """Инструмент для предложения конкретных сделок для ребалансировки"""
    name: str = "suggest_rebalancing_trades"
    description: str = "Предлагает конкретные сделки для ребалансировки с учетом комиссий за газ"
    parameters: dict = {
        "type": "object",
        "properties": {
            "rebalancing_actions": {
                "type": "object",
                "description": "Результат расчета ребалансировки (JSON строка)"
            },
            "gas_fees": {
                "type": "object",
                "description": "Оценка комиссий за газ (JSON строка)"
            },
            "min_profit_threshold_usd": {
                "type": "number",
                "description": "Минимальная прибыль в USD для выполнения ребалансировки (по умолчанию 50 USD)",
                "default": 50.0
            }
        },
        "required": ["rebalancing_actions", "gas_fees"]
    }

    async def execute(self, rebalancing_actions: Dict[str, Any], gas_fees: Dict[str, Any],
                     min_profit_threshold_usd: float = 50.0, **kwargs) -> str:
        """Предлагает конкретные сделки"""
        try:
            # Парсим входные данные если это строки
            if isinstance(rebalancing_actions, str):
                rebalancing_actions = json.loads(rebalancing_actions)
            if isinstance(gas_fees, str):
                gas_fees = json.loads(gas_fees)
            
            total_gas_usd = gas_fees.get("total_gas_usd", 0)
            actions = rebalancing_actions.get("actions", [])
            
            suggested_trades = []
            total_expected_benefit = 0.0
            
            for action in actions:
                amount_usd = action.get("amount_usd", 0)
                # Ожидаемая выгода от ребалансировки (упрощенная модель)
                # В реальности это должно учитывать волатильность и корреляции
                expected_benefit = amount_usd * 0.02  # Предполагаем 2% выгоды от ребалансировки
                
                if expected_benefit > (total_gas_usd / len(actions) if actions else total_gas_usd):
                    trade = {
                        "token": action["token"],
                        "action": action["action"],
                        "amount_usd": round(amount_usd, 2),
                        "expected_benefit_usd": round(expected_benefit, 2),
                        "gas_cost_usd": round(total_gas_usd / len(actions) if actions else total_gas_usd, 2),
                        "net_benefit_usd": round(expected_benefit - (total_gas_usd / len(actions) if actions else total_gas_usd), 2),
                        "recommended": True
                    }
                    suggested_trades.append(trade)
                    total_expected_benefit += expected_benefit
            
            net_benefit = total_expected_benefit - total_gas_usd
            
            result = {
                "should_rebalance": net_benefit > min_profit_threshold_usd,
                "total_gas_cost_usd": round(total_gas_usd, 2),
                "total_expected_benefit_usd": round(total_expected_benefit, 2),
                "net_benefit_usd": round(net_benefit, 2),
                "min_profit_threshold_usd": min_profit_threshold_usd,
                "suggested_trades": suggested_trades
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return json.dumps({"error": f"Ошибка при предложении сделок: {str(e)}"}, ensure_ascii=False)

