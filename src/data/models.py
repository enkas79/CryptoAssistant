"""
Data Models for CryptoAssistant
Defines the data structures for transactions and portfolio.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Transaction:
    """
    Represents a single cryptocurrency transaction (buy/sell).
    """
    date: datetime
    token: str
    transaction_type: str  # "buy" or "sell"
    amount: float
    price: float
    fee: float = 0.0
    notes: str = ""
    original_currency: str = "EUR"  # Currency of the price (EUR/USD)


@dataclass
class Portfolio:
    """
    Represents the current state of a user's cryptocurrency portfolio.
    """
    token: str
    quantity: float
    average_price: float  # PMC (Prezzo Medio di Carico)
    total_invested: float
    current_value: float = 0.0
    
    def performance(self) -> float:
        """Calculate performance percentage."""
        if self.total_invested == 0:
            return 0.0
        return ((self.current_value / self.total_invested) - 1) * 100


@dataclass
class CurrentData:
    """
    Holds temporary data for the current view (used in GUI).
    """
    pmc: float = 0.0
    quantity: float = 0.0
    total_cost: float = 0.0
    invested: float = 0.0


# Coin colors for visualization
COIN_COLORS = {
    'BTC': '#F7931A', 'ETH': '#627EEA', 'USDT': '#26A17B', 'BNB': '#F3BA2F',
    'SOL': '#14F195', 'XRP': '#23292F', 'USDC': '#2775CA', 'ADA': '#0033AD',
    'AVAX': '#E84142', 'DOGE': '#C2A633', 'TRX': '#EF0027', 'LINK': '#2A5ADA',
    'DOT': '#E6007A', 'MATIC': '#8247E5', 'LTC': '#345D9D', 'SHIB': '#FFA409',
    'BCH': '#8DC351', 'ATOM': '#2E3148', 'XLM': '#14B6E7', 'XMR': '#FF6600',
    'ALGO': '#000000', 'UNI': '#FF007A', 'NEAR': '#000000', 'APT': '#000000',
    'FIL': '#0090FF', 'HBAR': '#3C454A', 'ICP': '#29ABE2', 'LDO': '#F07A55',
    'ARB': '#2D374B', 'VET': '#15BDFF', 'QNT': '#000000', 'MKR': '#1AAB9B',
    'TON': '#0098EA', 'VSN': '#131A26', 'NEXO': '#1E4DD8', 'ETC': '#34FA99'
}

FALLBACK_COLORS = [
    '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4', 
    '#46f0f0', '#f032e6', '#bcf60c', '#fabebe', '#008080', '#e6beff', 
    '#9a6324', '#fffac8', '#800000', '#aaffc3', '#808000', '#ffd8b1', 
    '#000075', '#808080', '#000000'
]
