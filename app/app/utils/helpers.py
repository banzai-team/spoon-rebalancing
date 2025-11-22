from typing import Any
import logging

logger = logging.getLogger(__name__)

# ==================== HELPER FUNCTIONS ====================

def convert_hex_balance_to_float(balance: Any, decimals: int = 18) -> float:
    """
    Конвертирует баланс из hex строки в число с учетом decimals
    
    Args:
        balance: Баланс в виде hex строки (например, '0x35f0a27d') или числа
        decimals: Количество десятичных знаков токена (по умолчанию 18)
    
    Returns:
        float: Баланс в человекочитаемом формате
    
    Examples:
        >>> convert_hex_balance_to_float('0x35f0a27d', 6)
        900.000125
        >>> convert_hex_balance_to_float('0xde0b6b3a7640000', 18)
        1.0
    """
    try:
        # Если balance уже число
        if isinstance(balance, (int, float)):
            return float(balance) / (10 ** decimals)
        
        # Если balance строка
        if isinstance(balance, str):
            # Если это hex строка (начинается с 0x)
            if balance.startswith('0x') or balance.startswith('0X'):
                # Конвертируем hex в int
                balance_int = int(balance, 16)
                # Учитываем decimals
                return float(balance_int) / (10 ** decimals)
            else:
                # Если это обычная строка с числом
                return float(balance) / (10 ** decimals)
        
        # Если это уже число
        return float(balance) / (10 ** decimals)
    
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to convert balance {balance} with decimals {decimals}: {e}")
        return 0.0
