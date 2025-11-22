"""
Конфигурация для агента ребалансировки портфеля
"""
from typing import Dict, List, Optional


class PortfolioConfig:
    """Класс для хранения конфигурации портфеля"""
    
    def __init__(self):
        # Целевое распределение портфеля (в процентах)
        self.target_allocation: Dict[str, float] = {
            "BTC": 40.0,
            "ETH": 35.0,
            "USDC": 25.0
        }
        
        # Порог отклонения для ребалансировки (в процентах)
        self.threshold_percent: float = 5.0
        
        # Минимальная прибыль в USD для выполнения ребалансировки
        self.min_profit_threshold_usd: float = 50.0
        
        # Режим работы агента: "consultation" или "autonomous"
        self.mode: str = "consultation"
        
        # Кошельки для мониторинга
        self.wallets: List[str] = [
            # Добавьте ваши адреса кошельков здесь
            # "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
        ]
        
        # Токены для отслеживания
        self.tokens: List[str] = ["BTC", "ETH", "USDC"]
        
        # Блокчейн по умолчанию
        self.default_chain: str = "ethereum"
        
        # Настройки для разных блокчейнов
        self.chains_config: Dict[str, Dict[str, any]] = {
            "ethereum": {
                "rpc_url": "https://eth.llamarpc.com",
                "native_token": "ETH",
                "gas_limit_swap": 150000,
                "gas_limit_transfer": 21000,
                "gas_limit_approve": 46000
            },
            "arbitrum": {
                "rpc_url": "https://arb1.arbitrum.io/rpc",
                "native_token": "ETH",
                "gas_limit_swap": 150000,
                "gas_limit_transfer": 21000,
                "gas_limit_approve": 46000
            },
            "polygon": {
                "rpc_url": "https://polygon-rpc.com",
                "native_token": "MATIC",
                "gas_limit_swap": 150000,
                "gas_limit_transfer": 21000,
                "gas_limit_approve": 46000
            }
        }
        
        # Настройки риска
        self.risk_tolerance: str = "moderate"  # "conservative", "moderate", "aggressive"
        
        # Максимальное отклонение от целевого распределения перед принудительной ребалансировкой
        self.max_deviation_percent: float = 20.0
        
        # Интервал проверки портфеля (в секундах)
        self.check_interval_seconds: int = 3600  # 1 час
        
        # Включить автоматическую ребалансировку
        self.auto_rebalance_enabled: bool = False
        
        # Минимальная стоимость портфеля для ребалансировки (в USD)
        self.min_portfolio_value_usd: float = 1000.0

    def get_target_allocation(self) -> Dict[str, float]:
        """Возвращает целевое распределение"""
        return self.target_allocation.copy()
    
    def set_target_allocation(self, allocation: Dict[str, float]):
        """Устанавливает целевое распределение"""
        total = sum(allocation.values())
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Сумма процентов должна быть 100%, получено {total}%")
        self.target_allocation = allocation
    
    def add_wallet(self, address: str):
        """Добавляет кошелек для мониторинга"""
        if address not in self.wallets:
            self.wallets.append(address)
    
    def remove_wallet(self, address: str):
        """Удаляет кошелек из мониторинга"""
        if address in self.wallets:
            self.wallets.remove(address)
    
    def get_chain_config(self, chain: str) -> Dict[str, any]:
        """Возвращает конфигурацию для указанного блокчейна"""
        return self.chains_config.get(chain, self.chains_config["ethereum"])
    
    def to_dict(self) -> Dict:
        """Преобразует конфигурацию в словарь"""
        return {
            "target_allocation": self.target_allocation,
            "threshold_percent": self.threshold_percent,
            "min_profit_threshold_usd": self.min_profit_threshold_usd,
            "mode": self.mode,
            "wallets": self.wallets,
            "tokens": self.tokens,
            "default_chain": self.default_chain,
            "risk_tolerance": self.risk_tolerance,
            "max_deviation_percent": self.max_deviation_percent,
            "check_interval_seconds": self.check_interval_seconds,
            "auto_rebalance_enabled": self.auto_rebalance_enabled,
            "min_portfolio_value_usd": self.min_portfolio_value_usd
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PortfolioConfig':
        """Создает конфигурацию из словаря"""
        config = cls()
        if "target_allocation" in data:
            config.target_allocation = data["target_allocation"]
        if "threshold_percent" in data:
            config.threshold_percent = data["threshold_percent"]
        if "min_profit_threshold_usd" in data:
            config.min_profit_threshold_usd = data["min_profit_threshold_usd"]
        if "mode" in data:
            config.mode = data["mode"]
        if "wallets" in data:
            config.wallets = data["wallets"]
        if "tokens" in data:
            config.tokens = data["tokens"]
        if "default_chain" in data:
            config.default_chain = data["default_chain"]
        if "risk_tolerance" in data:
            config.risk_tolerance = data["risk_tolerance"]
        if "max_deviation_percent" in data:
            config.max_deviation_percent = data["max_deviation_percent"]
        if "check_interval_seconds" in data:
            config.check_interval_seconds = data["check_interval_seconds"]
        if "auto_rebalance_enabled" in data:
            config.auto_rebalance_enabled = data["auto_rebalance_enabled"]
        if "min_portfolio_value_usd" in data:
            config.min_portfolio_value_usd = data["min_portfolio_value_usd"]
        return config


# Глобальный экземпляр конфигурации
default_config = PortfolioConfig()

