"""
Инструменты для ребалансировки портфеля
"""
import asyncio
from typing import Dict, List, Optional, Any
from spoon_ai.tools.base import BaseTool
from spoon_ai.tools.crypto_tools import get_crypto_tools
from web3 import Web3
import json
import uuid
import logging

logger = logging.getLogger(__name__)


class CalculateRebalancingTool(BaseTool):
    """Tool for calculating necessary rebalancing actions"""
    name: str = "calculate_rebalancing"
    description: str = "Calculates necessary trades for portfolio rebalancing based on current balances and target percentages"
    parameters: dict = {
        "type": "object",
        "properties": {
            "current_portfolio": {
                "type": "object",
                "description": "Current portfolio with balances in USD (JSON string)"
            },
            "target_allocation": {
                "type": "object",
                "description": "Target allocation in percentages (e.g., {'BTC': 40, 'ETH': 35, 'USDC': 25})"
            },
            "threshold_percent": {
                "type": "number",
                "description": "Deviation threshold in percentage that requires rebalancing (default 5%)",
                "default": 5.0
            }
        },
        "required": ["current_portfolio", "target_allocation"]
    }

    async def execute(self, current_portfolio: Dict[str, Any], target_allocation: Dict[str, float], 
                     threshold_percent: float = 5.0, **kwargs) -> str:
        """Calculates necessary actions for rebalancing"""
        try:
            # Parse current portfolio if it's a string
            if isinstance(current_portfolio, str):
                current_portfolio = json.loads(current_portfolio)
            
            # Calculate total portfolio value
            total_value_usd = sum(current_portfolio.get("total_balances", {}).values())
            
            if total_value_usd == 0:
                return json.dumps({"error": "Portfolio is empty or failed to get balances"}, ensure_ascii=False)
            
            # Normalize target percentages (should sum to 100)
            total_target = sum(target_allocation.values())
            if total_target != 100:
                # Normalize
                for token in target_allocation:
                    target_allocation[token] = (target_allocation[token] / total_target) * 100
            
            # Calculate current and target values
            rebalancing_actions = []
            current_balances = current_portfolio.get("total_balances", {})
            
            for token, target_percent in target_allocation.items():
                current_value = current_balances.get(token, 0.0)
                current_percent = (current_value / total_value_usd) * 100 if total_value_usd > 0 else 0
                target_value = (target_percent / 100) * total_value_usd
                
                deviation = current_percent - target_percent
                
                # Check if rebalancing is needed
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
            return json.dumps({"error": f"Error calculating rebalancing: {str(e)}"}, ensure_ascii=False)


class EstimateGasFeesTool(BaseTool):
    """Tool for estimating gas fees"""
    name: str = "estimate_gas_fees"
    description: str = "Estimates gas fees for rebalancing transactions"
    parameters: dict = {
        "type": "object",
        "properties": {
            "chain": {
                "type": "string",
                "description": "Blockchain (ethereum, arbitrum, polygon)",
                "default": "ethereum"
            },
            "num_transactions": {
                "type": "integer",
                "description": "Number of transactions to execute",
                "default": 1
            }
        },
        "required": []
    }

    async def execute(self, chain: str = "ethereum", num_transactions: int = 1, **kwargs) -> str:
        """Estimates gas fees"""
        try:
            rpc_endpoints = {
                "ethereum": "https://eth.llamarpc.com",
                "arbitrum": "https://arb1.arbitrum.io/rpc",
                "polygon": "https://polygon-rpc.com"
            }
            
            rpc_url = rpc_endpoints.get(chain.lower(), rpc_endpoints["ethereum"])
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            
            if not w3.is_connected():
                return json.dumps({"error": f"Failed to connect to network {chain}"}, ensure_ascii=False)
            
            # Get current gas price
            gas_price_wei = w3.eth.gas_price
            gas_price_gwei = w3.from_wei(gas_price_wei, 'gwei')
            
            # Average gas limits for different operations
            # Swap: ~150k, Transfer: ~21k, Approve: ~46k
            avg_gas_limit = 150000  # For swap operations
            
            total_gas_wei = gas_price_wei * avg_gas_limit * num_transactions
            total_gas_eth = w3.from_wei(total_gas_wei, 'ether')
            
            # Get ETH price for USD conversion
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
            logger.error(f"Error estimating gas fees: {e}", exc_info=True)
            return json.dumps({"error": f"Error estimating gas fees: {str(e)}"}, ensure_ascii=False)


class SuggestRebalancingTradesTool(BaseTool):
    """Tool for suggesting specific trades for rebalancing"""
    name: str = "suggest_rebalancing_trades"
    description: str = "Suggests specific trades for rebalancing considering gas fees"
    parameters: dict = {
        "type": "object",
        "properties": {
            "rebalancing_actions": {
                "type": "object",
                "description": "Result of rebalancing calculation (JSON string)"
            },
            "gas_fees": {
                "type": "object",
                "description": "Gas fees estimate (JSON string)"
            },
            "min_profit_threshold_usd": {
                "type": "number",
                "description": "Minimum profit in USD to execute rebalancing (default 50 USD)",
                "default": 50.0
            }
        },
        "required": ["rebalancing_actions", "gas_fees"]
    }

    async def execute(self, rebalancing_actions: Dict[str, Any], gas_fees: Dict[str, Any],
                     min_profit_threshold_usd: float = 50.0, **kwargs) -> str:
        """Suggests specific trades"""
        try:
            # Parse input data if it's strings
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
                # Expected benefit from rebalancing (simplified model)
                # In reality, this should consider volatility and correlations
                expected_benefit = amount_usd * 0.02  # Assume 2% benefit from rebalancing
                
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
            logger.error(f"Error suggesting trades: {e}", exc_info=True)
            return json.dumps({"error": f"Error suggesting trades: {str(e)}"}, ensure_ascii=False)


class GetStrategiesTool(BaseTool):
    """Tool for getting user's strategies"""
    name: str = "get_strategies"
    description: str = "Get list of all strategies for the current user. Returns strategies with their IDs, names, descriptions, and associated wallets."
    parameters: dict = {
        "type": "object",
        "properties": {
            "search_query": {
                "type": "string",
                "description": "Optional search query to filter strategies by name or description"
            }
        },
        "required": []
    }

    async def execute(self, search_query: Optional[str] = None, **kwargs) -> str:
        """Gets list of strategies"""
        try:
            from app.db import get_db, get_user_id
            from app.db.models import Strategy, StrategyWallet
            from sqlalchemy.orm import Session
            
            # Get user ID and database session
            user_id = get_user_id()
            db: Session = next(get_db())
            
            try:
                # Query strategies
                query = db.query(Strategy).filter(Strategy.user_id == user_id)
                
                # Apply search filter if provided
                if search_query:
                    search_pattern = f"%{search_query}%"
                    query = query.filter(
                        (Strategy.name.ilike(search_pattern)) |
                        (Strategy.description.ilike(search_pattern))
                    )
                
                strategies = query.all()
                
                result = []
                for strategy in strategies:
                    # Get wallets for this strategy
                    wallet_links = db.query(StrategyWallet).filter(
                        StrategyWallet.strategy_id == strategy.id
                    ).all()
                    wallet_ids = [str(sw.wallet_id) for sw in wallet_links]
                    
                    result.append({
                        "id": str(strategy.id),
                        "name": str(strategy.name),
                        "description": str(strategy.description),
                        "wallet_ids": wallet_ids,
                        "created_at": strategy.created_at.isoformat() if strategy.created_at is not None else None,
                        "updated_at": strategy.updated_at.isoformat() if strategy.updated_at is not None else None
                    })
                
                logger.debug(f"Retrieved {len(result)} strategies for user {user_id}")
                return json.dumps({"strategies": result, "count": len(result)}, ensure_ascii=False, indent=2)
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error getting strategies: {e}", exc_info=True)
            return json.dumps({"error": f"Error getting strategies: {str(e)}"}, ensure_ascii=False)


class GetStrategyDetailsTool(BaseTool):
    """Tool for getting detailed information about a specific strategy"""
    name: str = "get_strategy_details"
    description: str = "Get detailed information about a specific strategy by its ID, including wallets, description, and metadata."
    parameters: dict = {
        "type": "object",
        "properties": {
            "strategy_id": {
                "type": "string",
                "description": "ID of the strategy to get details for"
            }
        },
        "required": ["strategy_id"]
    }

    async def execute(self, strategy_id: str, **kwargs) -> str:
        """Gets strategy details"""
        try:
            from app.db import get_db, get_user_id
            from app.db.models import Strategy, StrategyWallet, Wallet
            from sqlalchemy.orm import Session
            
            # Get user ID and database session
            user_id = get_user_id()
            db: Session = next(get_db())
            
            try:
                # Parse strategy ID
                try:
                    strategy_uuid = uuid.UUID(strategy_id)
                except ValueError:
                    return json.dumps({"error": "Invalid strategy ID format"}, ensure_ascii=False)
                
                # Get strategy
                strategy = db.query(Strategy).filter(
                    Strategy.id == strategy_uuid,
                    Strategy.user_id == user_id
                ).first()
                
                if not strategy:
                    return json.dumps({"error": "Strategy not found"}, ensure_ascii=False)
                
                # Get wallets for this strategy
                wallet_links = db.query(StrategyWallet).filter(
                    StrategyWallet.strategy_id == strategy.id
                ).all()
                
                wallets_info = []
                for wallet_link in wallet_links:
                    wallet = db.query(Wallet).filter(
                        Wallet.id == wallet_link.wallet_id,
                        Wallet.user_id == user_id
                    ).first()
                    if wallet:
                        wallet_label = str(wallet.label) if wallet.label is not None else None
                        wallet_tokens = wallet.tokens if wallet.tokens is not None else []
                        wallets_info.append({
                            "id": str(wallet.id),
                            "address": str(wallet.address),
                            "chain": str(wallet.chain),
                            "label": wallet_label,
                            "tokens": wallet_tokens
                        })
                
                result = {
                    "id": str(strategy.id),
                    "name": str(strategy.name),
                    "description": str(strategy.description),
                    "wallets": wallets_info,
                    "created_at": strategy.created_at.isoformat() if strategy.created_at is not None else None,
                    "updated_at": strategy.updated_at.isoformat() if strategy.updated_at is not None else None
                }
                
                logger.debug(f"Retrieved strategy details: {strategy_id} for user {user_id}")
                return json.dumps(result, ensure_ascii=False, indent=2)
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error getting strategy details for {strategy_id}: {e}", exc_info=True)
            return json.dumps({"error": f"Error getting strategy details: {str(e)}"}, ensure_ascii=False)


class FindStrategyTool(BaseTool):
    """Tool for finding a strategy by name or description"""
    name: str = "find_strategy"
    description: str = "Find a strategy by searching in its name or description. Useful when user mentions a strategy but doesn't know its exact ID."
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query to find strategy by name or description"
            }
        },
        "required": ["query"]
    }

    async def execute(self, query: str, **kwargs) -> str:
        """Finds strategy by search query"""
        try:
            from app.db import get_db, get_user_id
            from app.db.models import Strategy
            from sqlalchemy.orm import Session
            
            # Get user ID and database session
            user_id = get_user_id()
            db: Session = next(get_db())
            
            try:
                # Search in name and description
                search_pattern = f"%{query}%"
                strategies = db.query(Strategy).filter(
                    Strategy.user_id == user_id,
                    (Strategy.name.ilike(search_pattern)) |
                    (Strategy.description.ilike(search_pattern))
                ).all()
                
                if not strategies:
                    return json.dumps({"message": "No strategies found", "strategies": []}, ensure_ascii=False, indent=2)
                
                result = []
                for strategy in strategies:
                    result.append({
                        "id": str(strategy.id),
                        "name": str(strategy.name),
                        "description": str(strategy.description),
                        "created_at": strategy.created_at.isoformat() if strategy.created_at is not None else None
                    })
                
                logger.debug(f"Found {len(result)} strategies matching query '{query}' for user {user_id}")
                return json.dumps({"strategies": result, "count": len(result)}, ensure_ascii=False, indent=2)
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error finding strategy with query '{query}': {e}", exc_info=True)
            return json.dumps({"error": f"Error finding strategy: {str(e)}"}, ensure_ascii=False)


class CreateStrategyTool(BaseTool):
    """Tool for creating a new strategy in the database"""
    name: str = "create_strategy"
    description: str = "Create a new portfolio rebalancing strategy. Used only if user intends to create a new strategy. Use this when a strategy mentioned by the user doesn't exist yet.."
    parameters: dict = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name for the strategy (optional, will be auto-generated if not provided)"
            },
            "description": {
                "type": "string",
                "description": "Description of desired management for the portfolio"
            },
            "wallet_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of wallet IDs to associate with this strategy"
            }
        },
        "required": ["description"]
    }

    async def execute(self, description: str, name: Optional[str] = None, wallet_ids: Optional[List[str]] = None, **kwargs) -> str:
        """Creates a new strategy"""
        try:
            from app.db import get_db, get_user_id
            from app.services.strategy_service import StrategyService
            from app.api.schemas import StrategyCreate
            from sqlalchemy.orm import Session
            from datetime import datetime
            
            # Get user ID and database session
            user_id = get_user_id()
            db: Session = next(get_db())
            
            try:
                # Generate name if not provided
                if not name:
                    name = f"Strategy from {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
                
                # Validate wallet IDs if provided
                validated_wallet_ids = []
                if wallet_ids:
                    from app.db.models import Wallet
                    for wallet_id in wallet_ids:
                        try:
                            wallet_uuid = uuid.UUID(wallet_id)
                            wallet = db.query(Wallet).filter(
                                Wallet.id == wallet_uuid,
                                Wallet.user_id == user_id
                            ).first()
                            if wallet:
                                validated_wallet_ids.append(wallet_id)
                        except ValueError:
                            # Invalid UUID format, skip
                            pass
                
                # Create strategy using StrategyService
                # Note: StrategyCreate requires wallet_ids, so we pass empty list if none provided
                strategy_create = StrategyCreate(
                    name=name,
                    description=description,
                    wallet_ids=validated_wallet_ids if validated_wallet_ids else []
                )
                
                try:
                    strategy_response = await StrategyService.create_strategy(db, strategy_create, user_id)
                except Exception as e:
                    # Handle HTTPException and other errors from StrategyService
                    from fastapi import HTTPException
                    error_msg = str(e)
                    if isinstance(e, HTTPException):
                        error_msg = e.detail
                    return json.dumps({"error": f"Failed to create strategy: {error_msg}"}, ensure_ascii=False)
                
                result = {
                    "success": True,
                    "message": "Strategy created successfully",
                    "strategy": {
                        "id": strategy_response.id,
                        "name": strategy_response.name,
                        "description": strategy_response.description,
                        "wallet_ids": strategy_response.wallet_ids,
                        "created_at": strategy_response.created_at,
                        "updated_at": strategy_response.updated_at
                    }
                }
                
                logger.info(f"Strategy created: {strategy_response.id} (name: {name}, user_id: {user_id})")
                return json.dumps(result, ensure_ascii=False, indent=2)
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error creating strategy: {e}", exc_info=True)
            return json.dumps({"error": f"Error creating strategy: {str(e)}"}, ensure_ascii=False)

