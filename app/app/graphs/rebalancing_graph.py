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
    execution_log.append("📊 Получение балансов портфеля...")
    
    wallets = state.get("wallets", [])
    chain_id = state.get("chain_id", 1)
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
    
    try:
        # Получаем балансы для каждого кошелька
        for wallet_address in wallets:
            # Получаем ERC20 токены
            tokens_result = await get_tokens_tool.execute(
                chain_id=chain_id,
                address=wallet_address,
                limit=100
            )
            
            # Получаем нативный баланс (ETH, MATIC и т.д.)
            balance_result = await get_balance_tool.execute(
                chain_id=chain_id,
                address=wallet_address
            )

            logger.info("tokens_result: %s", tokens_result)
            logger.info("balance_result: %s", balance_result)
            
            # Обрабатываем результаты
            if "error" not in tokens_result and "data" in tokens_result:
                for token_data in tokens_result.get("data", []):
                    symbol = token_data.get("symbol", "").upper()
                    
                    # Получаем decimals (по умолчанию 18 для большинства токенов)
                    decimals = token_data.get("decimals", 18)
                    
                    # Конвертируем баланс из hex строки в число
                    raw_balance = token_data.get("balance", 0)
                    balance = convert_hex_balance_to_float(raw_balance, decimals)
                    
                    # Получаем баланс в USD (если есть)
                    balance_usd = float(token_data.get("balance_usd", 0) or 0)
                    
                    # Если balance_usd не указан, но есть current_usd_price, вычисляем
                    if balance_usd == 0 and balance > 0:
                        current_price = float(token_data.get("current_usd_price", 0) or 0)
                        if current_price > 0:
                            balance_usd = balance * current_price
                    
                    if symbol and balance > 0:
                        if symbol not in total_balances_usd:
                            total_balances_usd[symbol] = 0.0
                        total_balances_usd[symbol] += balance_usd
                        
                        if wallet_address not in token_balances:
                            token_balances[wallet_address] = {}
                        token_balances[wallet_address][symbol] = {
                            "balance": balance,
                            "balance_usd": balance_usd,
                            "decimals": decimals,
                            "raw_balance": raw_balance
                        }
            
            # Обрабатываем нативный баланс
            if "error" not in balance_result:
                native_balance_wei = float(balance_result.get("data", {}).get("balance", 0) or 0)
                # Конвертируем из wei в ETH (или другой нативный токен)
                native_balance = native_balance_wei / 1e18
                native_balances[wallet_address] = native_balance
        
        execution_log.append(f"✅ Получены балансы для {len(wallets)} кошельков")
        
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
        execution_log.append(f"❌ Ошибка при получении балансов: {str(e)}")
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
    execution_log.append("💰 Получение цен токенов...")
    
    try:
        tokens = state.get("tokens", [])
        current_portfolio = state.get("current_portfolio", {})
        
        if not current_portfolio:
            execution_log.append("⚠️ Портфель не найден, пропускаем получение цен")
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
            execution_log.append("⚠️ Нет токенов для получения цен")
            return {
                "token_prices": {},
                "execution_log": execution_log
            }
        
        token_prices = {}
        price_tool = GetTokenPriceTool()
        
        # Пытаемся получить цены через инструмент
        if price_tool:
            for token in all_tokens:
                try:
                    # Пробуем разные форматы символов
                    symbols_to_try = [
                        f"{token}-USDT",
                    ]
                    
                    price_found = False
                    for symbol in symbols_to_try:
                        try:
                            result = await price_tool.execute(
                                symbol=symbol
                            )
                            logger.info(result)
                            if isinstance(result, dict) and "price" in result:
                                token_prices[token] = float(result["price"])
                                price_found = True
                                break
                            elif isinstance(result, str):
                                import re
                                price_match = re.search(r'(\d+[.,]?\d*)', result)
                                if price_match:
                                    token_prices[token] = float(price_match.group(1).replace(',', ''))
                                    price_found = True
                                    break
                        except Exception as e:
                            logger.debug(f"Failed to get price for {symbol}: {e}")
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
                            token_prices[token] = balance_usd / total_amount
                            logger.debug(f"Calculated price for {token} from balance: {token_prices[token]}")
                
                except Exception as e:
                    logger.warning(f"Failed to get price for {token}: {e}")
                    continue
        
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
        
        execution_log.append(f"✅ Получены цены для {len(token_prices)} токенов")
        
        return {
            "token_prices": token_prices,
            "execution_log": execution_log
        }
    
    except Exception as e:
        logger.error(f"Error fetching prices: {e}", exc_info=True)
        execution_log.append(f"❌ Ошибка при получении цен: {str(e)}")
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
    execution_log.append("📈 Вычисление текущего распределения...")
    
    try:
        current_portfolio = state.get("current_portfolio", {})
        
        if not current_portfolio:
            execution_log.append("⚠️ Портфель не найден")
            return {
                "total_portfolio_value_usd": 0.0,
                "execution_log": execution_log
            }
        
        total_balances = current_portfolio.get("total_balances", {})
        
        if not total_balances:
            execution_log.append("⚠️ Балансы не найдены")
            return {
                "total_portfolio_value_usd": 0.0,
                "execution_log": execution_log
            }
        
        total_value_usd = sum(float(v) for v in total_balances.values() if v)
        
        if total_value_usd == 0:
            execution_log.append("⚠️ Портфель пуст или балансы равны нулю")
            return {
                "total_portfolio_value_usd": 0.0,
                "execution_log": execution_log
            }
        
        execution_log.append(f"💰 Общая стоимость портфеля: ${total_value_usd:,.2f}")
        
        return {
            "total_portfolio_value_usd": total_value_usd,
            "execution_log": execution_log
        }
    
    except Exception as e:
        logger.error(f"Error calculating allocation: {e}", exc_info=True)
        execution_log.append(f"❌ Ошибка при вычислении распределения: {str(e)}")
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
    execution_log.append("⚖️ Вычисление необходимости ребалансировки...")
    
    try:
        current_portfolio = state.get("current_portfolio", {})
        target_allocation = state.get("target_allocation", {})
        threshold_percent = state.get("threshold_percent", 5.0)
        
        if not current_portfolio:
            execution_log.append("⚠️ Портфель не найден, пропускаем вычисление ребалансировки")
            return {
                "rebalancing_actions": {"rebalancing_needed": False, "actions": []},
                "rebalancing_needed": False,
                "execution_log": execution_log
            }
        
        if not target_allocation:
            execution_log.append("⚠️ Целевое распределение не задано, пропускаем вычисление ребалансировки")
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
            execution_log.append(f"⚠️ Ошибка при вычислении: {result['error']}")
            return {
                "rebalancing_actions": {"rebalancing_needed": False, "actions": []},
                "rebalancing_needed": False,
                "execution_log": execution_log
            }
        
        rebalancing_needed = result.get("rebalancing_needed", False)
        actions_count = len(result.get("actions", []))
        
        if rebalancing_needed:
            execution_log.append(f"✅ Ребалансировка необходима: {actions_count} действий")
        else:
            execution_log.append("✅ Портфель сбалансирован, ребалансировка не требуется")
        
        return {
            "rebalancing_actions": result,
            "rebalancing_needed": rebalancing_needed,
            "execution_log": execution_log
        }
    
    except Exception as e:
        logger.error(f"Error calculating rebalancing: {e}", exc_info=True)
        execution_log.append(f"❌ Ошибка при вычислении ребалансировки: {str(e)}")
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
    execution_log.append("⛽ Оценка стоимости транзакций...")
    
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
            execution_log.append(f"⚠️ Не удалось оценить gas fees: {result['error']}")
            # Используем значения по умолчанию
            result = {
                "total_gas_usd": 50.0,
                "estimated_cost_per_tx_usd": 50.0 / num_transactions if num_transactions > 0 else 50.0
            }
        
        total_gas = result.get("total_gas_usd", 0)
        execution_log.append(f"💰 Оценка gas fees: ${total_gas:,.2f}")
        
        return {
            "gas_fees": result,
            "execution_log": execution_log
        }
    
    except Exception as e:
        logger.error(f"Error estimating gas fees: {e}", exc_info=True)
        execution_log.append(f"⚠️ Ошибка при оценке gas fees: {str(e)}")
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
    execution_log.append("💡 Предложение сделок для ребалансировки...")
    
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
            execution_log.append(f"❌ Ошибка: {result['error']}")
            return {
                "execution_log": execution_log,
                "error": result["error"]
            }
        
        should_rebalance = result.get("should_rebalance", False)
        net_benefit = result.get("net_benefit_usd", 0)
        
        if should_rebalance:
            execution_log.append(f"✅ Рекомендуется ребалансировка. Чистая выгода: ${net_benefit:,.2f}")
        else:
            execution_log.append(f"⚠️ Ребалансировка не рекомендуется. Чистая выгода: ${net_benefit:,.2f}")
        
        return {
            "suggested_trades": result,
            "execution_log": execution_log
        }
    
    except Exception as e:
        logger.error(f"Error suggesting trades: {e}", exc_info=True)
        execution_log.append(f"❌ Ошибка при предложении сделок: {str(e)}")
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
    execution_log.append("📋 Генерация финальной рекомендации...")
    
    rebalancing_needed = state.get("rebalancing_needed", False)
    suggested_trades = state.get("suggested_trades", {})
    total_portfolio_value = state.get("total_portfolio_value_usd", 0)
    gas_fees = state.get("gas_fees", {})
    
    recommendation_parts = []
    
    recommendation_parts.append("=" * 60)
    recommendation_parts.append("АНАЛИЗ РЕБАЛАНСИРОВКИ ПОРТФЕЛЯ")
    recommendation_parts.append("=" * 60)
    recommendation_parts.append(f"\n💰 Общая стоимость портфеля: ${total_portfolio_value:,.2f}")
    
    if rebalancing_needed:
        should_rebalance = suggested_trades.get("should_rebalance", False)
        net_benefit = suggested_trades.get("net_benefit_usd", 0)
        total_gas = gas_fees.get("total_gas_usd", 0)
        
        recommendation_parts.append(f"\n⚖️ Статус: Ребалансировка {'РЕКОМЕНДУЕТСЯ' if should_rebalance else 'НЕ РЕКОМЕНДУЕТСЯ'}")
        recommendation_parts.append(f"💵 Ожидаемая чистая выгода: ${net_benefit:,.2f}")
        recommendation_parts.append(f"⛽ Стоимость gas fees: ${total_gas:,.2f}")
        
        trades = suggested_trades.get("suggested_trades", [])
        if trades:
            recommendation_parts.append("\n📊 Предложенные сделки:")
            for i, trade in enumerate(trades, 1):
                token = trade.get("token", "N/A")
                action = trade.get("action", "N/A")
                amount = trade.get("amount_usd", 0)
                recommendation_parts.append(
                    f"  {i}. {action} {token}: ${amount:,.2f}"
                )
    else:
        recommendation_parts.append("\n✅ Портфель сбалансирован, ребалансировка не требуется")
    
    recommendation_parts.append("\n" + "=" * 60)
    
    recommendation = "\n".join(recommendation_parts)
    
    execution_log.append("✅ Рекомендация сгенерирована")
    
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
        print("РЕЗУЛЬТАТ АНАЛИЗА")
        print("=" * 60)
        print(result.get("recommendation", "Нет рекомендации"))
        print("\n" + "=" * 60)
        print("ЛОГ ВЫПОЛНЕНИЯ:")
        print("=" * 60)
        for log_entry in result.get("execution_log", []):
            print(log_entry)
    
    asyncio.run(test())

