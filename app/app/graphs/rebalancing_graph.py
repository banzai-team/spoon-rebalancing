"""
Graph System для определения ребалансировки портфеля
Использует StateGraph для структурированного выполнения workflow ребалансировки
"""
import json
import logging
from typing import TypedDict, Dict, Any, Optional, List, Annotated
from spoon_ai.graph.builder import (
    DeclarativeGraphBuilder,
    GraphTemplate,
    NodeSpec,
    EdgeSpec,
    ParallelGroupSpec,
    ParallelGroupConfig,
)
from spoon_ai.graph.config import GraphConfig
from spoon_ai.graph import StateGraph, END
from app.tools.rebalancer_tools import (
    CalculateRebalancingTool,
    EstimateGasFeesTool,
    SuggestRebalancingTradesTool,
)
from app.tools.chainbase_tools import GetAccountTokensTool, GetAccountBalanceTool
from spoon_ai.tools.crypto_tools import get_crypto_tools
from spoon_toolkits.crypto.crypto_data_tools.price_data import GetTokenPriceTool
from app.utils.helpers import convert_hex_balance_to_float

logger = logging.getLogger(__name__)


# ==================== STATE DEFINITION ====================

class RebalancingState(TypedDict, total=False):
    """Состояние графа для процесса ребалансировки портфеля"""
    # Входные параметры
    wallets: List[str]  # Список адресов кошельков
    tokens: List[str]  # Список токенов для анализа
    chain_id: int  # ID блокчейна (1 = Ethereum, 137 = Polygon, 42161 = Arbitrum)
    target_allocation: Dict[str, float]  # Целевое распределение в процентах
    threshold_percent: float  # Порог отклонения для ребалансировки (по умолчанию 5%)
    risk_tolerance: str  # Уровень риска (low, medium, high)
    min_profit_threshold_usd: float  # Минимальная прибыль для выполнения ребалансировки
    
    # Промежуточные данные
    token_balances: Dict[str, Any]  # Балансы токенов по кошелькам
    native_balances: Dict[str, float]  # Нативные балансы (ETH, MATIC и т.д.)
    token_prices: Dict[str, float]  # Цены токенов в USD
    current_portfolio: Dict[str, Any]  # Текущий портфель с балансами в USD
    total_portfolio_value_usd: float  # Общая стоимость портфеля в USD
    
    # Результаты анализа
    rebalancing_actions: Dict[str, Any]  # Результат calculate_rebalancing
    gas_fees: Dict[str, Any]  # Оценка gas fees
    suggested_trades: Dict[str, Any]  # Предложенные сделки
    
    # Финальный результат
    rebalancing_needed: bool  # Нужна ли ребалансировка
    recommendation: str  # Текстовое описание рекомендации
    execution_log: List[str]  # Лог выполнения


# ==================== NODE FUNCTIONS ====================

async def fetch_portfolio_balances(
    state: RebalancingState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Узел 1: Получение балансов портфеля из кошельков"""
    logger.info("Fetching portfolio balances...")
    execution_log = state.get("execution_log", [])
    execution_log.append("📊 Fetching portfolio balances...")
    
    wallets = state.get("wallets", [])
    chain_id = state.get("chain_id", 1) # arbitrum
    tokens = state.get("tokens", [])
    
    if not wallets:
        return {
            "execution_log": execution_log,
            "error": "No wallets provided"
        }
    
    # Инструменты для получения балансов
    get_tokens_tool = GetAccountTokensTool()
    get_balance_tool = GetAccountBalanceTool()
    
    token_balances = {}
    native_balances = {}
    total_balances_usd = {}
    
    # Функция для извлечения базового токена из AAVE токена
    def extract_underlying_token(aave_token: str) -> Optional[str]:
        """Извлекает базовый токен из AAVE токена"""
        # AAVE токены на Arbitrum: aArbUSDT -> USDT, aArbWBTC -> WBTC, aArbWETH -> WETH
        token_upper = aave_token.upper()
        if token_upper.startswith("AARB"):
            return token_upper[4:]  # Убираем префикс "AARB"
        elif token_upper.startswith("A") and len(token_upper) > 1:
            underlying = token_upper[1:]
            # Проверяем, что это известный токен
            if underlying in ["USDT", "USDC", "WBTC", "WETH", "ETH", "BTC", "DAI", "BUSD", "TUSD"]:
                return underlying
        return None
    
    try:
        # Получаем балансы для каждого кошелька
        for wallet_address in wallets:
            # Получаем ERC20 токены
            tokens_result = await get_tokens_tool.execute(
                chain_id=chain_id,
                address=wallet_address,
                limit=100
            )
            logger.info("chain_id: %s", chain_id)
            # Получаем нативный баланс (ETH, MATIC и т.д.)
            balance_result = await get_balance_tool.execute(
                chain_id=chain_id,
                address=wallet_address
            )

            logger.debug("tokens_result: %s", tokens_result)
            logger.debug("balance_result: %s", balance_result)
            
            # Обрабатываем результаты GetAccountTokensTool
            # Структура ответа: {'code': 0, 'message': 'ok', 'data': [...], 'count': N}
            if "error" not in tokens_result:
                # Проверяем успешность ответа
                code = tokens_result.get("code", -1)
                if code == 0 and "data" in tokens_result:
                    token_list = tokens_result.get("data", [])
                    logger.debug(f"Обработка {len(token_list)} токенов для кошелька {wallet_address}")
                    
                    for token_data in token_list:
                        symbol = token_data.get("symbol", "").strip().upper()
                        
                        # Пропускаем токены без символа или с некорректными символами
                        if not symbol or "|" in symbol or len(symbol) > 20:
                            logger.debug(f"Пропуск токена с некорректным символом: {symbol}")
                            continue
                        
                        # Получаем decimals (по умолчанию 18 для большинства токенов)
                        decimals = token_data.get("decimals", 18)
                        
                        # Конвертируем баланс из hex строки в число используя convert_hex_balance_to_float
                        raw_balance = token_data.get("balance", "0x0")
                        balance = convert_hex_balance_to_float(raw_balance, decimals)
                        logger.info("token %s, balance: %s, decimals: %s, raw_balance: %s", symbol, balance, decimals, raw_balance)
                        # Пропускаем токены с нулевым балансом
                        if balance <= 0:
                            continue
                        
                        # Определяем, является ли это AAVE токеном (делаем это ДО расчета balance_usd)
                        underlying_token = extract_underlying_token(symbol)
                        aggregation_symbol = underlying_token if underlying_token else symbol
                        
                        # Получаем баланс в USD (если есть)
                        balance_usd = float(token_data.get("balance_usd", 0) or 0)
                        
                        # Если balance_usd не указан, пробуем использовать current_usd_price, но с проверкой разумности
                        # Проверяем разумность для базового токена (aggregation_symbol), а не для оригинального символа
                        if balance_usd == 0 and balance > 0:
                            current_price = float(token_data.get("current_usd_price", 0) or 0)
                            
                            # Проверяем разумность цены перед использованием
                            if current_price > 0:
                                # Для стейблкоинов: если цена больше $2, считаем неправильной
                                if aggregation_symbol in ["USDT", "USDC", "DAI", "BUSD", "TUSD"]:
                                    if current_price <= 2.0:
                                        balance_usd = balance * current_price
                                    else:
                                        # Используем дефолтную цену $1 для стейблкоинов
                                        balance_usd = balance * 1.0
                                        logger.debug(f"Неправильная цена для {symbol} ({current_price}), используем $1.00")
                                else:
                                    # Для других токенов: если цена не слишком завышена, используем
                                    # Проверяем, что цена не больше 1000000 (защита от ошибок)
                                    if current_price < 1000000:
                                        balance_usd = balance * current_price
                                    else:
                                        logger.debug(f"Неправильная цена для {symbol} ({current_price}), пропускаем")
                                        balance_usd = 0
                        
                        # Сохраняем информацию о токене
                        if symbol:
                            # Если balance_usd = 0, но баланс > 0, это означает, что цена не найдена
                            # В этом случае мы все равно должны учесть токен, но balance_usd будет пересчитан позже
                            # Для стейблкоинов используем дефолтную цену $1
                            if balance_usd == 0 and balance > 0:
                                if aggregation_symbol in ["USDT", "USDC", "DAI", "BUSD", "TUSD"]:
                                    balance_usd = balance * 1.0
                                    logger.debug(f"Используем дефолтную цену $1.00 для {symbol} (баланс={balance})")
                                # Для других токенов оставляем 0, пересчитаем позже с актуальными ценами
                            
                            # Агрегируем балансы по базовому токену
                            if aggregation_symbol not in total_balances_usd:
                                total_balances_usd[aggregation_symbol] = 0.0
                            total_balances_usd[aggregation_symbol] += balance_usd
                            
                            # Логируем агрегацию для отладки
                            if underlying_token:
                                logger.info(f"Агрегация AAVE токена {symbol} -> {aggregation_symbol}: баланс={balance}, balance_usd={balance_usd}, total={total_balances_usd[aggregation_symbol]}")
                            elif balance_usd > 0:
                                logger.debug(f"Агрегация токена {symbol}: баланс={balance}, balance_usd={balance_usd}, total={total_balances_usd[aggregation_symbol]}")
                            
                            # Сохраняем информацию о токене (сохраняем оригинальный символ для деталей)
                            if wallet_address not in token_balances:
                                token_balances[wallet_address] = {}
                            token_balances[wallet_address][symbol] = {
                                "balance": balance,
                                "balance_usd": balance_usd,
                                "decimals": decimals,
                                "raw_balance": raw_balance,
                                "contract_address": token_data.get("contract_address"),
                                "name": token_data.get("name"),
                                "is_aave": underlying_token is not None,
                                "underlying_token": underlying_token
                            }
                            
                            if underlying_token:
                                logger.info(f"Обработан AAVE токен {symbol} -> {aggregation_symbol}: баланс={balance}, USD={balance_usd}")
                            else:
                                logger.debug(f"Обработан токен {symbol}: баланс={balance}, USD={balance_usd}")
                else:
                    logger.warning(f"Неуспешный ответ от GetAccountTokensTool для {wallet_address}: code={code}")
            else:
                logger.warning(f"Ошибка при получении токенов для {wallet_address}: {tokens_result.get('error')}")
            
            # Обрабатываем нативный баланс
            if isinstance(balance_result, dict) and "error" not in balance_result:
                # Проверяем формат ответа
                code = balance_result.get("code", -1)
                if code == 0:
                    data = balance_result.get("data")
                    if isinstance(data, str):
                        # Если data - это hex строка, конвертируем её
                        try:
                            # Убираем префикс 0x если есть
                            hex_balance = data.replace("0x", "") if data.startswith("0x") else data
                            native_balance_wei = int(hex_balance, 16)
                        except (ValueError, AttributeError):
                            logger.warning(f"Не удалось конвертировать hex баланс: {data}")
                            native_balance_wei = 0
                    elif isinstance(data, dict):
                        # Если data - это словарь, ищем поле balance
                        balance_value = data.get("balance", 0)
                        if isinstance(balance_value, str):
                            # Если balance - hex строка
                            try:
                                hex_balance = balance_value.replace("0x", "") if balance_value.startswith("0x") else balance_value
                                native_balance_wei = int(hex_balance, 16)
                            except (ValueError, AttributeError):
                                native_balance_wei = float(balance_value) if balance_value else 0
                        else:
                            native_balance_wei = float(balance_value) if balance_value else 0
                    else:
                        # Если data - число
                        native_balance_wei = float(data) if data else 0
                    
                    # Конвертируем из wei в ETH (или другой нативный токен)
                    if native_balance_wei > 0:
                        native_balance = native_balance_wei / 1e18
                        native_balances[wallet_address] = native_balance
                        logger.debug(f"Нативный баланс для {wallet_address}: {native_balance} ETH")
                else:
                    logger.warning(f"Неуспешный ответ от GetAccountBalanceTool для {wallet_address}: code={code}")
            elif isinstance(balance_result, str):
                # Если результат - строка (неожиданный формат), пытаемся обработать
                logger.warning(f"GetAccountBalanceTool вернул строку вместо словаря: {balance_result}")
                try:
                    # Пытаемся распарсить как JSON
                    import json
                    balance_result = json.loads(balance_result)
                    # Повторяем обработку
                    if isinstance(balance_result, dict) and balance_result.get("code") == 0:
                        data = balance_result.get("data")
                        if isinstance(data, str):
                            hex_balance = data.replace("0x", "") if data.startswith("0x") else data
                            native_balance_wei = int(hex_balance, 16)
                            native_balance = native_balance_wei / 1e18
                            native_balances[wallet_address] = native_balance
                except (json.JSONDecodeError, ValueError, AttributeError):
                    logger.error(f"Не удалось обработать результат баланса: {balance_result}")
        
        execution_log.append(f"✅ Retrieved balances for {len(wallets)} wallets")
        
        # Логируем итоговые агрегированные балансы для отладки
        logger.info(f"Итоговые агрегированные балансы (total_balances_usd): {total_balances_usd}")
        for agg_symbol, total_usd in total_balances_usd.items():
            if total_usd > 0:
                logger.info(f"  {agg_symbol}: ${total_usd:,.2f}")
        
        return {
            "token_balances": token_balances,
            "native_balances": native_balances,
            "current_portfolio": {
                "total_balances": total_balances_usd,
                "wallets": wallets
            },
            "execution_log": execution_log
        }
    
    except Exception as e:
        logger.error(f"Error fetching balances: {e}", exc_info=True)
        execution_log.append(f"❌ Error fetching balances: {str(e)}")
        return {
            "execution_log": execution_log,
            "error": f"Failed to fetch balances: {str(e)}"
        }


async def fetch_token_prices(
    state: RebalancingState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Узел 2: Получение текущих цен токенов"""
    logger.info("Fetching token prices...")
    execution_log = state.get("execution_log", [])
    execution_log.append("💰 Fetching token prices...")
    
    try:
        tokens = state.get("tokens", [])
        current_portfolio = state.get("current_portfolio", {})
        
        if not current_portfolio:
            execution_log.append("⚠️ Portfolio not found, skipping price fetch")
            return {
                "token_prices": {},
                "execution_log": execution_log
            }
        
        total_balances = current_portfolio.get("total_balances", {})
        
        # Получаем все уникальные токены из портфеля и запрошенных
        all_tokens = set(tokens) if tokens else set()
        if total_balances:
            all_tokens.update(total_balances.keys())
        
        if not all_tokens:
            execution_log.append("⚠️ No tokens to fetch prices for")
            return {
                "token_prices": {},
                "execution_log": execution_log
            }
        
        token_prices = {}
        price_tool = GetTokenPriceTool()
        
        def extract_underlying_token(aave_token: str) -> Optional[str]:
            """Извлекает базовый токен из AAVE токена"""
            # AAVE токены на Arbitrum: aArbUSDT -> USDT, aArbWBTC -> WBTC, aArbWETH -> WETH
            if aave_token.startswith("aArb"):
                underlying = aave_token[4:]  # Убираем префикс "aArb"
                return underlying
            # AAVE токены на других сетях: aUSDT -> USDT, aWBTC -> WBTC
            elif aave_token.startswith("a") and len(aave_token) > 1:
                underlying = aave_token[1:]  # Убираем префикс "a"
                # Проверяем, что это не просто токен, начинающийся с "a"
                if underlying in ["USDT", "USDC", "WBTC", "WETH", "ETH", "BTC", "DAI"]:
                    return underlying
            return None
        
        # Пытаемся получить цены через инструмент
        if price_tool:
            for token in all_tokens:
                try:
                    price_found = False
                    underlying_token = extract_underlying_token(token)
                    
                    # Если это AAVE токен, сначала пробуем получить цену базового токена
                    if underlying_token:
                        logger.debug(f"Обнаружен AAVE токен {token}, базовый токен: {underlying_token}")
                        # Пробуем получить цену базового токена
                        base_symbols_to_try = [
                            f"{underlying_token}-USDT",
                        ]
                        
                        for symbol in base_symbols_to_try:
                            try:
                                result = await price_tool.execute(symbol=symbol)
                                logger.info(f"Результат запроса цены для базового токена {symbol}: {result} (тип: {type(result)})")
                                
                                # Обрабатываем разные форматы ответа
                                base_price = None
                                
                                if isinstance(result, dict):
                                    # Проверяем разные возможные ключи
                                    if "price" in result:
                                        base_price = result["price"]
                                    elif "Price" in result:
                                        base_price = result["Price"]
                                    elif "value" in result:
                                        base_price = result["value"]
                                    
                                    # Если base_price - строка, пытаемся распарсить
                                    if base_price is not None:
                                        try:
                                            base_price = float(base_price)
                                        except (ValueError, TypeError):
                                            # Если не число, пытаемся извлечь из строки
                                            if isinstance(base_price, str):
                                                import re
                                                price_match = re.search(r'(\d+[.,]?\d*(?:[eE][+-]?\d+)?)', str(base_price))
                                                if price_match:
                                                    base_price = float(price_match.group(1).replace(',', ''))
                                                else:
                                                    base_price = None
                                            else:
                                                base_price = None
                                
                                elif isinstance(result, str):
                                    # Пытаемся извлечь цену из строки
                                    import re
                                    # Ищем числа (включая научную нотацию)
                                    price_match = re.search(r'(\d+[.,]?\d*(?:[eE][+-]?\d+)?)', result)
                                    if price_match:
                                        base_price = float(price_match.group(1).replace(',', ''))
                                
                                # Проверяем разумность цены и сохраняем
                                if base_price is not None:
                                    # Для стейблкоинов принудительно используем цену $1
                                    if underlying_token in ["USDT", "USDC", "DAI", "BUSD", "TUSD"]:
                                        base_price = 1.0
                                    
                                    # Проверяем, что цена разумная (не слишком большая или маленькая)
                                    if 0 < base_price < 1e15:  # Максимальная разумная цена
                                        # Используем цену базового токена для AAVE токена
                                        token_prices[token] = base_price
                                        token_prices[underlying_token] = base_price  # Сохраняем и для базового токена
                                        price_found = True
                                        logger.info(f"Использована цена базового токена {underlying_token} ({base_price}) для AAVE токена {token}")
                                        break
                                    else:
                                        logger.warning(f"Неразумная цена для базового токена {underlying_token}: {base_price}, пропускаем")
                            except Exception as e:
                                logger.warning(f"Ошибка при получении цены для базового токена {symbol}: {e}", exc_info=True)
                                continue
                    
                    # Если не нашли цену через базовый токен (или это не AAVE токен), пробуем напрямую
                    if not price_found:
                        symbols_to_try = [
                            f"{token}-USDT",
                        ]
                        
                        for symbol in symbols_to_try:
                            try:
                                result = await price_tool.execute(symbol=symbol)
                                logger.info(f"Результат запроса цены для {symbol}: {result} (тип: {type(result)})")
                                
                                # Обрабатываем разные форматы ответа
                                price_value = None
                                
                                if isinstance(result, dict):
                                    # Проверяем разные возможные ключи
                                    if "price" in result:
                                        price_value = result["price"]
                                    elif "Price" in result:
                                        price_value = result["Price"]
                                    elif "value" in result:
                                        price_value = result["value"]
                                    
                                    # Если price_value - строка, пытаемся распарсить
                                    if price_value is not None:
                                        try:
                                            price_value = float(price_value)
                                        except (ValueError, TypeError):
                                            # Если не число, пытаемся извлечь из строки
                                            if isinstance(price_value, str):
                                                import re
                                                price_match = re.search(r'(\d+[.,]?\d*(?:[eE][+-]?\d+)?)', str(price_value))
                                                if price_match:
                                                    price_value = float(price_match.group(1).replace(',', ''))
                                                else:
                                                    price_value = None
                                            else:
                                                price_value = None
                                
                                elif isinstance(result, str):
                                    # Пытаемся извлечь цену из строки
                                    import re
                                    # Ищем числа (включая научную нотацию)
                                    price_match = re.search(r'(\d+[.,]?\d*(?:[eE][+-]?\d+)?)', result)
                                    if price_match:
                                        price_value = float(price_match.group(1).replace(',', ''))
                                
                                # Проверяем разумность цены и сохраняем
                                if price_value is not None:
                                    # Для стейблкоинов принудительно используем цену $1
                                    if token in ["USDT", "USDC", "DAI", "BUSD", "TUSD"]:
                                        price_value = 1.0
                                    elif underlying_token and underlying_token in ["USDT", "USDC", "DAI", "BUSD", "TUSD"]:
                                        price_value = 1.0
                                    
                                    # Проверяем, что цена разумная (не слишком большая или маленькая)
                                    if 0 < price_value < 1e15:  # Максимальная разумная цена
                                        token_prices[token] = price_value
                                        price_found = True
                                        logger.info(f"Сохранена цена для {token}: {price_value}")
                                        
                                        # Если это базовый токен для AAVE, сохраняем и для базового токена
                                        if underlying_token and underlying_token not in token_prices:
                                            # Для стейблкоинов принудительно используем цену $1
                                            if underlying_token in ["USDT", "USDC", "DAI", "BUSD", "TUSD"]:
                                                token_prices[underlying_token] = 1.0
                                            else:
                                                token_prices[underlying_token] = price_value
                                            logger.info(f"Также сохранена цена для базового токена {underlying_token}: {token_prices[underlying_token]}")
                                        break
                                    else:
                                        logger.warning(f"Неразумная цена для {token}: {price_value}, пропускаем")
                            except Exception as e:
                                logger.warning(f"Ошибка при получении цены для {symbol}: {e}", exc_info=True)
                                continue
                    
                    # Если не нашли цену через API, используем баланс USD / количество
                    if not price_found and token in total_balances:
                        balance_usd = total_balances[token]
                        # Пытаемся получить количество из балансов
                        total_amount = 0.0
                        token_balances = state.get("token_balances", {})
                        if token_balances:
                            for wallet_balances in token_balances.values():
                                if isinstance(wallet_balances, dict) and token in wallet_balances:
                                    balance_data = wallet_balances[token]
                                    if isinstance(balance_data, dict):
                                        total_amount += balance_data.get("balance", 0)
                                    elif isinstance(balance_data, (int, float)):
                                        total_amount += balance_data
                        
                        if total_amount > 0 and balance_usd > 0:
                            calculated_price = balance_usd / total_amount
                            token_prices[token] = calculated_price
                            logger.debug(f"Calculated price for {token} from balance: {calculated_price}")
                            
                            # Если это AAVE токен и мы не нашли цену базового токена, сохраняем и для базового
                            if underlying_token and underlying_token not in token_prices:
                                token_prices[underlying_token] = calculated_price
                                logger.debug(f"Также сохранена цена для базового токена {underlying_token}: {calculated_price}")
                
                except Exception as e:
                    logger.warning(f"Failed to get price for {token}: {e}")
                    continue
        
        # Для стейблкоинов принудительно устанавливаем цену $1
        for stablecoin in ["USDT", "USDC", "DAI", "BUSD", "TUSD"]:
            if stablecoin in all_tokens or stablecoin in total_balances:
                token_prices[stablecoin] = 1.0
                logger.info(f"Установлена цена $1.00 для стейблкоина {stablecoin}")
        
        # Если не нашли инструмент или не получили цены, используем значения из балансов
        if not token_prices and total_balances:
            token_balances = state.get("token_balances", {})
            for token, balance_usd in total_balances.items():
                if token not in token_prices and balance_usd > 0:
                    total_amount = 0.0
                    if token_balances:
                        for wallet_balances in token_balances.values():
                            if isinstance(wallet_balances, dict) and token in wallet_balances:
                                balance_data = wallet_balances[token]
                                if isinstance(balance_data, dict):
                                    total_amount += balance_data.get("balance", 0)
                                elif isinstance(balance_data, (int, float)):
                                    total_amount += balance_data
                    
                    if total_amount > 0:
                        token_prices[token] = balance_usd / total_amount
                        logger.debug(f"Calculated price for {token} from balance (fallback): {token_prices[token]}")
        
        execution_log.append(f"✅ Retrieved prices for {len(token_prices)} tokens")
        
        return {
            "token_prices": token_prices,
            "execution_log": execution_log
        }
    
    except Exception as e:
        logger.error(f"Error fetching prices: {e}", exc_info=True)
        execution_log.append(f"❌ Error fetching prices: {str(e)}")
        # Возвращаем пустые цены, но не останавливаем выполнение
        return {
            "token_prices": {},
            "execution_log": execution_log
        }


async def calculate_current_allocation(
    state: RebalancingState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Узел 3: Вычисление текущего распределения портфеля"""
    logger.info("Calculating current allocation...")
    execution_log = state.get("execution_log", [])
    execution_log.append("📈 Calculating current allocation...")
    
    try:
        current_portfolio = state.get("current_portfolio", {})
        token_balances = state.get("token_balances", {})
        token_prices = state.get("token_prices", {})
        native_balances = state.get("native_balances", {})
        
        if not current_portfolio:
            execution_log.append("⚠️ Portfolio not found")
            return {
                "total_portfolio_value_usd": 0.0,
                "execution_log": execution_log
            }
        
        # Пересчитываем балансы в USD используя актуальные цены из token_prices
        recalculated_balances_usd = {}
        
        # Получаем исходные total_balances для fallback
        original_total_balances = current_portfolio.get("total_balances", {})
        logger.info(f"Исходные total_balances: {original_total_balances}")
        logger.info(f"token_prices: {token_prices}")
        logger.info(f"token_balances keys: {list(token_balances.keys()) if token_balances else 'empty'}")
        
        # Если token_prices пустой, используем исходные total_balances как fallback
        if not token_prices:
            logger.warning("token_prices пустой, используем исходные total_balances")
            if original_total_balances:
                recalculated_balances_usd = dict(original_total_balances)
                logger.info(f"Использованы исходные балансы: {recalculated_balances_usd}")
        
        # Функция для извлечения базового токена из AAVE токена
        def extract_underlying_token(aave_token: str) -> Optional[str]:
            """Извлекает базовый токен из AAVE токена"""
            token_upper = aave_token.upper()
            if token_upper.startswith("AARB"):
                return token_upper[4:]  # Убираем префикс "AARB"
            elif token_upper.startswith("A") and len(token_upper) > 1:
                underlying = token_upper[1:]
                if underlying in ["USDT", "USDC", "WBTC", "WETH", "ETH", "BTC", "DAI", "BUSD", "TUSD"]:
                    return underlying
            return None
        
        # Обрабатываем ERC20 токены
        # Обрабатываем даже если token_prices пустой - используем сохраненные значения с проверкой
        if token_balances:
            for wallet_address, wallet_tokens in token_balances.items():
                if isinstance(wallet_tokens, dict):
                    for symbol, token_data in wallet_tokens.items():
                        if isinstance(token_data, dict):
                            balance = token_data.get("balance", 0)
                            if balance > 0:
                                # Определяем, является ли это AAVE токеном
                                underlying = extract_underlying_token(symbol)
                                
                                # Для агрегации используем базовый токен, если это AAVE токен
                                aggregation_symbol = underlying if underlying else symbol
                                
                                # Используем актуальную цену из token_prices для базового токена
                                price = 0
                                if token_prices:
                                    price = token_prices.get(aggregation_symbol, 0)
                                    
                                    # Если цена не найдена, пробуем получить цену для оригинального символа
                                    if price == 0:
                                        price = token_prices.get(symbol, 0)
                                
                                # Пересчитываем balance_usd используя актуальную цену
                                if price > 0:
                                    balance_usd = balance * price
                                    logger.debug(f"Пересчет {symbol} -> {aggregation_symbol}: баланс={balance}, цена={price}, USD={balance_usd}")
                                else:
                                    # Если цена не найдена, используем сохраненное значение, но проверяем его разумность
                                    saved_balance_usd = token_data.get("balance_usd", 0) or 0
                                    
                                    # Проверяем, что сохраненное значение разумное
                                    if saved_balance_usd > 0:
                                        calculated_price = saved_balance_usd / balance if balance > 0 else 0
                                        
                                        # Для стейблкоинов: если цена больше $2, считаем неправильной
                                        if aggregation_symbol in ["USDT", "USDC", "DAI", "BUSD", "TUSD"]:
                                            if calculated_price <= 2.0:
                                                balance_usd = saved_balance_usd
                                            else:
                                                # Используем дефолтную цену $1 для стейблкоинов
                                                balance_usd = balance * 1.0
                                                logger.warning(f"Неправильная цена для {symbol} ({calculated_price}), используем $1.00")
                                        else:
                                            # Для других токенов: если цена не слишком завышена, используем
                                            if calculated_price < 1000000:
                                                balance_usd = saved_balance_usd
                                            else:
                                                logger.warning(f"Неправильная цена для {symbol} ({calculated_price}), пропускаем")
                                                balance_usd = 0
                                    else:
                                        # Если сохраненное значение тоже 0, но баланс > 0, используем дефолт для стейблкоинов
                                        if aggregation_symbol in ["USDT", "USDC", "DAI", "BUSD", "TUSD"]:
                                            balance_usd = balance * 1.0
                                            logger.debug(f"Используем дефолтную цену $1.00 для {symbol} (баланс={balance})")
                                        else:
                                            balance_usd = 0
                                
                                # Агрегируем по базовому токену (даже если balance_usd = 0, чтобы не потерять токен)
                                if aggregation_symbol not in recalculated_balances_usd:
                                    recalculated_balances_usd[aggregation_symbol] = 0.0
                                recalculated_balances_usd[aggregation_symbol] += balance_usd
                                
                                if underlying:
                                    logger.info(f"Пересчет AAVE токена {symbol} -> {aggregation_symbol}: баланс={balance}, цена={price}, USD={balance_usd}")
                                else:
                                    logger.debug(f"Пересчет {symbol}: баланс={balance}, цена={price}, USD={balance_usd}")
        
        # Обрабатываем нативные токены (ETH, MATIC и т.д.)
        if native_balances:
            chain_id = state.get("chain_id", 1)
            native_symbol_map = {
                1: "ETH",
                137: "MATIC",
                42161: "ETH",
                10: "ETH",
                56: "BNB"
            }
            native_symbol = native_symbol_map.get(chain_id, "ETH")
            
            native_price = token_prices.get(native_symbol, 0)
            if native_price == 0 and native_symbol == "ETH":
                native_price = token_prices.get("ETH", 0)
            
            for wallet_address, native_balance in native_balances.items():
                if native_balance > 0:
                    if native_price > 0:
                        native_balance_usd = native_balance * native_price
                        if native_symbol not in recalculated_balances_usd:
                            recalculated_balances_usd[native_symbol] = 0.0
                        recalculated_balances_usd[native_symbol] += native_balance_usd
                        logger.debug(f"Нативный баланс {native_symbol}: {native_balance}, цена={native_price}, USD={native_balance_usd}")
        
        # Если после пересчета балансы пустые, используем исходные total_balances
        if not recalculated_balances_usd:
            logger.warning("После пересчета балансы пустые, используем исходные total_balances")
            total_balances = current_portfolio.get("total_balances", {})
            if total_balances:
                recalculated_balances_usd = dict(total_balances)
                logger.info(f"Использованы исходные балансы: {recalculated_balances_usd}")
            else:
                execution_log.append("⚠️ No balances found after recalculation and original balances are also empty")
                logger.error("Нет балансов для расчета стоимости портфеля")
                return {
                    "total_portfolio_value_usd": 0.0,
                    "current_portfolio": current_portfolio,
                    "execution_log": execution_log
                }
        
        # Обновляем current_portfolio с пересчитанными балансами
        current_portfolio["total_balances"] = recalculated_balances_usd
        
        total_value_usd = sum(float(v) for v in recalculated_balances_usd.values() if v)
        
        if total_value_usd == 0:
            execution_log.append("⚠️ Portfolio is empty or balances are zero")
            return {
                "total_portfolio_value_usd": 0.0,
                "current_portfolio": current_portfolio,
                "execution_log": execution_log
            }
        
        execution_log.append(f"💰 Total portfolio value: ${total_value_usd:,.2f}")
        logger.info(f"Пересчитанная стоимость портфеля: ${total_value_usd:,.2f}")
        logger.debug(f"Балансы по токенам: {recalculated_balances_usd}")
        
        return {
            "total_portfolio_value_usd": total_value_usd,
            "current_portfolio": current_portfolio,
            "execution_log": execution_log
        }
    
    except Exception as e:
        logger.error(f"Error calculating allocation: {e}", exc_info=True)
        execution_log.append(f"❌ Error calculating allocation: {str(e)}")
        return {
            "total_portfolio_value_usd": 0.0,
            "execution_log": execution_log
        }


async def calculate_rebalancing_needs(
    state: RebalancingState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Узел 4: Вычисление необходимости ребалансировки"""
    logger.info("Calculating rebalancing needs...")
    execution_log = state.get("execution_log", [])
    execution_log.append("⚖️ Calculating rebalancing needs...")
    
    try:
        current_portfolio = state.get("current_portfolio", {})
        target_allocation = state.get("target_allocation", {})
        threshold_percent = state.get("threshold_percent", 5.0)
        
        if not current_portfolio:
            execution_log.append("⚠️ Portfolio not found, skipping rebalancing calculation")
            return {
                "rebalancing_actions": {"rebalancing_needed": False, "actions": []},
                "rebalancing_needed": False,
                "execution_log": execution_log
            }
        
        if not target_allocation:
            execution_log.append("⚠️ Target allocation not set, skipping rebalancing calculation")
            return {
                "rebalancing_actions": {"rebalancing_needed": False, "actions": []},
                "rebalancing_needed": False,
                "execution_log": execution_log
            }
        
        tool = CalculateRebalancingTool()
        result_str = await tool.execute(
            current_portfolio=current_portfolio,
            target_allocation=target_allocation,
            threshold_percent=threshold_percent
        )
        
        result = json.loads(result_str) if isinstance(result_str, str) else result_str
        
        if "error" in result:
            execution_log.append(f"⚠️ Calculation error: {result['error']}")
            return {
                "rebalancing_actions": {"rebalancing_needed": False, "actions": []},
                "rebalancing_needed": False,
                "execution_log": execution_log
            }
        
        rebalancing_needed = result.get("rebalancing_needed", False)
        actions_count = len(result.get("actions", []))
        
        if rebalancing_needed:
            execution_log.append(f"✅ Rebalancing needed: {actions_count} actions")
        else:
            execution_log.append("✅ Portfolio is balanced, rebalancing not required")
        
        return {
            "rebalancing_actions": result,
            "rebalancing_needed": rebalancing_needed,
            "execution_log": execution_log
        }
    
    except Exception as e:
        logger.error(f"Error calculating rebalancing: {e}", exc_info=True)
        execution_log.append(f"❌ Error calculating rebalancing: {str(e)}")
        # Возвращаем безопасное значение, чтобы граф мог продолжить работу
        return {
            "rebalancing_actions": {"rebalancing_needed": False, "actions": []},
            "rebalancing_needed": False,
            "execution_log": execution_log
        }


async def estimate_transaction_costs(
    state: RebalancingState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Узел 5: Оценка стоимости транзакций (gas fees)"""
    logger.info("Estimating transaction costs...")
    execution_log = state.get("execution_log", [])
    execution_log.append("⛽ Estimating transaction costs...")
    
    chain_id = state.get("chain_id", 1)
    rebalancing_actions = state.get("rebalancing_actions", {})
    actions = rebalancing_actions.get("actions", [])
    
    # Определяем название блокчейна
    chain_names = {
        1: "ethereum",
        137: "polygon",
        42161: "arbitrum",
        10: "optimism",
        56: "bsc"
    }
    chain_name = chain_names.get(chain_id, "ethereum")
    
    num_transactions = len(actions) if actions else 1
    
    try:
        tool = EstimateGasFeesTool()
        result_str = await tool.execute(
            chain=chain_name,
            num_transactions=num_transactions
        )
        
        result = json.loads(result_str) if isinstance(result_str, str) else result_str
        
        if "error" in result:
            execution_log.append(f"⚠️ Failed to estimate gas fees: {result['error']}")
            # Используем значения по умолчанию
            result = {
                "total_gas_usd": 50.0,
                "estimated_cost_per_tx_usd": 50.0 / num_transactions if num_transactions > 0 else 50.0
            }
        
        total_gas = result.get("total_gas_usd", 0)
        execution_log.append(f"💰 Estimated gas fees: ${total_gas:,.2f}")
        
        return {
            "gas_fees": result,
            "execution_log": execution_log
        }
    
    except Exception as e:
        logger.error(f"Error estimating gas fees: {e}", exc_info=True)
        execution_log.append(f"⚠️ Error estimating gas fees: {str(e)}")
        # Возвращаем значения по умолчанию
        return {
            "gas_fees": {
                "total_gas_usd": 50.0,
                "estimated_cost_per_tx_usd": 25.0
            },
            "execution_log": execution_log
        }


async def suggest_trades(
    state: RebalancingState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Узел 6: Предложение конкретных сделок для ребалансировки"""
    logger.info("Suggesting trades...")
    execution_log = state.get("execution_log", [])
    execution_log.append("💡 Suggesting trades for rebalancing...")
    
    rebalancing_actions = state.get("rebalancing_actions", {})
    gas_fees = state.get("gas_fees", {})
    min_profit_threshold = state.get("min_profit_threshold_usd", 50.0)
    
    try:
        tool = SuggestRebalancingTradesTool()
        result_str = await tool.execute(
            rebalancing_actions=rebalancing_actions,
            gas_fees=gas_fees,
            min_profit_threshold_usd=min_profit_threshold
        )
        
        result = json.loads(result_str) if isinstance(result_str, str) else result_str
        
        if "error" in result:
            execution_log.append(f"❌ Error: {result['error']}")
            return {
                "execution_log": execution_log,
                "error": result["error"]
            }
        
        should_rebalance = result.get("should_rebalance", False)
        net_benefit = result.get("net_benefit_usd", 0)
        
        if should_rebalance:
            execution_log.append(f"✅ Rebalancing recommended. Net benefit: ${net_benefit:,.2f}")
        else:
            execution_log.append(f"⚠️ Rebalancing not recommended. Net benefit: ${net_benefit:,.2f}")
        
        return {
            "suggested_trades": result,
            "execution_log": execution_log
        }
    
    except Exception as e:
        logger.error(f"Error suggesting trades: {e}", exc_info=True)
        execution_log.append(f"❌ Error suggesting trades: {str(e)}")
        return {
            "execution_log": execution_log,
            "error": f"Failed to suggest trades: {str(e)}"
        }


async def generate_recommendation(
    state: RebalancingState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Узел 7: Генерация финальной рекомендации"""
    logger.info("Generating recommendation...")
    execution_log = state.get("execution_log", [])
    execution_log.append("📋 Generating final recommendation...")
    
    rebalancing_needed = state.get("rebalancing_needed", False)
    suggested_trades = state.get("suggested_trades", {})
    total_portfolio_value = state.get("total_portfolio_value_usd", 0)
    gas_fees = state.get("gas_fees", {})
    current_portfolio = state.get("current_portfolio", {})
    token_balances = state.get("token_balances", {})
    token_prices = state.get("token_prices", {})
    
    recommendation_parts = []
    
    recommendation_parts.append("=" * 60)
    recommendation_parts.append("PORTFOLIO REBALANCING ANALYSIS")
    recommendation_parts.append("=" * 60)
    recommendation_parts.append(f"\n💰 Total portfolio value: ${total_portfolio_value:,.2f}")
    
    # Функция для извлечения базового токена из AAVE токена
    def extract_underlying_token(aave_token: str) -> Optional[str]:
        """Извлекает базовый токен из AAVE токена"""
        token_upper = aave_token.upper()
        if token_upper.startswith("AARB"):
            return token_upper[4:]  # Убираем префикс "AARB"
        elif token_upper.startswith("A") and len(token_upper) > 1:
            underlying = token_upper[1:]
            if underlying in ["USDT", "USDC", "WBTC", "WETH", "ETH", "BTC", "DAI", "BUSD", "TUSD"]:
                return underlying
        return None
    
    # Подсчитываем количество токенов и их детали
    total_balances = current_portfolio.get("total_balances", {})
    unique_tokens = set()
    token_details = []
    aave_tokens_map = {}  # Маппинг базовый_токен -> список AAVE токенов
    
    # Собираем информацию о токенах из балансов
    # Сначала агрегируем все токены (включая AAVE) по базовым токенам
    aggregated_balances = {}  # Базовый_токен -> список всех токенов (обычных и AAVE)
    
    if token_balances:
        for wallet_address, wallet_tokens in token_balances.items():
            if isinstance(wallet_tokens, dict):
                for symbol, token_data in wallet_tokens.items():
                    if isinstance(token_data, dict):
                        balance = token_data.get("balance", 0)
                        if balance > 0:
                            # Определяем базовый токен для агрегации
                            underlying = extract_underlying_token(symbol)
                            aggregation_symbol = underlying if underlying else symbol
                            
                            # Получаем цену для базового токена
                            price = token_prices.get(aggregation_symbol, 0)
                            if price == 0:
                                price = token_prices.get(symbol, 0)
                            
                            # Для стейблкоинов принудительно используем цену $1
                            if aggregation_symbol in ["USDT", "USDC", "DAI", "BUSD", "TUSD"]:
                                price = 1.0
                            
                            # Пересчитываем balance_usd используя актуальную цену
                            if price > 0 and balance > 0:
                                balance_usd = balance * price
                            else:
                                # Fallback: используем сохраненное значение
                                balance_usd = token_data.get("balance_usd", 0) or 0
                                # Для стейблкоинов пересчитываем с ценой $1
                                if balance_usd == 0 and aggregation_symbol in ["USDT", "USDC", "DAI", "BUSD", "TUSD"]:
                                    balance_usd = balance * 1.0
                            
                            if balance_usd > 0:
                                # Инициализируем структуру для базового токена
                                if aggregation_symbol not in aggregated_balances:
                                    aggregated_balances[aggregation_symbol] = {
                                        "total_balance": 0.0,
                                        "total_balance_usd": 0.0,
                                        "tokens": [],
                                        "is_aave_mixed": False
                                    }
                                
                                # Добавляем токен в агрегацию
                                aggregated_balances[aggregation_symbol]["total_balance"] += balance
                                aggregated_balances[aggregation_symbol]["total_balance_usd"] += balance_usd
                                aggregated_balances[aggregation_symbol]["tokens"].append({
                                    "symbol": symbol,
                                    "balance": balance,
                                    "balance_usd": balance_usd,
                                    "price": price,
                                    "is_aave": underlying is not None
                                })
                                
                                if underlying:
                                    aggregated_balances[aggregation_symbol]["is_aave_mixed"] = True
                                
                                unique_tokens.add(symbol)  # Добавляем оригинальный символ для подсчета
    
    # Формируем детали портфеля из агрегированных данных
    for aggregation_symbol, agg_data in aggregated_balances.items():
        total_balance = agg_data["total_balance"]
        total_balance_usd = agg_data["total_balance_usd"]
        tokens_list = agg_data["tokens"]
        is_aave_mixed = agg_data["is_aave_mixed"]
        
        # Вычисляем среднюю цену
        # Для стейблкоинов принудительно используем цену $1
        if aggregation_symbol in ["USDT", "USDC", "DAI", "BUSD", "TUSD"]:
            avg_price = 1.0
        else:
            avg_price = total_balance_usd / total_balance if total_balance > 0 else 0
        
        if is_aave_mixed:
            # Если есть AAVE токены, добавляем ТОЛЬКО AAVE токены в aave_tokens_map
            # Обычные токены отображаем отдельно
            if aggregation_symbol not in aave_tokens_map:
                aave_tokens_map[aggregation_symbol] = []
            # Добавляем только AAVE токены, не обычные
            aave_balance = 0.0
            aave_balance_usd = 0.0
            for token in tokens_list:
                if token.get("is_aave", False):
                    aave_tokens_map[aggregation_symbol].append(token)
                    aave_balance += token.get("balance", 0)
                    aave_balance_usd += token.get("balance_usd", 0)
            
            # Обычные токены (не AAVE) отображаем отдельно
            regular_balance = total_balance - aave_balance
            regular_balance_usd = total_balance_usd - aave_balance_usd
            
            # Для стейблкоинов принудительно используем цену $1
            if aggregation_symbol in ["USDT", "USDC", "DAI", "BUSD", "TUSD"]:
                regular_price = 1.0
                # Пересчитываем balance_usd с правильной ценой
                if regular_balance > 0 and regular_balance_usd != regular_balance:
                    regular_balance_usd = regular_balance * 1.0
            else:
                regular_price = regular_balance_usd / regular_balance if regular_balance > 0 else avg_price
            
            if regular_balance > 0:
                token_details.append({
                    "symbol": aggregation_symbol,
                    "balance": regular_balance,
                    "balance_usd": regular_balance_usd,
                    "price": regular_price,
                    "is_aave": False
                })
                logger.info(f"Добавлен обычный токен {aggregation_symbol}: баланс={regular_balance}, USD={regular_balance_usd}, цена={regular_price}")
        else:
            # Обычный токен
            token_details.append({
                "symbol": aggregation_symbol,
                "balance": total_balance,
                "balance_usd": total_balance_usd,
                "price": avg_price,
                "is_aave": False
            })
    
    # Добавляем токены из total_balances (уже агрегированные), если их еще нет в aggregated_balances
    # total_balances содержит уже агрегированные балансы по базовым токенам
    for symbol, balance_usd in total_balances.items():
        # Пропускаем, если токен уже обработан в aggregated_balances
        if symbol in aggregated_balances:
            continue
            
        if balance_usd > 0:
            # Проверяем, есть ли AAVE токены для этого базового токена
            has_aave_tokens = False
            if token_balances:
                for wallet_balances in token_balances.values():
                    if isinstance(wallet_balances, dict):
                        for token_symbol, token_data in wallet_balances.items():
                            if isinstance(token_data, dict):
                                underlying = extract_underlying_token(token_symbol)
                                if underlying == symbol:
                                    has_aave_tokens = True
                                    break
                        if has_aave_tokens:
                            break
            
            price = token_prices.get(symbol, 0)
            balance = 0.0
            
            # Пытаемся найти баланс из token_balances (суммируем все токены для этого базового токена)
            if token_balances:
                for wallet_balances in token_balances.values():
                    if isinstance(wallet_balances, dict):
                        for token_symbol, token_data in wallet_balances.items():
                            if isinstance(token_data, dict):
                                underlying = extract_underlying_token(token_symbol)
                                aggregation_symbol = underlying if underlying else token_symbol
                                
                                # Если это токен для нашего базового символа
                                if aggregation_symbol == symbol:
                                    balance += token_data.get("balance", 0)
            
            # Если баланс не найден, вычисляем из balance_usd и цены
            if balance == 0 and price > 0:
                balance = balance_usd / price
            elif balance == 0 and balance_usd > 0:
                # Если цена не найдена, но есть balance_usd, используем его
                # Для стейблкоинов используем дефолтную цену $1
                if symbol in ["USDT", "USDC", "DAI", "BUSD", "TUSD"]:
                    balance = balance_usd / 1.0
                    price = 1.0
            
            if balance > 0 and balance_usd > 0:
                # Если есть AAVE токены, обычный токен уже учтен в агрегированном балансе
                # Не добавляем его отдельно в aave_tokens_map
                if not has_aave_tokens:
                    # Обычный токен без AAVE
                    token_details.append({
                        "symbol": symbol,
                        "balance": balance,
                        "balance_usd": balance_usd,
                        "price": price,
                        "is_aave": False
                    })
                    unique_tokens.add(symbol)
    
    # Добавляем AAVE токены в детали портфеля
    # Важно: добавляем ТОЛЬКО AAVE токены, не обычные
    for underlying, aave_list in aave_tokens_map.items():
        # Суммируем только AAVE токены (не обычные)
        total_aave_balance = sum(a["balance"] for a in aave_list)
        total_aave_balance_usd = sum(a["balance_usd"] for a in aave_list)
        
        # Для стейблкоинов принудительно используем цену $1
        if underlying in ["USDT", "USDC", "DAI", "BUSD", "TUSD"]:
            avg_price = 1.0
        else:
            avg_price = total_aave_balance_usd / total_aave_balance if total_aave_balance > 0 else 0
        
        # НЕ удаляем обычный токен - он должен остаться отдельно
        # AAVE токены добавляем как отдельную группу
        
        # Добавляем агрегированную информацию о базовом токене в AAVE (только AAVE токены)
        token_details.append({
            "symbol": underlying,
            "balance": total_aave_balance,
            "balance_usd": total_aave_balance_usd,
            "price": avg_price,
            "is_aave": True,
            "aave_tokens": aave_list  # Сохраняем список AAVE токенов для детального вывода
        })
        
        # Также добавляем каждый AAVE токен отдельно для детального вывода (только AAVE токены, не обычные)
        for aave_token in aave_list:
            if aave_token.get("is_aave", False):  # Только AAVE токены
                token_details.append({
                    "symbol": aave_token["symbol"],
                    "balance": aave_token["balance"],
                    "balance_usd": aave_token["balance_usd"],
                    "price": aave_token["price"],
                    "is_aave": True,
                    "underlying": underlying
                })
    
    # Сортируем токены по стоимости (от большего к меньшему)
    token_details.sort(key=lambda x: x["balance_usd"], reverse=True)
    
    # Выводим информацию о токенах
    recommendation_parts.append(f"\n📊 Tokens in portfolio: {len(unique_tokens)}")
    if token_details:
        recommendation_parts.append("\n💼 Portfolio details:")
        
        # Группируем токены: сначала обычные, потом AAVE
        regular_tokens = [t for t in token_details if not t.get("is_aave", False)]
        aave_aggregated = {}  # Агрегированные AAVE токены по базовому токену
        aave_individual = []  # Индивидуальные AAVE токены
        
        for token_info in token_details:
            if token_info.get("is_aave", False):
                underlying = token_info.get("underlying")
                if underlying:
                    # Индивидуальный AAVE токен
                    aave_individual.append(token_info)
                elif "aave_tokens" in token_info:
                    # Агрегированный базовый токен
                    aave_aggregated[token_info["symbol"]] = token_info
        
        # Выводим обычные токены
        for token_info in regular_tokens:
            symbol = token_info["symbol"]
            balance = token_info["balance"]
            balance_usd = token_info["balance_usd"]
            price = token_info["price"]
            
            # Форматируем баланс в зависимости от размера
            if balance >= 1:
                balance_str = f"{balance:,.4f}"
            elif balance >= 0.0001:
                balance_str = f"{balance:.6f}"
            else:
                balance_str = f"{balance:.10f}"
            
            price_str = f"${price:,.2f}" if price > 0 else "N/A"
            recommendation_parts.append(
                f"  • {symbol}: {balance_str} (${balance_usd:,.2f}) @ {price_str}"
            )
        
        # Выводим AAVE токены (агрегированные)
        if aave_aggregated:
            recommendation_parts.append("\n🏦 Tokens in AAVE:")
            for underlying, token_info in sorted(aave_aggregated.items(), key=lambda x: x[1]["balance_usd"], reverse=True):
                symbol = token_info["symbol"]
                balance = token_info["balance"]
                balance_usd = token_info["balance_usd"]
                price = token_info["price"]
                aave_list = token_info.get("aave_tokens", [])
                
                # Форматируем баланс
                if balance >= 1:
                    balance_str = f"{balance:,.4f}"
                elif balance >= 0.0001:
                    balance_str = f"{balance:.6f}"
                else:
                    balance_str = f"{balance:.10f}"
                
                price_str = f"${price:,.2f}" if price > 0 else "N/A"
                recommendation_parts.append(
                    f"  • {symbol} (in AAVE): {balance_str} (${balance_usd:,.2f}) @ {price_str}"
                )
                
                # Выводим детали по каждому AAVE токену
                for aave_token in aave_list:
                    aave_symbol = aave_token["symbol"]
                    aave_balance = aave_token["balance"]
                    aave_balance_usd = aave_token["balance_usd"]
                    
                    if aave_balance >= 1:
                        aave_balance_str = f"{aave_balance:,.4f}"
                    elif aave_balance >= 0.0001:
                        aave_balance_str = f"{aave_balance:.6f}"
                    else:
                        aave_balance_str = f"{aave_balance:.10f}"
                    
                    recommendation_parts.append(
                        f"    └─ {aave_symbol}: {aave_balance_str} (${aave_balance_usd:,.2f})"
                    )
    
    if rebalancing_needed:
        should_rebalance = suggested_trades.get("should_rebalance", False)
        net_benefit = suggested_trades.get("net_benefit_usd", 0)
        total_gas = gas_fees.get("total_gas_usd", 0)
        
        recommendation_parts.append(f"\n⚖️ Status: Rebalancing {'RECOMMENDED' if should_rebalance else 'NOT RECOMMENDED'}")
        recommendation_parts.append(f"💵 Expected net benefit: ${net_benefit:,.2f}")
        recommendation_parts.append(f"⛽ Gas fees cost: ${total_gas:,.2f}")
        
        trades = suggested_trades.get("suggested_trades", [])
        if trades:
            recommendation_parts.append("\n📊 Suggested trades:")
            for i, trade in enumerate(trades, 1):
                token = trade.get("token", "N/A")
                action = trade.get("action", "N/A")
                amount = trade.get("amount_usd", 0)
                recommendation_parts.append(
                    f"  {i}. {action} {token}: ${amount:,.2f}"
                )
    else:
        recommendation_parts.append("\n✅ Portfolio is balanced, rebalancing not required")
    
    recommendation_parts.append("\n" + "=" * 60)
    
    recommendation = "\n".join(recommendation_parts)
    
    execution_log.append("✅ Recommendation generated")
    
    return {
        "recommendation": recommendation,
        "execution_log": execution_log
    }


def should_continue_rebalancing(state: RebalancingState) -> str:
    """Условная функция: нужно ли продолжать анализ ребалансировки"""
    rebalancing_needed = state.get("rebalancing_needed", False)
    
    if not rebalancing_needed:
        return "skip_rebalancing"
    
    # Проверяем, есть ли ошибки
    if "error" in state:
        return "error"
    
    return "continue_rebalancing"


# ==================== GRAPH BUILDER ====================

def build_rebalancing_graph() -> StateGraph:
    """Создает граф для определения ребалансировки портфеля"""
    
    # Определяем узлы
    # type: ignore - NodeSpec принимает функции с Dict[str, Any], но в runtime работает с TypedDict
    nodes = [
        NodeSpec("fetch_balances", fetch_portfolio_balances),  # type: ignore
        NodeSpec("fetch_prices", fetch_token_prices),  # type: ignore
        NodeSpec("calculate_allocation", calculate_current_allocation),  # type: ignore
        NodeSpec("calculate_rebalancing", calculate_rebalancing_needs),  # type: ignore
        NodeSpec("estimate_gas", estimate_transaction_costs),  # type: ignore
        NodeSpec("suggest_trades", suggest_trades),  # type: ignore
        NodeSpec("generate_recommendation", generate_recommendation),  # type: ignore
    ]
    
    # Определяем связи (edges)
    edges = [
        # Последовательность основных шагов
        EdgeSpec("fetch_balances", "fetch_prices"),
        EdgeSpec("fetch_prices", "calculate_allocation"),
        EdgeSpec("calculate_allocation", "calculate_rebalancing"),
        
        # Условная маршрутизация после вычисления ребалансировки
        # (будет добавлена через add_conditional_edges)
        
        # Если ребалансировка нужна - продолжаем
        EdgeSpec("estimate_gas", "suggest_trades"),
        EdgeSpec("suggest_trades", "generate_recommendation"),
        
        # Финальный узел
        EdgeSpec("generate_recommendation", END),
    ]
    
    # Конфигурация графа
    config = GraphConfig(
        max_iterations=50
    )
    
    # Создаем шаблон
    template = GraphTemplate(
        entry_point="fetch_balances",
        nodes=nodes,
        edges=edges,
        parallel_groups=[],
        config=config
    )
    
    # Строим граф
    builder = DeclarativeGraphBuilder(RebalancingState)
    graph = builder.build(template)
    
    # Добавляем условную маршрутизацию
    graph.add_conditional_edges(
        "calculate_rebalancing",
        should_continue_rebalancing,
        {
            "continue_rebalancing": "estimate_gas",
            "skip_rebalancing": "generate_recommendation",
            "error": END
        }
    )
    
    return graph


# ==================== USAGE EXAMPLE ====================

async def run_rebalancing_analysis(
    wallets: List[str],
    tokens: List[str],
    target_allocation: Dict[str, float],
    chain_id: int = 1,
    threshold_percent: float = 5.0,
    min_profit_threshold_usd: float = 50.0
) -> Dict[str, Any]:
    """
    Запускает анализ ребалансировки портфеля через Graph System
    
    Args:
        wallets: Список адресов кошельков
        tokens: Список токенов для анализа
        target_allocation: Целевое распределение в процентах (например, {"BTC": 40, "ETH": 35, "USDC": 25})
        chain_id: ID блокчейна (1 = Ethereum, 137 = Polygon, 42161 = Arbitrum)
        threshold_percent: Порог отклонения для ребалансировки (по умолчанию 5%)
        min_profit_threshold_usd: Минимальная прибыль для выполнения ребалансировки
    
    Returns:
        Dict с результатами анализа
    """
    # Создаем граф
    graph = build_rebalancing_graph()
    compiled = graph.compile()
    
    # Инициализируем состояние
    initial_state: RebalancingState = {
        "wallets": wallets,
        "tokens": tokens,
        "chain_id": chain_id,
        "target_allocation": target_allocation,
        "threshold_percent": threshold_percent,
        "min_profit_threshold_usd": min_profit_threshold_usd,
        "execution_log": []
    }
    
    # Запускаем выполнение графа
    # Преобразуем TypedDict в обычный dict для совместимости
    state_dict = dict(initial_state)
    result = await compiled.invoke(state_dict)
    
    return result


if __name__ == "__main__":
    import asyncio
    
    async def test():
        result = await run_rebalancing_analysis(
            wallets=["0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"],  # vitalik.eth
            tokens=["ETH", "USDC", "DAI"],
            target_allocation={"ETH": 60.0, "USDC": 25.0, "DAI": 15.0},
            chain_id=1,
            threshold_percent=5.0,
            min_profit_threshold_usd=50.0
        )
        
        print("\n" + "=" * 60)
        print("ANALYSIS RESULT")
        print("=" * 60)
        print(result.get("recommendation", "No recommendation"))
        print("\n" + "=" * 60)
        print("EXECUTION LOG:")
        print("=" * 60)
        for log_entry in result.get("execution_log", []):
            print(log_entry)
    
    asyncio.run(test())

