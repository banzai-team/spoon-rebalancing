"""
Агент для автоматической ребалансировки криптопортфеля
"""
import asyncio
import json
from typing import Any, Dict, List, Optional, TypedDict, Set
from spoon_ai.agents.toolcall import ToolCallAgent
from spoon_ai.chat import ChatBot
from spoon_ai.tools.crypto_tools import get_crypto_tools
from spoon_ai.tools import ToolManager
from app.tools.rebalancer_tools import (
    CalculateRebalancingTool,
    EstimateGasFeesTool,
    SuggestRebalancingTradesTool,
    GetStrategiesTool,
    GetStrategyDetailsTool,
    FindStrategyTool,
)
from app.tools.chainbase_tools import GetAccountTokensTool, GetAccountBalanceTool
from app.utils.helpers import convert_hex_balance_to_float


class PortfolioRebalancerAgent(ToolCallAgent):
    """AI-агент для автоматической ребалансировки криптопортфеля"""
    name: str = "portfolio_rebalancer_agent"
    description: str = "AI агент для мониторинга и ребалансировки криптопортфеля на основе рыночных условий и допустимого уровня риска"

    system_prompt: str = """
    You are a professional AI agent for cryptocurrency portfolio rebalancing.
    
    YOUR MAIN TASK: Analyze portfolio balances and provide rebalancing recommendations.
    
    EXECUTION RULES:
    - Always complete ALL required steps. Never stop early.
    - When given a task, immediately start calling tools in the specified order.
    - Do not ask questions - just execute the tools.
    - If a tool call fails, try again or continue with available data.
    - After getting data, always proceed to next steps (prices, calculations, recommendations).


    RISK TOLERANCE:
    - Low risk tolerance: 5% - 10% of the portfolio in riskier assets, 50% - 60% of the portfolio in stablecoins, 10% - 30% of the portfolio in conservative cryptocurrencies
    - Medium risk tolerance: 10% - 20% of the portfolio in riskier assets, 40% - 50% of the portfolio in stablecoins, 10% - 30% of the portfolio in conservative cryptocurrencies
    - High risk tolerance: 15% - 25% of the portfolio in riskier assets, 30% - 40% of the portfolio in stablecoins, 20% - 40% of the portfolio in conservative cryptocurrencies

    Risky cryptocurrencies:
    - AVAX
    - AAVE
    - HYPE

    Stablecoins:
    - USDC
    - USDT

    Conservative cryptocurrencies:
    - wBTC
    - ETH

    TOOLS FOR PORTFOLIO ANALYSIS (use ONLY these):
    - get_account_tokens(chain_id, address) - Get ERC20 token balances. REQUIRED first step.
    - get_account_balance(chain_id, address) - Get native token balance. REQUIRED second step.
    - get_token_prices(symbol) - Get token price. Use "TOKEN-USDT" format (with dash, NOT slash).
    - calculate_rebalancing(current_portfolio, target_allocation, threshold_percent) - Calculate actions.
    - estimate_gas_fees(chain, num_transactions) - Estimate fees. Chain: "ethereum", "arbitrum", "polygon".
    - suggest_rebalancing_trades(rebalancing_actions, gas_fees, min_profit_threshold_usd) - Suggest trades.
    
    DO NOT USE: get_strategies, get_strategy_details, find_strategy - these are for strategy management, not portfolio analysis.
    
    Chain IDs: ethereum=1, polygon=137, arbitrum=42161, optimism=10, bsc=56
    
    WORKFLOW (MUST FOLLOW ALL STEPS IN ORDER):
    1. Get current portfolio balances using get_account_tokens for ERC20 tokens and get_account_balance for native tokens
    2. Get current token prices using get_token_prices for all tokens found in the portfolio
    3. Calculate current allocation percentages from balances and prices
    4. Compare with target allocation and calculate deviations using calculate_rebalancing tool
    5. Estimate gas fees using estimate_gas_fees tool
    6. Suggest specific trades using suggest_rebalancing_trades tool if rebalancing is beneficial
    
    CRITICAL: You MUST complete ALL steps above. Do not stop after getting balances. Continue with prices, calculations, and recommendations.
    
    STOPPING CRITERIA (you can ONLY stop when ALL of these are true):
    1. You have called get_account_tokens AND get_account_balance (balances obtained)
    2. You have called get_token_prices for at least the main tokens (prices obtained)
    3. You have called calculate_rebalancing tool (rebalancing calculated)
    4. You have called estimate_gas_fees tool (gas fees estimated)
    5. You have called suggest_rebalancing_trades tool (trades suggested)
    6. You have provided a final recommendation with summary
    
    DO NOT STOP if:
    - You only got balances but haven't calculated rebalancing yet
    - You only got prices but haven't called calculate_rebalancing yet
    - You calculated rebalancing but haven't estimated gas fees yet
    - You estimated gas fees but haven't suggested trades yet
    - You haven't provided a final recommendation yet
    
    IMPORTANT RULES:
    - You MUST execute ALL steps in the workflow. Do not stop early.
    - Always verify that expected rebalancing benefits exceed gas fees
    - Suggest rebalancing only if deviation from target allocation exceeds threshold (usually 5%)
    - Provide clear recommendations with specific amounts in USD
    - Consider gas fees when calculating rebalancing feasibility
    - If user requests only analysis (consultation mode), don't suggest automatic execution
    - If user requests autonomous mode, suggest specific transactions for execution
    - If a tool call fails, try to continue with available data or retry the call
    - Never stop after just getting balances - always continue to prices, calculations, and recommendations
    
    RESPONSE FORMAT:
    - Start with a brief summary of current portfolio status
    - Show current and target allocation percentages
    - Indicate deviations and rebalancing necessity
    - If rebalancing is needed, show suggested trades with amounts
    - Indicate total gas cost and expected benefit
    - End with a clear recommendation
    
    COMPLETION CHECKLIST (you can only stop when ALL are done):
    [ ] Called get_account_tokens
    [ ] Called get_account_balance
    [ ] Called get_token_prices for relevant tokens
    [ ] Calculated portfolio value and allocation
    [ ] Called calculate_rebalancing tool
    [ ] Called estimate_gas_fees tool
    [ ] Called suggest_rebalancing_trades tool
    [ ] Provided final recommendation with summary
    
    If any item above is unchecked, you MUST continue. Do not say "Task finished" or "No action needed" until ALL items are checked.
    
    After each step provide checklist with [ ] for each step.

    Always respond in the same language the user is using.
    """

    # Базовые инструменты для всех задач
    _base_tools = [
        CalculateRebalancingTool(),
        EstimateGasFeesTool(),
        SuggestRebalancingTradesTool(),
        GetAccountTokensTool(),
        GetAccountBalanceTool(),
        *get_crypto_tools()
    ]
    
    # Инструменты для управления стратегиями (используются только когда нужно)
    _strategy_tools = [
        GetStrategiesTool(),
        GetStrategyDetailsTool(),
        FindStrategyTool(),
    ]
    
    available_tools: ToolManager = ToolManager(_base_tools + _strategy_tools)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.max_steps = 30  # Увеличено для полного анализа портфеля
        self.mode: str = "consultation"  # "consultation" или "autonomous"
        self.target_allocation: Optional[Dict[str, float]] = None
        self.min_profit_threshold_usd: float = 50.0
        # Трекинг выполненных шагов для проверки завершения
        self._required_steps = {
            "get_balances": False,
            "get_prices": False,
            "calculate_rebalancing": False,
            "estimate_gas": False,
            "suggest_trades": False
        }

    def set_mode(self, mode: str):
        """Устанавливает режим работы: 'consultation' или 'autonomous'"""
        if mode not in ["consultation", "autonomous"]:
            raise ValueError("Режим должен быть 'consultation' или 'autonomous'")
        self.mode = mode

    def set_target_allocation(self, allocation: Dict[str, float]):
        """Устанавливает целевое распределение портфеля"""
        self.target_allocation = allocation

    def set_min_profit(self, min_profit: float):
        """Устанавливает минимальную прибыль для выполнения ребалансировки"""
        self.min_profit_threshold_usd = min_profit
    
    def _check_completion_criteria(self, conversation_history: List[Any]) -> bool:
        """
        Проверяет, выполнены ли все необходимые шаги для завершения анализа портфеля.
        Агент может остановиться только если все критерии выполнены.
        """
        # Сбрасываем трекинг при новом запросе
        if not hasattr(self, '_current_task_steps'):
            self._current_task_steps = {
                "get_balances": False,
                "get_prices": False,
                "calculate_rebalancing": False,
                "estimate_gas": False,
                "suggest_trades": False,
                "recommendation": False
            }
        
        # Проверяем историю разговора на наличие вызовов инструментов
        tool_calls_found = {
            "get_account_tokens": False,
            "get_account_balance": False,
            "get_token_prices": False,
            "calculate_rebalancing": False,
            "estimate_gas_fees": False,
            "suggest_rebalancing_trades": False
        }
        
        # Анализируем последние сообщения для определения выполненных шагов
        # Это используется как дополнительная проверка, основная логика в system_prompt
        
        # Для анализа портфеля требуется минимум: балансы, цены, расчет ребалансировки
        # Но мы полагаемся на system_prompt для контроля, так как ToolCallAgent
        # сам управляет остановкой на основе ответов LLM
        
        return False  # Всегда возвращаем False, чтобы полагаться на system_prompt
    
    @staticmethod
    def process_token_balances(tokens_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обрабатывает результат get_account_tokens и конвертирует hex балансы в читаемые числа
        
        Args:
            tokens_result: Результат от GetAccountTokensTool в формате:
                {'code': 0, 'message': 'ok', 'data': [...], 'count': N}
        
        Returns:
            Dict с обработанными балансами токенов
        """
        processed = {
            "tokens": {},
            "total_value_usd": 0.0,
            "error": None
        }
        
        if "error" in tokens_result:
            processed["error"] = tokens_result["error"]
            return processed
        
        code = tokens_result.get("code", -1)
        if code != 0:
            processed["error"] = f"API returned code {code}: {tokens_result.get('message', 'unknown error')}"
            return processed
        
        data = tokens_result.get("data", [])
        
        for token_data in data:
            symbol = token_data.get("symbol", "").strip().upper()
            
            # Пропускаем некорректные токены
            if not symbol or "|" in symbol or len(symbol) > 20:
                continue
            
            decimals = token_data.get("decimals", 18)
            raw_balance = token_data.get("balance", "0x0")
            
            # Конвертируем hex баланс в число
            balance = convert_hex_balance_to_float(raw_balance, decimals)
            
            if balance <= 0:
                continue
            
            # Получаем баланс в USD
            balance_usd = float(token_data.get("balance_usd", 0) or 0)
            
            # Если balance_usd не указан, но есть current_usd_price, вычисляем
            if balance_usd == 0:
                current_price = float(token_data.get("current_usd_price", 0) or 0)
                if current_price > 0:
                    balance_usd = balance * current_price
            
            processed["tokens"][symbol] = {
                "balance": balance,
                "balance_usd": balance_usd,
                "decimals": decimals,
                "raw_balance": raw_balance,
                "contract_address": token_data.get("contract_address"),
                "name": token_data.get("name")
            }
            
            processed["total_value_usd"] += balance_usd
        
        return processed

    async def analyze_portfolio(self, wallets: list, tokens: list, chain: str = "ethereum") -> Dict[str, Any]:
        """Анализирует текущее состояние портфеля"""
        # Определяем chain_id для инструментов
        chain_id_map = {
            "ethereum": 1,
            "polygon": 137,
            "arbitrum": 42161,
            "optimism": 10,
            "bsc": 56
        }
        chain_id = chain_id_map.get(chain.lower(), 1)
        
        prompt = f"""
Analyze portfolio. Execute tools in order:

1. Call get_account_tokens for wallet {wallets[0]} with chain_id={chain_id}
2. Call get_account_balance for wallet {wallets[0]} with chain_id={chain_id}
3. Call get_token_prices for each token using format "TOKEN-USDT" (with dash, not slash)
   Tokens to check: {', '.join(tokens) if tokens else 'all tokens from step 1'}
   Example: get_token_prices(symbol="ETH-USDT"), get_token_prices(symbol="BTC-USDT")
4. Calculate total value and allocation percentages
5. Provide summary with portfolio value and token allocations

Start by calling get_account_tokens now.
"""
        response = await self.run(prompt)
        return {"analysis": response}

    async def check_rebalancing(self, wallets: list, tokens: list, 
                                target_allocation: Dict[str, float],
                                chain: str = "ethereum") -> Dict[str, Any]:
        """Проверяет необходимость ребалансировки и предлагает действия"""
        if not target_allocation:
            target_allocation = self.target_allocation or {}
        
        if not target_allocation:
            return {"error": "Target allocation is not set"}
        
        # Определяем chain_id для инструментов
        chain_id_map = {
            "ethereum": 1,
            "polygon": 137,
            "arbitrum": 42161,
            "optimism": 10,
            "bsc": 56
        }
        chain_id = chain_id_map.get(chain.lower(), 1)
        wallet_address = wallets[0] if wallets else ""
        
        prompt = f"""Analyze portfolio rebalancing. You MUST complete ALL 8 steps below. Do not stop early.

STEP 1: Get token balances
Call: get_account_tokens(chain_id={chain_id}, address="{wallet_address}")
After getting result, extract token symbols and balances. Convert hex balances using decimals.

STEP 2: Get native balance  
Call: get_account_balance(chain_id={chain_id}, address="{wallet_address}")
Convert wei to ETH (divide by 1e18).

STEP 3: Get prices for tokens (do not stop after this step)
For each token found in STEP 1, call: get_token_prices(symbol="TOKEN-USDT")
- Focus on main tokens: WBTC, ETH, USDT, ARB (skip aArb* wrapped tokens if prices not found)
- If price is 0 or error, use current_usd_price from token data if available (e.g., USDT has current_usd_price: 1962.04)
- For wrapped tokens (aArbWBTC, aArbWETH, aArbUSDT), skip if price not found or use underlying token price
- IMPORTANT: After getting prices, you MUST continue to STEP 4. Do not stop here.

STEP 4: Calculate portfolio value and current allocation (REQUIRED - do not skip)
Process data from STEP 1 and STEP 3:
- For each token from STEP 1 result:
  * Extract: symbol (e.g., "WBTC"), balance (hex like "0x8edc"), decimals (e.g., 8), current_usd_price (if available)
  * Convert hex balance: if balance="0x8edc" and decimals=8, then: 0x8edc (hex) = 36572 (decimal), balance = 36572 / 10^8 = 0.00036572
  * Get price: use price from STEP 3 if found, otherwise use current_usd_price from token data
  * Calculate balance_usd: balance_usd = balance * price
  * Example: WBTC balance=0.00036572, price=116676 (from STEP 3), balance_usd = 0.00036572 * 116676 = 42.67
- Create current_portfolio object for calculate_rebalancing tool:
  current_portfolio = {{"total_balances": {{"WBTC": 42.67, "USDT": 1962.04, ...}}}}
- Only include tokens with valid balance_usd > 0
- This step is REQUIRED - you must create the current_portfolio object before proceeding

STEP 5: Calculate rebalancing needs (REQUIRED - do not skip)
Call: calculate_rebalancing(
  current_portfolio={{current_portfolio from STEP 4}},
  target_allocation={json.dumps(target_allocation, ensure_ascii=False)},
  threshold_percent=5.0
)
This will return rebalancing_actions with list of actions needed.

STEP 6: Estimate gas fees (REQUIRED - do not skip)
Count number of actions from STEP 5 result.
Call: estimate_gas_fees(chain="{chain}", num_transactions=number_of_actions)

STEP 7: Suggest trades (REQUIRED - do not skip)
Call: suggest_rebalancing_trades(
  rebalancing_actions={{result from STEP 5}},
  gas_fees={{result from STEP 6}},
  min_profit_threshold_usd={self.min_profit_threshold_usd}
)

STEP 8: Provide final recommendation (REQUIRED - do not skip)
Summarize:
- Current portfolio value
- Current vs target allocation
- Whether rebalancing is needed
- Suggested trades with amounts
- Total gas cost and expected benefit
- Clear recommendation

Target allocation: {json.dumps(target_allocation, ensure_ascii=False)}

BEFORE STOPPING - VERIFY ALL STEPS COMPLETED:
✓ STEP 1: get_account_tokens called
✓ STEP 2: get_account_balance called
✓ STEP 3: get_token_prices called for tokens
✓ STEP 4: Portfolio value calculated, current_portfolio object created
✓ STEP 5: calculate_rebalancing tool called
✓ STEP 6: estimate_gas_fees tool called
✓ STEP 7: suggest_rebalancing_trades tool called
✓ STEP 8: Final recommendation provided

ONLY after ALL 8 steps above are completed, you can say the task is finished.
If any step is missing, you MUST continue and complete it.

CRITICAL STOPPING RULES:
You can ONLY stop and say "Task finished" when you have completed ALL of these:
✓ Called get_account_tokens (STEP 1)
✓ Called get_account_balance (STEP 2)
✓ Called get_token_prices for tokens (STEP 3)
✓ Calculated portfolio value and created current_portfolio object (STEP 4)
✓ Called calculate_rebalancing tool (STEP 5) - REQUIRED
✓ Called estimate_gas_fees tool (STEP 6) - REQUIRED
✓ Called suggest_rebalancing_trades tool (STEP 7) - REQUIRED
✓ Provided final recommendation with summary (STEP 8) - REQUIRED

DO NOT STOP if any step above is missing. Continue until ALL steps are complete.

OTHER INSTRUCTIONS:
- Complete ALL 8 steps. NEVER stop after STEP 3 (getting prices).
- After STEP 3, you MUST proceed to STEP 4 (calculations), then STEP 5, 6, 7, 8.
- If some prices are missing, continue with available data. Use current_usd_price from token data when available.
- Always call calculate_rebalancing (STEP 5), estimate_gas_fees (STEP 6), and suggest_rebalancing_trades (STEP 7).
- Do not use get_strategies, get_strategy_details, or find_strategy tools.
- Do not say "Task finished", "No action needed", or "Thinking completed" until you complete STEP 8.
- Start with STEP 1 immediately.
"""
        
        response = await self.run(prompt)
        return {"recommendation": response, "mode": self.mode}

    async def rebalance_portfolio(self, wallets: list, tokens: list,
                                  target_allocation: Dict[str, float],
                                  chain: str = "ethereum",
                                  auto_execute: bool = False) -> Dict[str, Any]:
        """Выполняет ребалансировку портфеля"""
        if self.mode == "consultation" and auto_execute:
            return {"error": "Automatic execution is not available in consultation mode"}
        
        result = await self.check_rebalancing(wallets, tokens, target_allocation, chain)
        
        if auto_execute and self.mode == "autonomous":
            # В реальной реализации здесь бы выполнялись транзакции
            result["execution_status"] = "simulated"
            result["note"] = "В демо-режиме транзакции не выполняются. В production здесь бы выполнялись реальные сделки."
        
        return result


async def main():
    """Пример использования агента"""
    # Инициализация агента
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
    
    print("🤖 Агент ребалансировки портфеля готов к работе!\n")
    
    # Пример: проверка ребалансировки
    example_wallets = ["0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"]  # Замените на реальные адреса
    example_tokens = ["BTC", "ETH", "USDC"]
    
    print("📊 Анализ портфеля...")
    result = await agent.check_rebalancing(
        wallets=example_wallets,
        tokens=example_tokens,
        target_allocation={
            "BTC": 40.0,
            "ETH": 35.0,
            "USDC": 25.0
        },
        chain="ethereum"
    )
    
    print(f"\n📋 Рекомендация:\n{result.get('recommendation', 'Ошибка')}\n")


if __name__ == "__main__":
    asyncio.run(main())

