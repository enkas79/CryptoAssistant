"""
Calculations Module for CryptoAssistant
Handles all financial calculations (PMC, performance, target calculations).
"""

import pandas as pd
from typing import Callable, Dict, Optional, Tuple


def _rate_for_row(row, exchange_rate: float, rate_for_date: Optional[Callable] = None) -> float:
    """Tasso USD->EUR da usare per una riga: quello storico alla data della
    transazione se è disponibile un lookup, altrimenti quello (odierno)
    passato come fallback."""
    if rate_for_date is not None:
        try:
            return rate_for_date(row['Date (UTC+1:00)'])
        except Exception:
            pass
    return exchange_rate


def _cost_basis_and_quantity(
    df_token: pd.DataFrame,
    exchange_rate: float,
    currency: str = "EUR",
    rate_for_date: Optional[Callable] = None
) -> Tuple[float, float]:
    """
    Calcola quantità detenuta e relativo costo base (PMC) con il metodo del
    costo medio ponderato, processando le transazioni in ordine cronologico:
    un acquisto aumenta quantità e costo, una vendita riduce entrambi in
    proporzione (al costo medio del momento), invece di sommare il costo di
    TUTTI gli acquisti storici anche per la parte poi rivenduta (il che
    gonfierebbe l'importo investito e falserebbe il calcolo di performance).

    Args:
        df_token (pd.DataFrame): Transazioni di un singolo token.
        exchange_rate (float): Tasso di cambio USD->EUR odierno, usato come
            fallback quando rate_for_date non è fornito o non ha un valore
            per la data della transazione.
        currency (str): Valuta di destinazione (EUR o USD).
        rate_for_date (Optional[Callable]): Funzione data->tasso storico
            USD->EUR. Fondamentale per acquisti in USD di anni fa: usare il
            tasso odierno per convertirli falsa pesantemente il costo base
            (e quindi la performance) quando il cambio si è mosso molto.

    Returns:
        Tuple[float, float]: (quantità detenuta, costo base della quantità detenuta).
    """
    df_sorted = df_token
    if 'Date (UTC+1:00)' in df_token.columns:
        df_sorted = df_token.sort_values('Date (UTC+1:00)', kind='stable')

    quantity = 0.0
    cost_basis = 0.0

    for _, row in df_sorted.iterrows():
        amount = row['Amount']
        tx_type = str(row['Type']).lower()

        if tx_type == 'buy':
            price = row['Price']
            orig_curr = str(row.get('Original Currency', 'EUR'))
            if currency == "EUR" and orig_curr == "USD":
                rate = _rate_for_row(row, exchange_rate, rate_for_date)
                cost_row = (amount * price * rate) + (row['Fee'] * rate)
            else:
                cost_row = (amount * price) + row['Fee']
            quantity += amount
            cost_basis += cost_row
        elif tx_type == 'sell':
            if quantity > 0:
                avg_cost = cost_basis / quantity
                cost_basis -= avg_cost * min(amount, quantity)
            quantity -= amount

    return max(quantity, 0.0), max(cost_basis, 0.0)


def calculate_cmc_style_stats(
    df_token: pd.DataFrame,
    live_price: float,
    exchange_rate: float,
    currency: str = "EUR",
    rate_for_date: Optional[Callable] = None,
) -> Dict[str, float]:
    """
    Statistiche di un token con lo stesso metodo del portafoglio di
    CoinMarketCap (vedi articolo ufficiale "How CMC Calculates Your Portfolio
    Profits"):

    - **media ponderata**, ma il costo base NON viene ridotto dalle vendite;
    - P/L = realizzato + non realizzato (all-time), non solo il non realizzato
      sul posseduto attuale;
    - percentuale calcolata sul costo base totale.

    Formule:
        Costo base       = Σ(prezzo_acq × qta_acq) + Σ(fee_acq)
        Prezzo medio     = Costo base / Σ(qta_acq)
        Realizzato       = Σ(prezzo_ven × qta_ven) − Prezzo medio × Σ(qta_ven) − Σ(fee_ven)
        Non realizzato   = (prezzo_corrente − Prezzo medio) × qta_posseduta
        P/L totale       = Realizzato + Non realizzato
        P/L %            = P/L totale / Costo base

    Le righe di vendita a prezzo 0 (trasferimenti tra wallet) riducono la
    quantità posseduta ma non entrano nel realizzato. Gli acquisti a prezzo 0
    (reward/airdrop non ancora valorizzati) abbassano il prezzo medio finché
    non vengono rivalutati.

    Returns:
        Dict con quantity, avg_buy_price, cost_basis, realized_pl,
        unrealized_pl, current_value, total_pl, total_pl_pct.
    """
    df = df_token
    mult = exchange_rate if currency == "EUR" else 1.0

    cost_basis = 0.0
    total_buy_amount = 0.0
    total_sell_amount = 0.0
    proceeds = 0.0
    sell_fees = 0.0
    priced_sell_amount = 0.0

    for _, row in df.iterrows():
        amount = row['Amount']
        price = row['Price']
        tx_type = str(row['Type']).lower()
        orig_curr = str(row.get('Original Currency', 'EUR'))
        rate = _rate_for_row(row, exchange_rate, rate_for_date) if (
            currency == "EUR" and orig_curr == "USD"
        ) else 1.0

        if tx_type == 'buy':
            cost_basis += (amount * price * rate) + (row['Fee'] * rate)
            total_buy_amount += amount
        elif tx_type == 'sell':
            total_sell_amount += amount
            if price > 0:
                proceeds += amount * price * rate
                sell_fees += row['Fee'] * rate
                priced_sell_amount += amount

    avg_buy_price = (cost_basis / total_buy_amount) if total_buy_amount > 0 else 0.0
    realized_pl = proceeds - (avg_buy_price * priced_sell_amount) - sell_fees

    quantity = max(total_buy_amount - total_sell_amount, 0.0)
    price_eur = (live_price or 0.0) * mult
    current_value = quantity * price_eur
    unrealized_pl = (price_eur - avg_buy_price) * quantity

    total_pl = realized_pl + unrealized_pl
    total_pl_pct = (total_pl / cost_basis * 100) if cost_basis > 0 else 0.0

    return {
        'quantity': quantity,
        'avg_buy_price': avg_buy_price,
        'cost_basis': cost_basis,
        'realized_pl': realized_pl,
        'unrealized_pl': unrealized_pl,
        'current_value': current_value,
        'total_pl': total_pl,
        'total_pl_pct': total_pl_pct,
    }


def calculate_portfolio_cmc_style(
    df: pd.DataFrame,
    live_prices: Dict[str, float],
    exchange_rate: float,
    currency: str = "EUR",
    rate_for_date: Optional[Callable] = None,
) -> Dict[str, float]:
    """
    Aggrega `calculate_cmc_style_stats` su tutto il portafoglio.

    Returns:
        Dict con cost_basis, realized_pl, unrealized_pl, current_value,
        total_pl, total_pl_pct (percentuale sul costo base complessivo).
    """
    tot = {
        'cost_basis': 0.0, 'realized_pl': 0.0, 'unrealized_pl': 0.0,
        'current_value': 0.0, 'total_pl': 0.0,
    }
    for token in df['Token'].unique():
        s = calculate_cmc_style_stats(
            df[df['Token'] == token], live_prices.get(token, 0) or 0,
            exchange_rate, currency, rate_for_date,
        )
        for k in tot:
            tot[k] += s[k]
    tot['total_pl_pct'] = (
        tot['total_pl'] / tot['cost_basis'] * 100 if tot['cost_basis'] > 0 else 0.0
    )
    return tot


def calculate_portfolio_allocation(
    df: pd.DataFrame,
    live_prices: Dict[str, float],
    exchange_rate: float,
    currency: str = "EUR",
    dust_threshold: float = 0.0,
    rate_for_date: Optional[Callable] = None
) -> Tuple[list, list, list, list, list]:
    """
    Calculate portfolio allocation for pie chart visualization.

    Args:
        df (pd.DataFrame): DataFrame with transactions.
        live_prices (Dict[str, float]): Current prices for each token.
        exchange_rate (float): Exchange rate (USD to EUR if currency is EUR).
        currency (str): Target currency (EUR or USD).
        dust_threshold (float): Asset con valore corrente inferiore a questa
            soglia (nella valuta indicata) vengono esclusi dal risultato.
        rate_for_date (Optional[Callable]): Funzione data->tasso storico
            USD->EUR per il costo base degli acquisti in USD (vedi
            _cost_basis_and_quantity).

    Returns:
        Tuple[list, list, list, list, list]: (values, labels, colors, invested, quantities)
            for pie chart. invested contains the total cost basis (invested amount) for
            each token, quantities the quantity held, in the same order as values/labels/colors.
    """
    from data.models import COIN_COLORS, FALLBACK_COLORS

    values = []
    labels = []
    colors = []
    invested = []
    quantities = []
    fallback_idx = 0

    mult = exchange_rate if currency == "EUR" else 1.0

    for token in df['Token'].unique():
        sub = df[df['Token'] == token]

        quantity, total_invested = _cost_basis_and_quantity(sub, exchange_rate, currency, rate_for_date)
        if quantity <= 0.000001:
            continue

        live_price = live_prices.get(token, 0) or 0
        current_value = quantity * live_price * mult

        if current_value > 0 and current_value >= dust_threshold:
            values.append(current_value)
            labels.append(token)
            invested.append(total_invested)
            quantities.append(quantity)
            if token.upper() in COIN_COLORS:
                colors.append(COIN_COLORS[token.upper()])
            else:
                colors.append(FALLBACK_COLORS[fallback_idx % len(FALLBACK_COLORS)])
                fallback_idx += 1

    return values, labels, colors, invested, quantities


def calculate_token_stats(
    df: pd.DataFrame,
    token: str,
    live_price: float,
    exchange_rate: float,
    currency: str = "EUR",
    rate_for_date: Optional[Callable] = None
) -> Dict[str, float]:
    """
    Calculate statistics for a single token.

    Args:
        df (pd.DataFrame): DataFrame with transactions.
        token (str): Token symbol.
        live_price (float): Current price of the token.
        exchange_rate (float): Exchange rate (USD to EUR if currency is EUR).
        currency (str): Target currency (EUR or USD).
        rate_for_date (Optional[Callable]): Funzione data->tasso storico
            USD->EUR per il costo base degli acquisti in USD.

    Returns:
        Dict[str, float]: Dictionary with statistics (quantity, pmc, invested, current_value).
    """
    df_token = df[df['Token'] == token]

    quantity, total_invested = _cost_basis_and_quantity(df_token, exchange_rate, currency, rate_for_date)

    pmc = (total_invested / quantity) if quantity > 0 else 0
    
    mult = exchange_rate if currency == "EUR" else 1.0
    current_value = quantity * (live_price or 0) * mult
    
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


def calculate_invested_over_time(
    df: pd.DataFrame,
    exchange_rate: float,
    currency: str = "EUR",
    rate_for_date: Optional[Callable] = None
) -> Tuple[list, list]:
    """
    Calculate the cumulative net invested capital over time (running total of
    buy costs minus sell proceeds), for a historical trend chart.

    Note: this reflects cost basis deployed over time from the transaction
    history, not the historical market value of the portfolio (which would
    require historical price data per token, not just FX rates).

    Args:
        df (pd.DataFrame): DataFrame with transactions (must include 'Date (UTC+1:00)').
        exchange_rate (float): Exchange rate (USD to EUR if currency is EUR).
        currency (str): Target currency (EUR or USD).
        rate_for_date (Optional[Callable]): Funzione data->tasso storico
            USD->EUR per il costo base degli acquisti in USD.

    Returns:
        Tuple[list, list]: (dates, cumulative_invested) sorted chronologically,
            one point per calendar day with at least one transaction.
    """
    df = df.dropna(subset=['Date (UTC+1:00)'])
    if df.empty:
        return [], []

    def row_flow(row) -> float:
        price = row['Price']
        orig_curr = str(row.get('Original Currency', 'EUR'))

        if currency == "EUR" and orig_curr == "USD":
            rate = _rate_for_row(row, exchange_rate, rate_for_date)
            value = (row['Amount'] * price * rate) + (row['Fee'] * rate)
        else:
            value = (row['Amount'] * price) + row['Fee']

        return value if str(row['Type']).lower() == 'buy' else -value

    flows = df.apply(row_flow, axis=1)
    days = df['Date (UTC+1:00)'].dt.date

    daily = flows.groupby(days).sum().sort_index()
    cumulative = daily.cumsum()

    return list(cumulative.index), list(cumulative.values)


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
