"""
Tax Calculator Module for CryptoAssistant
Calculates taxes for cryptocurrency transactions based on country-specific rules.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd

from ..data.models import Transaction
from ..data.tax_rules import TaxRule, TaxCalculationResult, TaxRulesManager


@dataclass
class TaxableEvent:
    """
    Represents a taxable event (sale of cryptocurrency).
    """
    date: datetime
    token: str
    amount: float
    buy_price: float  # Price at which the token was bought (cost basis)
    sell_price: float  # Price at which the token was sold
    gain: float  # gain = (sell_price - buy_price) * amount
    fee: float  # Transaction fee
    holding_days: int  # Days the token was held


class TaxCalculator:
    """
    Calculates taxes for cryptocurrency transactions.
    """
    
    def __init__(
        self,
        country_code: str = "IT",
        historical_rates: Optional[Dict[str, float]] = None,
        live_rate: float = 0.92
    ):
        """
        Initialize the tax calculator for a specific country.

        Args:
            country_code (str): ISO 3166-1 alpha-2 country code (e.g., "IT" for Italy).
            historical_rates (Optional[Dict[str, float]]): USD->EUR rates keyed by
                "YYYY-MM-DD", used to normalize transactions recorded in USD to EUR
                (all supported tax rules are EUR-denominated).
            live_rate (float): Fallback USD->EUR rate used when a transaction date
                is not found in historical_rates.
        """
        self.rules_manager = TaxRulesManager()
        self.rule: TaxRule = self.rules_manager.get_rule(country_code)

        if self.rule is None:
            raise ValueError(f"No tax rules found for country code: {country_code}")

        self.historical_rates: Dict[str, float] = historical_rates or {}
        self.live_rate: float = live_rate

    def set_country(self, country_code: str) -> None:
        """
        Change the country for tax calculation.

        Args:
            country_code (str): ISO 3166-1 alpha-2 country code.
        """
        self.rule = self.rules_manager.get_rule(country_code)
        if self.rule is None:
            raise ValueError(f"No tax rules found for country code: {country_code}")

    def set_historical_rates(self, historical_rates: Dict[str, float]) -> None:
        """
        Update the USD->EUR historical rates used to normalize transactions.

        Args:
            historical_rates (Dict[str, float]): USD->EUR rates keyed by "YYYY-MM-DD".
        """
        self.historical_rates = historical_rates

    def _rate_for_date(self, date_obj) -> float:
        """Get the USD->EUR rate for a given date, falling back to live_rate."""
        try:
            date_str = date_obj.strftime("%Y-%m-%d")
            if date_str in self.historical_rates:
                return self.historical_rates[date_str]
        except Exception:
            pass
        return self.live_rate

    def _normalize_to_eur(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert Price and Fee to EUR for transactions recorded in USD.

        All supported tax rules (capital gain thresholds, stamp duty,
        declaration threshold) are EUR-denominated, so mixed-currency
        portfolios must be normalized before any tax computation.

        Args:
            df (pd.DataFrame): DataFrame with transactions (already filtered by year).

        Returns:
            pd.DataFrame: DataFrame with Price/Fee normalized to EUR.
        """
        if 'Original Currency' not in df.columns:
            return df

        df = df.copy()
        is_usd = df['Original Currency'].astype(str) == 'USD'
        if not is_usd.any():
            return df

        rates = df.loc[is_usd, 'Date (UTC+1:00)'].apply(self._rate_for_date)
        df.loc[is_usd, 'Price'] = df.loc[is_usd, 'Price'] * rates
        df.loc[is_usd, 'Fee'] = df.loc[is_usd, 'Fee'] * rates
        return df
    
    def calculate_taxes(
        self,
        df: pd.DataFrame,
        year: Optional[int] = None
    ) -> TaxCalculationResult:
        """
        Calculate taxes for a DataFrame of transactions.
        
        Args:
            df (pd.DataFrame): DataFrame with transactions (must have columns:
                'Date (UTC+1:00)', 'Token', 'Type', 'Amount', 'Price', 'Fee').
            year (Optional[int]): Year for which to calculate taxes. If None, uses current year.
        
        Returns:
            TaxCalculationResult: Result of tax calculation.
        """
        if year is None:
            year = datetime.now().year
        
        # Filter transactions for the year
        df = df.copy()
        df['Date (UTC+1:00)'] = pd.to_datetime(df['Date (UTC+1:00)'], errors='coerce')
        df = df[df['Date (UTC+1:00)'].dt.year == year]

        # Normalize USD transactions to EUR (tax rules are EUR-denominated)
        df = self._normalize_to_eur(df)

        if df.empty:
            return TaxCalculationResult(
                country=self.rule.country,
                year=year,
                capital_gain=0.0,
                capital_gain_tax=0.0,
                stamp_duty=0.0,
                total_tax=0.0,
                taxable_transactions=[],
                declaration_required=False,
                notes=["Nessuna transazione per l'anno selezionato."]
            )
        
        # Apply FIFO to match buys and sells
        taxable_events: List[TaxableEvent] = self._apply_fifo(df)
        
        # Calculate capital gains
        capital_gain = sum(event.gain for event in taxable_events if event.gain > 0)
        
        # Calculate capital gain tax
        if capital_gain > self.rule.capital_gain_threshold:
            capital_gain_tax = capital_gain * self.rule.capital_gain_rate
        else:
            capital_gain_tax = 0.0
        
        # Calculate stamp duty (for Italy: EUR 2 per transaction over EUR 5.000)
        stamp_duty = 0.0
        if self.rule.stamp_duty > 0:
            for _, row in df[df['Type'] == 'sell'].iterrows():
                transaction_value = row['Amount'] * row['Price']
                if transaction_value > self.rule.stamp_duty_threshold:
                    stamp_duty += self.rule.stamp_duty
        
        # Check if declaration is required (for Italy: portfolio > EUR 15.000)
        portfolio_value = self._calculate_portfolio_value(df, year)
        declaration_required = portfolio_value > self.rule.declaration_threshold
        
        # Prepare notes
        notes = []
        if self.rule.holding_period_exemption > 0:
            exempt_events = [e for e in taxable_events if e.holding_days >= self.rule.holding_period_exemption * 365]
            if exempt_events:
                notes.append(
                    f"{len(exempt_events)} transazioni esenti per detenzione > {self.rule.holding_period_exemption} anni."
                )
        
        if capital_gain <= self.rule.capital_gain_threshold:
            notes.append(
                f"Plusvalenze sotto la soglia annuale di €{self.rule.capital_gain_threshold:,.2f} - Nessuna tassazione."
            )
        
        if declaration_required:
            notes.append(
                f"Dichiarazione RW obbligatoria (portafoglio > €{self.rule.declaration_threshold:,.2f})."
            )
        
        return TaxCalculationResult(
            country=self.rule.country,
            year=year,
            capital_gain=capital_gain,
            capital_gain_tax=capital_gain_tax,
            stamp_duty=stamp_duty,
            total_tax=capital_gain_tax + stamp_duty,
            taxable_transactions=[
                {
                    "date": event.date.strftime("%d/%m/%Y"),
                    "token": event.token,
                    "amount": event.amount,
                    "buy_price": event.buy_price,
                    "sell_price": event.sell_price,
                    "gain": event.gain,
                    "holding_days": event.holding_days
                }
                for event in taxable_events if event.gain > 0
            ],
            declaration_required=declaration_required,
            notes=notes
        )
    
    def _apply_fifo(self, df: pd.DataFrame) -> List[TaxableEvent]:
        """
        Apply FIFO (First-In-First-Out) to match buy and sell transactions.
        
        Args:
            df (pd.DataFrame): DataFrame with transactions.
        
        Returns:
            List[TaxableEvent]: List of taxable events (sells with matched buys).
        """
        taxable_events = []
        
        # Group by token
        for token in df['Token'].unique():
            token_df = df[df['Token'] == token].sort_values('Date (UTC+1:00)')
            buys = token_df[token_df['Type'] == 'buy'].copy()
            sells = token_df[token_df['Type'] == 'sell'].copy()
            
            # Convert to list of dicts for easier manipulation
            buy_list = buys.to_dict('records')
            sell_list = sells.to_dict('records')
            
            # Apply FIFO
            for sell in sell_list:
                sell_date = sell['Date (UTC+1:00)']
                sell_amount = sell['Amount']
                sell_price = sell['Price']
                
                remaining_amount = sell_amount
                
                for buy in buy_list:
                    if remaining_amount <= 0:
                        break
                    
                    if buy['Amount'] <= 0:
                        continue
                    
                    # Calculate how much we can match from this buy
                    match_amount = min(remaining_amount, buy['Amount'])
                    
                    # Calculate gain/loss
                    buy_date = buy['Date (UTC+1:00)']
                    buy_price = buy['Price']
                    gain = (sell_price - buy_price) * match_amount
                    
                    # Calculate holding period in days
                    holding_days = (sell_date - buy_date).days if isinstance(sell_date, datetime) and isinstance(buy_date, datetime) else 0
                    
                    # Add taxable event
                    taxable_events.append(TaxableEvent(
                        date=sell_date,
                        token=token,
                        amount=match_amount,
                        buy_price=buy_price,
                        sell_price=sell_price,
                        gain=gain,
                        fee=sell.get('Fee', 0) * (match_amount / sell_amount) if sell_amount > 0 else 0,
                        holding_days=holding_days
                    ))
                    
                    # Update remaining amounts
                    buy['Amount'] -= match_amount
                    remaining_amount -= match_amount
        
        return taxable_events
    
    def _calculate_portfolio_value(self, df: pd.DataFrame, year: int) -> float:
        """
        Calculate the total portfolio value at the end of the year.
        
        Args:
            df (pd.DataFrame): DataFrame with transactions.
            year (int): Year for which to calculate the portfolio.
        
        Returns:
            float: Total portfolio value in EUR at the end of the year.
        """
        # Filter transactions up to the end of the year
        df = df.copy()
        df['Date (UTC+1:00)'] = pd.to_datetime(df['Date (UTC+1:00)'], errors='coerce')
        df = df[df['Date (UTC+1:00)'].dt.year <= year]
        
        # Calculate holdings for each token
        portfolio_value = 0.0
        
        for token in df['Token'].unique():
            token_df = df[df['Token'] == token]
            buys = token_df[token_df['Type'] == 'buy']
            sells = token_df[token_df['Type'] == 'sell']
            
            # Calculate net amount
            total_bought = buys['Amount'].sum()
            total_sold = sells['Amount'].sum()
            net_amount = total_bought - total_sold
            
            if net_amount > 0:
                # Use the last price of the year as the current price
                last_price = token_df[token_df['Date (UTC+1:00)'].dt.year == year]['Price'].iloc[-1] if not token_df.empty else 0
                portfolio_value += net_amount * last_price
        
        return portfolio_value
    
    def get_tax_summary(self, df: pd.DataFrame, year: Optional[int] = None) -> Dict:
        """
        Get a summary of tax calculations for a given year.
        
        Args:
            df (pd.DataFrame): DataFrame with transactions.
            year (Optional[int]): Year for which to calculate taxes.
        
        Returns:
            Dict: Summary of tax calculations.
        """
        result = self.calculate_taxes(df, year)
        
        return {
            "country": result.country,
            "year": result.year,
            "capital_gain": round(result.capital_gain, 2),
            "capital_gain_tax": round(result.capital_gain_tax, 2),
            "stamp_duty": round(result.stamp_duty, 2),
            "total_tax": round(result.total_tax, 2),
            "declaration_required": result.declaration_required,
            "taxable_transactions_count": len(result.taxable_transactions),
            "notes": result.notes,
            "rule": {
                "capital_gain_rate": f"{self.rule.capital_gain_rate * 100}%",
                "capital_gain_threshold": f"€{self.rule.capital_gain_threshold:,.2f}",
                "stamp_duty": f"€{self.rule.stamp_duty:,.2f}",
                "declaration_threshold": f"€{self.rule.declaration_threshold:,.2f}",
            }
        }
