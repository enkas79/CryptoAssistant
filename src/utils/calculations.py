"""
Calculations Module for CryptoAssistant
Handles all financial calculations (PMC, performance, target calculations).
"""

import pandas as pd
from typing import Dict, Tuple


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
    from src.data.models import COIN_COLORS, FALLBACK_COLORS
    
    values = []
    labels = []
    colors = []
    fallback_idx = 0
    
    mult = exchange_rate if currency == "EUR" else 1.0
    
    for token in df['Token'].unique():
        sub = df[df['Token'] == token]
        buys = sub[sub['Type'] == 'buy']
        sells = sub[sub['Type'] == 'sell']
        
        quantity = buys['Amount'].sum() - sells['Amount'].sum()
        if quantity <= 0.000001:
            continue
        
        # Calculate total invested (with currency conversion)
        total_invested = 0.0
        for _, row in buys.iterrows():
            price = row['Price']
            orig_curr = str(row.get('Original Currency', 'EUR'))
            
            if currency == "EUR" and orig_curr == "USD":
                # Convert from USD to EUR using historical rate (simplified here)
                # In the full app, this would use the historical rate for the transaction date
                total_invested += (row['Amount'] * price * exchange_rate) + (row['Fee'] * exchange_rate)
            else:
                total_invested += (row['Amount'] * price) + row['Fee']
        
        current_value = quantity * live_prices.get(token, 0) * mult
        
        if current_value > 0:
            values.append(current_value)
            labels.append(token)
            if token.upper() in COIN_COLORS:
                colors.append(COIN_COLORS[token.upper()])
            else:
                colors.append(FALLBACK_COLORS[fallback_idx % len(FALLBACK_COLORS)])
                fallback_idx += 1
    
    return values, labels, colors


def calculate_token_stats(
    df: pd.DataFrame,
    token: str,
    live_price: float,
    exchange_rate: float,
    currency: str = "EUR"
) -> Dict[str, float]:
    """
    Calculate statistics for a single token.
    
    Args:
        df (pd.DataFrame): DataFrame with transactions.
        token (str): Token symbol.
        live_price (float): Current price of the token.
        exchange_rate (float): Exchange rate (USD to EUR if currency is EUR).
        currency (str): Target currency (EUR or USD).
    
    Returns:
        Dict[str, float]: Dictionary with statistics (quantity, pmc, invested, current_value).
    """
    df_token = df[df['Token'] == token]
    buys = df_token[df_token['Type'] == 'buy']
    sells = df_token[df_token['Type'] == 'sell']
    
    quantity = buys['Amount'].sum() - sells['Amount'].sum()
    quantity_buys = buys['Amount'].sum()
    
    # Calculate total invested (with currency conversion)
    total_invested = 0.0
    for _, row in buys.iterrows():
        price = row['Price']
        orig_curr = str(row.get('Original Currency', 'EUR'))
        
        if currency == "EUR" and orig_curr == "USD":
            total_invested += (row['Amount'] * price * exchange_rate) + (row['Fee'] * exchange_rate)
        else:
            total_invested += (row['Amount'] * price) + row['Fee']
    
    pmc = (total_invested / quantity_buys) if quantity_buys > 0 else 0
    
    mult = exchange_rate if currency == "EUR" else 1.0
    current_value = quantity * live_price * mult
    
    return {
        'quantity': quantity,
        'pmc': pmc,
        'invested': total_invested,
        'current_value': current_value
    }


def calculate_target_quantity(
    current_quantity: float,
    current_pmc: float,
    target_pmc: float,
    market_price: float
) -> Tuple[float, float]:
    """
    Calculate the quantity to buy to reach a target PMC.
    
    Args:
        current_quantity (float): Current quantity of the token.
        current_pmc (float): Current PMC (Prezzo Medio di Carico).
        target_pmc (float): Target PMC to reach.
        market_price (float): Current market price.
    
    Returns:
        Tuple[float, float]: (quantity_to_buy, cost) or (0, 0) if not possible.
    """
    if market_price == target_pmc:
        return 0, 0  # Already at target
    
    try:
        quantity_to_buy = (current_quantity * (target_pmc - current_pmc)) / (market_price - target_pmc)
        if quantity_to_buy > 0:
            cost = quantity_to_buy * market_price
            return quantity_to_buy, cost
        else:
            return 0, 0  # Target not reachable
    except ZeroDivisionError:
        return 0, 0


def calculate_performance(
    invested: float,
    current_value: float
) -> Tuple[float, float]:
    """
    Calculate performance percentage and absolute difference.
    
    Args:
        invested (float): Total amount invested.
        current_value (float): Current value of the portfolio.
    
    Returns:
        Tuple[float, float]: (percentage, absolute_difference).
    """
    if invested > 0:
        percentage = ((current_value / invested) - 1) * 100
        difference = current_value - invested
        return percentage, difference
    return 0.0, 0.0
