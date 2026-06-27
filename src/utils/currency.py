"""
Currency Module for CryptoAssistant
Handles currency conversion and exchange rate management.
"""

from datetime import datetime
from typing import Dict, Optional


class CurrencyConverter:
    """
    Manages currency conversion with historical and live exchange rates.
    """
    
    def __init__(self, default_currency: str = "EUR"):
        """
        Initialize the converter.
        
        Args:
            default_currency (str): Default currency (EUR or USD).
        """
        self.default_currency = default_currency
        self.historical_rates: Dict[str, float] = {}  # {date_str: rate}
        self.live_rate: float = 0.92  # Fallback rate (USD to EUR)
    
    def set_historical_rates(self, rates: Dict[str, float]) -> None:
        """
        Set historical exchange rates.
        
        Args:
            rates (Dict[str, float]): Dictionary of {date_str: rate}.
        """
        self.historical_rates = rates
    
    def set_live_rate(self, rate: float) -> None:
        """
        Set the live exchange rate.
        
        Args:
            rate (float): Live exchange rate (USD to EUR).
        """
        self.live_rate = rate
    
    def get_rate_for_date(self, date_obj: datetime) -> float:
        """
        Get the exchange rate for a specific date.
        
        Args:
            date_obj (datetime): Date for which to get the rate.
        
        Returns:
            float: Exchange rate for the date, or live rate if not found.
        """
        if self.default_currency == "USD":
            return 1.0  # No conversion needed
        
        try:
            date_str = date_obj.strftime("%Y-%m-%d")
            if date_str in self.historical_rates:
                return self.historical_rates[date_str]
        except Exception:
            pass
        
        return self.live_rate
    
    def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        date: Optional[datetime] = None
    ) -> float:
        """
        Convert an amount from one currency to another.
        
        Args:
            amount (float): Amount to convert.
            from_currency (str): Source currency (EUR or USD).
            to_currency (str): Target currency (EUR or USD).
            date (Optional[datetime]): Date for historical rate (optional).
        
        Returns:
            float: Converted amount.
        """
        if from_currency == to_currency:
            return amount
        
        if from_currency == "USD" and to_currency == "EUR":
            if date:
                return amount * self.get_rate_for_date(date)
            return amount * self.live_rate
        
        if from_currency == "EUR" and to_currency == "USD":
            if date:
                return amount / self.get_rate_for_date(date)
            return amount / self.live_rate
        
        return amount  # Fallback
