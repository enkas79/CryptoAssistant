"""
Tax Calculator Module for CryptoAssistant
Calculates taxes for cryptocurrency transactions based on country-specific rules.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import date, datetime
import pandas as pd

# Aliquota dell'imposta sulle cripto-attività (ex IVAFE): 2 per mille annuo
# sul valore di fine periodo, rapportato ai giorni di detenzione e alla quota.
IVAFE_RATE = 0.002

from data.models import Transaction
from data.tax_rules import TaxRule, TaxCalculationResult, TaxRulesManager


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


@dataclass
class QuadroRWRow:
    """
    Una riga del Quadro RW (monitoraggio fiscale) per una cripto-attività
    detenuta nel periodo d'imposta.
    """
    token: str
    quantita_iniziale: float
    valore_iniziale: float   # EUR: valore a inizio periodo o costo del primo acquisto
    quantita_finale: float
    valore_finale: float     # EUR: valore al 31/12 o corrispettivo di cessione
    giorni_possesso: int
    quota: float             # quota di possesso (1.0 = 100%)
    ivafe: float             # imposta cripto-attività 0,2% pro-rata giorni/quota
    note: str = ""


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

    def _effective_rate_and_threshold(self, year: int) -> Tuple[float, float]:
        """
        Restituisce l'aliquota e la franchigia effettivamente in vigore per l'anno
        indicato. Per l'Italia la normativa è cambiata nel tempo: 26% con franchigia
        di €2.000 fino al 2025, 33% senza franchigia dal 2026 (Legge di Bilancio 2025).
        Per le altre nazioni si usano i valori fissi della regola.

        Args:
            year (int): Anno fiscale di riferimento.

        Returns:
            Tuple[float, float]: (aliquota, soglia/franchigia).
        """
        if self.rule.country_code == "IT":
            if year >= 2026:
                return 0.33, 0.0  # L. 208/2025: aliquota 33%, nessuna franchigia
            if year == 2025:
                return 0.26, 0.0  # L. 207/2024: aliquota 26%, franchigia abolita
            return 0.26, 2000.0  # Fino al 2024: aliquota 26%, franchigia €2.000
        return self.rule.capital_gain_rate, self.rule.capital_gain_threshold

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

        df = df.copy()
        df['Date (UTC+1:00)'] = pd.to_datetime(df['Date (UTC+1:00)'], errors='coerce')

        # Il costo di carico FIFO richiede l'intero storico fino a fine anno:
        # una vendita del 2026 puo' chiudere un acquisto fatto nel 2023, 2024 o 2025.
        # Filtrare subito per il solo anno selezionato (come prima) faceva perdere
        # gli acquisti pregressi e produceva plusvalenze/minusvalenze errate.
        df_storico = df[df['Date (UTC+1:00)'].dt.year <= year].copy()
        df_storico = self._normalize_to_eur(df_storico)

        df_anno = df_storico[df_storico['Date (UTC+1:00)'].dt.year == year]

        if df_anno.empty:
            return TaxCalculationResult(
                country=self.rule.country,
                year=year,
                capital_gain=0.0,
                capital_gain_tax=0.0,
                stamp_duty=0.0,
                total_tax=0.0,
                taxable_transactions=[],
                declaration_required=False,
                notes=["Nessuna transazione per l'anno selezionato."],
                all_transactions=[]
            )

        # Tutte le compravendite dell'anno (buy e sell, incluso crypto/crypto),
        # a prescindere dal loro esito ai fini FIFO/plusvalenza.
        all_transactions = [
            {
                "date": row['Date (UTC+1:00)'].strftime("%d/%m/%Y"),
                "token": row['Token'],
                "type": row['Type'],
                "amount": row['Amount'],
                "price": row['Price'],
                "total": row['Amount'] * row['Price'],
                "notes": row.get('Notes', '')
            }
            for _, row in df_anno.sort_values('Date (UTC+1:00)').iterrows()
            if str(row['Type']).lower() in ('buy', 'sell')
        ]

        # Applica il metodo di abbinamento lotti sull'intero storico (cosi' i lotti
        # gia' consumati negli anni precedenti non vengono riutilizzati), poi tiene
        # solo le vendite effettivamente avvenute nell'anno selezionato.
        eventi_storico: List[TaxableEvent] = self._apply_cost_basis(df_storico)
        taxable_events = [
            e for e in eventi_storico
            if isinstance(e.date, datetime) and e.date.year == year
        ]

        # Plusvalenze e minusvalenze si compensano nello stesso periodo d'imposta
        # (Italia: art. 67 TUIR); il risultato negativo non genera imposta.
        plusvalenze_lorde = sum(event.gain for event in taxable_events if event.gain > 0)
        minusvalenze = sum(-event.gain for event in taxable_events if event.gain < 0)
        capital_gain = max(plusvalenze_lorde - minusvalenze, 0.0)

        # Calculate capital gain tax (aliquota/franchigia in vigore per l'anno selezionato)
        rate, threshold = self._effective_rate_and_threshold(year)
        if capital_gain > threshold:
            capital_gain_tax = capital_gain * rate
        else:
            capital_gain_tax = 0.0

        # Calculate stamp duty (for Italy: EUR 2 per transaction over EUR 5.000)
        stamp_duty = 0.0
        if self.rule.stamp_duty > 0:
            for _, row in df_anno[df_anno['Type'] == 'sell'].iterrows():
                transaction_value = row['Amount'] * row['Price']
                if transaction_value > self.rule.stamp_duty_threshold:
                    stamp_duty += self.rule.stamp_duty

        # Check if declaration is required (for Italy: portfolio > EUR 15.000);
        # richiede lo storico completo, non solo le transazioni dell'anno.
        portfolio_value = self._calculate_portfolio_value(df_storico, year)
        declaration_required = portfolio_value > self.rule.declaration_threshold
        
        # Prepare notes
        notes = []
        if self.rule.holding_period_exemption > 0:
            exempt_events = [e for e in taxable_events if e.holding_days >= self.rule.holding_period_exemption * 365]
            if exempt_events:
                notes.append(
                    f"{len(exempt_events)} transazioni esenti per detenzione > {self.rule.holding_period_exemption} anni."
                )
        
        if minusvalenze > 0:
            notes.append(
                f"Minusvalenze dell'anno compensate con le plusvalenze: €{minusvalenze:,.2f}."
            )

        if capital_gain <= threshold:
            if threshold > 0:
                notes.append(
                    f"Plusvalenze nette sotto la franchigia annuale di €{threshold:,.2f} - Nessuna tassazione."
                )
        elif rate != self.rule.capital_gain_rate:
            notes.append(f"Aliquota applicata per il {year}: {rate * 100:.0f}%.")

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
                for event in sorted(taxable_events, key=lambda e: e.date)
            ],
            declaration_required=declaration_required,
            notes=notes,
            all_transactions=all_transactions
        )
    
    def _apply_cost_basis(self, df: pd.DataFrame) -> List[TaxableEvent]:
        """
        Abbina acquisti e vendite col metodo previsto dalla regola nazionale
        (`cost_basis_method`: "LIFO" per l'Italia, "FIFO" altrove).

        Le righe con prezzo <= 0 (trasferimenti tra wallet, fee di rete, reward
        non ancora valorizzati) NON sono cessioni/acquisti a titolo oneroso:
        vengono ignorate sia come lotti sia come realizzo. Vanno valorizzate a
        parte (vedi `zero_price_rows`).

        Args:
            df (pd.DataFrame): Transazioni (Price/Fee già normalizzati in EUR).

        Returns:
            List[TaxableEvent]: Eventi tassabili (vendite con lotti abbinati).
        """
        method = getattr(self.rule, 'cost_basis_method', 'FIFO').upper()
        taxable_events: List[TaxableEvent] = []

        for token in df['Token'].unique():
            token_df = df[df['Token'] == token].sort_values('Date (UTC+1:00)')
            token_df = token_df[token_df['Price'] > 0]

            buy_list = token_df[token_df['Type'] == 'buy'].to_dict('records')
            sell_list = token_df[token_df['Type'] == 'sell'].to_dict('records')

            for sell in sell_list:
                sell_date = sell['Date (UTC+1:00)']
                sell_amount = sell['Amount']
                sell_price = sell['Price']
                remaining_amount = sell_amount

                # Lotti disponibili: acquistati non dopo la vendita e non esauriti.
                available = [
                    b for b in buy_list
                    if b['Amount'] > 0 and b['Date (UTC+1:00)'] <= sell_date
                ]
                if method == 'LIFO':
                    available = list(reversed(available))

                for buy in available:
                    if remaining_amount <= 1e-12:
                        break

                    match_amount = min(remaining_amount, buy['Amount'])
                    buy_date = buy['Date (UTC+1:00)']
                    buy_price = buy['Price']
                    gain = (sell_price - buy_price) * match_amount
                    holding_days = (
                        (sell_date - buy_date).days
                        if isinstance(sell_date, datetime) and isinstance(buy_date, datetime)
                        else 0
                    )

                    taxable_events.append(TaxableEvent(
                        date=sell_date,
                        token=token,
                        amount=match_amount,
                        buy_price=buy_price,
                        sell_price=sell_price,
                        gain=gain,
                        fee=sell.get('Fee', 0) * (match_amount / sell_amount) if sell_amount > 0 else 0,
                        holding_days=holding_days,
                    ))

                    buy['Amount'] -= match_amount
                    remaining_amount -= match_amount

        return taxable_events

    def zero_price_rows(self, df: pd.DataFrame, year: int) -> List[Dict]:
        """
        Righe di acquisto con prezzo mancante (0) nell'anno o negli anni
        precedenti ma ancora rilevanti: reward, airdrop, cashback o
        trasferimenti in entrata non valorizzati. Vanno esaminate a mano
        (valore EUR alla ricezione per i proventi, costo originario per i
        trasferimenti) perché falsano costo base e imposta.
        """
        df = df.copy()
        df['Date (UTC+1:00)'] = pd.to_datetime(df['Date (UTC+1:00)'], errors='coerce')
        df = df.dropna(subset=['Date (UTC+1:00)'])
        mask = (
            (df['Date (UTC+1:00)'].dt.year <= year)
            & (df['Type'].astype(str).str.lower() == 'buy')
            & (df['Price'] <= 0)
        )
        out = []
        for _, r in df[mask].sort_values('Date (UTC+1:00)').iterrows():
            out.append({
                'date': r['Date (UTC+1:00)'].strftime('%d/%m/%Y'),
                'token': r['Token'],
                'amount': float(r['Amount']),
                'notes': str(r.get('Notes', '') or ''),
            })
        return out

    def holdings_bounds(self, df: pd.DataFrame, year: int) -> List[Tuple[str, float, float]]:
        """
        Per ogni token rilevante nell'anno restituisce (token, qtà al 1° gennaio,
        qtà al 31 dicembre). Serve a sapere quali quotazioni storiche recuperare.
        Esclude i token già azzerati prima dell'anno e mai più movimentati.
        """
        df = df.copy()
        df['Date (UTC+1:00)'] = pd.to_datetime(df['Date (UTC+1:00)'], errors='coerce')
        df = df.dropna(subset=['Date (UTC+1:00)'])
        df = df[df['Date (UTC+1:00)'].dt.year <= year]
        year_start = pd.Timestamp(year, 1, 1)

        out: List[Tuple[str, float, float]] = []
        for token in sorted(df['Token'].unique()):
            tdf = df[df['Token'] == token]
            delta = tdf.apply(
                lambda r: r['Amount'] if str(r['Type']).lower() == 'buy' else -r['Amount'],
                axis=1,
            )
            qty_start = max(delta[tdf['Date (UTC+1:00)'] < year_start].sum(), 0.0)
            qty_end = max(delta.sum(), 0.0)
            movimentato = (tdf['Date (UTC+1:00)'].dt.year == year).any()
            if qty_start <= 1e-9 and qty_end <= 1e-9 and not movimentato:
                continue
            out.append((token, float(qty_start), float(qty_end)))
        return out

    def build_quadro_rw(
        self,
        df: pd.DataFrame,
        year: int,
        prices_start: Dict[str, float],
        prices_end: Dict[str, float],
    ) -> List[QuadroRWRow]:
        """
        Costruisce le righe del Quadro RW per l'anno indicato.

        Args:
            df: Storico completo delle transazioni.
            year: Anno d'imposta.
            prices_start: Quotazione EUR di ogni token al 1° gennaio dell'anno.
            prices_end: Quotazione EUR di ogni token al 31 dicembre dell'anno.

        Returns:
            Una riga per ogni token detenuto (anche solo in parte dell'anno).
        """
        df = df.copy()
        df['Date (UTC+1:00)'] = pd.to_datetime(df['Date (UTC+1:00)'], errors='coerce')
        df = df.dropna(subset=['Date (UTC+1:00)'])
        df = self._normalize_to_eur(df[df['Date (UTC+1:00)'].dt.year <= year].copy())

        year_start = pd.Timestamp(year, 1, 1)
        year_end = pd.Timestamp(year, 12, 31)
        days_in_year = (date(year, 12, 31) - date(year, 1, 1)).days + 1

        rows: List[QuadroRWRow] = []
        for token in sorted(df['Token'].unique()):
            tdf = df[df['Token'] == token].sort_values('Date (UTC+1:00)').copy()
            tdf['_delta'] = tdf.apply(
                lambda r: r['Amount'] if str(r['Type']).lower() == 'buy' else -r['Amount'],
                axis=1,
            )
            tdf['_cum'] = tdf['_delta'].cumsum()

            qty_start = max(tdf.loc[tdf['Date (UTC+1:00)'] < year_start, '_delta'].sum(), 0.0)
            qty_end = max(tdf['_delta'].sum(), 0.0)

            in_year = tdf[tdf['Date (UTC+1:00)'].dt.year == year]
            in_year_buys = in_year[in_year['Type'].astype(str).str.lower() == 'buy']

            held_at_start = qty_start > 1e-9
            held_at_end = qty_end > 1e-9
            if not held_at_start and not held_at_end and in_year_buys.empty:
                continue

            if held_at_start:
                first_day = year_start
            else:
                if in_year_buys.empty:
                    continue
                first_day = in_year_buys['Date (UTC+1:00)'].min().normalize()

            if held_at_end:
                last_day = year_end
            else:
                zeroing = in_year[in_year['_cum'] <= 1e-9]
                last_day = (
                    zeroing['Date (UTC+1:00)'].min().normalize()
                    if not zeroing.empty else year_end
                )

            giorni = (last_day.date() - first_day.date()).days + 1
            giorni = max(0, min(giorni, days_in_year))

            price_s = prices_start.get(token, 0.0) or 0.0
            price_e = prices_end.get(token, 0.0) or 0.0

            if held_at_start:
                valore_iniziale = qty_start * price_s
            else:
                priced = in_year_buys[in_year_buys['Price'] > 0]
                valore_iniziale = float((priced['Amount'] * priced['Price']).sum())

            if held_at_end:
                valore_finale = qty_end * price_e
            else:
                sells = in_year[
                    (in_year['Type'].astype(str).str.lower() == 'sell') & (in_year['Price'] > 0)
                ]
                valore_finale = float((sells['Amount'] * sells['Price']).sum())

            ivafe = valore_finale * IVAFE_RATE * giorni / days_in_year

            note = ""
            if not held_at_end:
                note = "Posizione chiusa nell'anno: valore finale = corrispettivo di cessione."
            elif not held_at_start:
                note = "Acquisita nell'anno: valore iniziale = costo d'acquisto."

            rows.append(QuadroRWRow(
                token=token,
                quantita_iniziale=qty_start,
                valore_iniziale=valore_iniziale,
                quantita_finale=qty_end,
                valore_finale=valore_finale,
                giorni_possesso=int(giorni),
                quota=1.0,
                ivafe=ivafe,
                note=note,
            ))
        return rows

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
                prices_anno = token_df[token_df['Date (UTC+1:00)'].dt.year == year]['Price']
                last_price = prices_anno.iloc[-1] if not prices_anno.empty else token_df['Price'].iloc[-1]
                portfolio_value += net_amount * last_price
        
        return portfolio_value
    
    def get_tax_summary(
        self,
        df: pd.DataFrame,
        year: Optional[int] = None,
        prices_start: Optional[Dict[str, float]] = None,
        prices_end: Optional[Dict[str, float]] = None,
    ) -> Dict:
        """
        Get a summary of tax calculations for a given year.

        Args:
            df (pd.DataFrame): DataFrame with transactions.
            year (Optional[int]): Year for which to calculate taxes.
            prices_start (Optional[Dict[str, float]]): Quotazioni EUR al 1° gennaio
                dell'anno, per token. Se fornite (insieme a prices_end) il
                riepilogo include il Quadro RW e l'imposta cripto-attività.
            prices_end (Optional[Dict[str, float]]): Quotazioni EUR al 31 dicembre.

        Returns:
            Dict: Summary of tax calculations.
        """
        if year is None:
            year = datetime.now().year

        result = self.calculate_taxes(df, year)
        rate, threshold = self._effective_rate_and_threshold(year)

        quadro_rw: List[Dict] = []
        imposta_cripto_totale = 0.0
        if prices_start is not None and prices_end is not None:
            righe = self.build_quadro_rw(df, year, prices_start, prices_end)
            for r in righe:
                quadro_rw.append({
                    "token": r.token,
                    "quantita_iniziale": r.quantita_iniziale,
                    "valore_iniziale": round(r.valore_iniziale, 2),
                    "quantita_finale": r.quantita_finale,
                    "valore_finale": round(r.valore_finale, 2),
                    "giorni_possesso": r.giorni_possesso,
                    "quota": r.quota,
                    "ivafe": round(r.ivafe, 2),
                    "note": r.note,
                })
            imposta_cripto_totale = sum(r.ivafe for r in righe)

        return {
            "country": result.country,
            "year": result.year,
            "cost_basis_method": getattr(self.rule, "cost_basis_method", "FIFO"),
            "capital_gain": round(result.capital_gain, 2),
            "capital_gain_tax": round(result.capital_gain_tax, 2),
            "stamp_duty": round(result.stamp_duty, 2),
            "total_tax": round(result.total_tax, 2),
            "declaration_required": result.declaration_required,
            "taxable_transactions_count": len(result.taxable_transactions),
            "taxable_transactions": result.taxable_transactions,
            "all_transactions": result.all_transactions,
            "quadro_rw": quadro_rw,
            "imposta_cripto_totale": round(imposta_cripto_totale, 2),
            "zero_price_rows": self.zero_price_rows(df, year),
            "notes": result.notes,
            "rule": {
                "capital_gain_rate": f"{rate * 100:.0f}%",
                "capital_gain_threshold": f"€{threshold:,.2f}",
                "stamp_duty": f"€{self.rule.stamp_duty:,.2f}",
                "declaration_threshold": f"€{self.rule.declaration_threshold:,.2f}",
            }
        }
