"""
Calculations Module for CryptoAssistant
Handles all financial calculations (PMC, performance, target calculations).
"""

import pandas as pd
from typing import Dict, Tuple
from data.models import COIN_COLORS, FALLBACK_COLORS


def calculate_portfolio_allocation(
    df: pd.DataFrame,
    live_prices: Dict[str, float],
    exchange_rate: float,
    currency: str = "EUR"
) -> Tuple[list, list, list]:
    """
    Calculate portfolio allocation for pie chart visualization.
    
    Args:
        df (pd.DataFrame): DataFrame with transactions.
        live_prices (Dict[str, float]): Current prices for each token.
        exchange_rate (float): Exchange rate (USD to EUR if currency is EUR).
        currency (str): Target currency (EUR or USD).
    
    Returns:
        Tuple[list, list, list]: (values, labels, colors) for pie chart.
    """
    values = []
    labels = []
    colors = []
    fallback_idx = 0
    
    mult = exchange_rate if currency == "EUR" else 1.0
    
    for token in df['Token'].unique():
        sub = df[df['Token'] == token]
        buys = sub[sub['Type'] == 'buy']
        sells = sub[sub['Type'] == 'sell']
