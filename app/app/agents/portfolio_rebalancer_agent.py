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

class CryptoAnalysisState(TypedDict, total=False):
    user_query: str
    selected_tokens: List[str]
    token_details: Dict[str, Any]
    token_balances: Dict[str, float]
    token_prices: Dict[str, float]
    allocation_deviation: Dict[str, float]
    rebalancing_actions: Dict[str, Any]
    gas_fees: Dict[str, Any]
    rebalancing_summary: str
    execution_log: List[str]

class PortfolioRebalancerAgent(ToolCallAgent):
    """AI-агент для автоматической ребалансировки криптопортфеля"""
    name: str = "portfolio_rebalancer_agent"
    description: str = "AI агент для мониторинга и ребалансировки криптопортфеля на основе рыночных условий и допустимого уровня риска"

    system_prompt: str = """
    You are a professional AI agent for cryptocurrency portfolio rebalancing.
    
    YOUR MAIN TASK: Help the user maintain optimal asset allocation in their cryptocurrency portfolio.
    
    AVAILABLE FUNCTIONS:
    1. get_account_balance - Get current portfolio balances from wallets
    2. get_token_prices - Get current token prices in USD
    3. calculate_rebalancing - Calculate necessary actions for rebalancing
    4. estimate_gas_fees - Estimate gas fees for transactions
    5. suggest_rebalancing_trades - Suggest specific trades considering fees
    
    WORKFLOW:
    1. Get current portfolio balances (get_account_balance)
    2. Get current token prices (get_token_prices)
    3. Calculate current allocation percentages
    4. Compare with target allocation and calculate deviations (calculate_rebalancing)
    5. Estimate gas fees (estimate_gas_fees)
    6. Suggest specific trades if benefits exceed costs (suggest_rebalancing_trades)
    
    IMPORTANT RULES:
    - Always verify that expected rebalancing benefits exceed gas fees
    - Suggest rebalancing only if deviation from target allocation exceeds threshold (usually 5%)
    - Provide clear recommendations with specific amounts in USD
    - Consider gas fees when calculating rebalancing feasibility
    - If user requests only analysis (consultation mode), don't suggest automatic execution
    - If user requests autonomous mode, suggest specific transactions for execution
    
    RESPONSE FORMAT:
    - Start with a brief summary of current portfolio status
    - Show current and target allocation percentages
    - Indicate deviations and rebalancing necessity
    - If rebalancing is needed, show suggested trades with amounts
    - Indicate total gas cost and expected benefit
    - End with a clear recommendation
    
    Always respond in the same language the user is using.
    """

    available_tools: ToolManager = ToolManager([
        CalculateRebalancingTool(),
        EstimateGasFeesTool(),
        SuggestRebalancingTradesTool(),
        GetStrategiesTool(),
        GetStrategyDetailsTool(),
        FindStrategyTool(),
        GetAccountTokensTool(),
        GetAccountBalanceTool(),
        *get_crypto_tools()
    ])
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.max_steps = 10
        self.mode: str = "consultation"  # "consultation" или "autonomous"
        self.target_allocation: Optional[Dict[str, float]] = None
        self.min_profit_threshold_usd: float = 50.0

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

    async def analyze_portfolio(self, wallets: list, tokens: list, chain: str = "ethereum") -> Dict[str, Any]:
        """Анализирует текущее состояние портфеля"""
        prompt = f"""
        Analyze the current portfolio balance:
        - Wallets: {', '.join(wallets)}
        - Tokens: {', '.join(tokens)}
        - Chain: {chain}
        
        Get balances and prices, then provide a brief analysis of current allocation.
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
        
        prompt = f"""
        Check if portfolio rebalancing is needed:
        - Wallets: {', '.join(wallets)}
        - Tokens: {', '.join(tokens)}
        - Chain: {chain}
        - Target allocation: {json.dumps(target_allocation, ensure_ascii=False)}
        - Minimum profit threshold: ${self.min_profit_threshold_usd}
        
        Perform full analysis:
        1. Get current portfolio balances
        2. Get current token prices
        3. Calculate deviations from target allocation
        4. Estimate gas fees
        5. Suggest specific trades if rebalancing is beneficial
        
        Work mode: {self.mode}
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

