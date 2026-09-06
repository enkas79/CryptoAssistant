"""
CSV Importer Module for CryptoAssistant
Handles importing transactions from various CSV formats (Binance, CoinMarketCap, Crypto.com, Nexo, ecc.).
"""

import os
import re
import pandas as pd
from typing import List, Optional


class CSVImporter:
    """
    Imports transactions from CSV files con formati diversi.
    Prova prima i parser dedicati per exchange noti (Crypto.com, Nexo),
    poi ricade sull'euristica generica per formati non riconosciuti.
    """

    # Mappings for column detection (parser generico)
    DATE_KEYWORDS = ["DATE", "DATA", "TIME"]
    TOKEN_KEYWORDS = ["TOKEN", "COIN", "ASSET", "CURRENCY TICKER"]
    TYPE_KEYWORDS = ["TYPE", "TIPO", "DIRECTION"]
    AMOUNT_KEYWORDS = ["AMOUNT", "QUANTIT", "QTA", "OPERATION AMOUNT"]
    PRICE_KEYWORDS = ["PRICE", "PREZZO", "VALORE", "VALUE", "COUNTER VALUE"]
    FEE_KEYWORDS = ["FEE", "COMMISSION"]
    NOTES_KEYWORDS = ["NOTE", "NOTES", "MEMO", "COMMENT"]

    FINAL_COLUMNS = [
        'Date (UTC+1:00)', 'Token', 'Type', 'Amount',
        'Price', 'Fee', 'Notes', 'Original Currency'
    ]

    # Firme (colonne obbligatorie) usate per riconoscere i formati noti
    CRYPTO_COM_SIGNATURE = {
        'Timestamp (UTC)', 'Transaction Description', 'Currency', 'Transaction Kind'
    }
    NEXO_SIGNATURE = {
        'Transaction', 'Type', 'Input Currency', 'Output Currency', 'USD Equivalent'
    }

    @classmethod
    def detect_column(cls, columns: List[str], keywords: List[str]) -> Optional[str]:
        """
        Detect a column by keywords in its name.
        """
        for col in columns:
            if any(keyword in col.upper() for keyword in keywords):
                return col
        return None

    @staticmethod
    def _parse_money(value) -> float:
        """Converte stringhe tipo '$1,264.09' o '-' in float."""
        if pd.isna(value):
            return 0.0
        s = str(value).strip()
        if s in ('', '-', 'nan', 'None'):
            return 0.0
        s = re.sub(r'[^0-9.\-]', '', s)
        try:
            return float(s)
        except ValueError:
            return 0.0

    @classmethod
    def _parse_crypto_com(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Parser dedicato per l'export 'Crypto Transactions Record' di Crypto.com.
        Gestisce i conversion/exchange (Currency -> To Currency) come due righe
        (sell + buy), tutti gli altri movimenti come singola riga in base al
        segno di 'Amount'. Il valore in USD arriva da 'Native Amount (in USD)'.
        """
        rows = []
        for _, row in df.iterrows():
            amount = pd.to_numeric(row.get('Amount'), errors='coerce')
            if pd.isna(amount):
                continue

            currency = str(row.get('Currency', '')).strip()
            to_currency = row.get('To Currency')
            to_amount = pd.to_numeric(row.get('To Amount'), errors='coerce')
            native_usd = pd.to_numeric(row.get('Native Amount (in USD)'), errors='coerce')
            native_usd = 0.0 if pd.isna(native_usd) else native_usd

            date = row.get('Timestamp (UTC)')
            description = str(row.get('Transaction Description', '') or '')
            kind = str(row.get('Transaction Kind', '') or '')
            notes = f"{description} ({kind})".strip()

            has_second_leg = (
                pd.notna(to_currency) and str(to_currency).strip() != ''
                and str(to_currency).strip() != currency
                and not pd.isna(to_amount)
            )

            if has_second_leg:
                qty_sell = abs(amount)
                price_sell = (native_usd / qty_sell) if qty_sell else 0.0
                rows.append({
                    'Date (UTC+1:00)': date, 'Token': currency, 'Type': 'sell',
                    'Amount': qty_sell, 'Price': price_sell, 'Fee': 0.0,
                    'Notes': notes, 'Original Currency': 'USD'
                })

                qty_buy = abs(to_amount)
                price_buy = (native_usd / qty_buy) if qty_buy else 0.0
                rows.append({
                    'Date (UTC+1:00)': date, 'Token': str(to_currency).strip(), 'Type': 'buy',
                    'Amount': qty_buy, 'Price': price_buy, 'Fee': 0.0,
                    'Notes': notes, 'Original Currency': 'USD'
                })
            else:
                qty = abs(amount)
                tx_type = 'buy' if amount >= 0 else 'sell'
                price = (native_usd / qty) if qty else 0.0
                rows.append({
                    'Date (UTC+1:00)': date, 'Token': currency, 'Type': tx_type,
                    'Amount': qty, 'Price': price, 'Fee': 0.0,
                    'Notes': notes, 'Original Currency': 'USD'
                })

        return pd.DataFrame(rows, columns=cls.FINAL_COLUMNS)

    # Tipi che duplicano un'altra riga dello stesso evento (lato "exchange"
    # interno di Nexo): stessa data, stesso importo, stesso controvalore USD
    # della riga lato wallet già generata da un altro Type. Vanno scartati
    # per non contare due volte la stessa conversione.
    NEXO_DUPLICATE_TYPES = {'Exchange Deposited On', 'Manual Sell Order'}

    @classmethod
    def _parse_nexo(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Parser dedicato per l'export 'Transactions' di Nexo.
        Usa il segno di 'Input Amount' per buy/sell: i movimenti interni
        (lock/unlock, trasferimenti tra wallet Nexo) si compensano a somma
        zero, mentre interessi/top-up/withdrawal spostano davvero la quantità.
        Quando 'Input Currency' e 'Output Currency' differiscono (vere
        conversioni, es. Exchange) genera due righe (sell + buy), come per
        Crypto.com. Il valore arriva da 'USD Equivalent'.

        Alcuni Type ('Exchange Deposited On', 'Manual Sell Order') sono la
        seconda riga generata da Nexo per lo stesso evento già registrato
        rispettivamente da 'Deposit To Exchange' e 'Exchange Liquidation':
        vengono scartati per evitare di contare due volte la stessa conversione.
        """
        rows = []
        for _, row in df.iterrows():
            tx_kind = str(row.get('Type', '') or '')
            if tx_kind in cls.NEXO_DUPLICATE_TYPES:
                continue

            in_amount = pd.to_numeric(row.get('Input Amount'), errors='coerce')
            if pd.isna(in_amount):
                continue

            in_token = str(row.get('Input Currency', '') or '').strip()
            out_token = str(row.get('Output Currency', '') or '').strip()
            if out_token == '-':
                out_token = ''
            out_amount = pd.to_numeric(row.get('Output Amount'), errors='coerce')
            usd_value = cls._parse_money(row.get('USD Equivalent'))
            fee = cls._parse_money(row.get('Fee'))
            fee_currency = str(row.get('Fee Currency', '') or '').strip()
            if fee_currency == '-':
                fee_currency = ''

            details = str(row.get('Details', '') or row.get('normalizedDisplayDetails', '') or '')
            notes = f"{tx_kind} - {details}".strip(' -')
            date = row.get('Date / Time (UTC)')

            is_conversion = (
                out_token != '' and out_token != in_token and not pd.isna(out_amount)
            )

            if is_conversion:
                qty_sell = abs(in_amount)
                price_sell = (usd_value / qty_sell) if qty_sell else 0.0
                rows.append({
                    'Date (UTC+1:00)': date, 'Token': in_token, 'Type': 'sell',
                    'Amount': qty_sell, 'Price': price_sell,
                    'Fee': fee if fee_currency == in_token else 0.0,
                    'Notes': notes, 'Original Currency': 'USD'
                })

                qty_buy = abs(out_amount)
                price_buy = (usd_value / qty_buy) if qty_buy else 0.0
                rows.append({
                    'Date (UTC+1:00)': date, 'Token': out_token, 'Type': 'buy',
                    'Amount': qty_buy, 'Price': price_buy,
                    'Fee': fee if fee_currency == out_token else 0.0,
                    'Notes': notes, 'Original Currency': 'USD'
                })
            else:
                token = in_token or out_token
                qty = abs(in_amount)
                tx_type = 'buy' if in_amount >= 0 else 'sell'
                price = (usd_value / qty) if qty else 0.0
                rows.append({
                    'Date (UTC+1:00)': date, 'Token': token,
                    'Type': tx_type, 'Amount': qty, 'Price': price, 'Fee': fee,
                    'Notes': notes, 'Original Currency': 'USD'
                })

        return pd.DataFrame(rows, columns=cls.FINAL_COLUMNS)

    @classmethod
    def _parse_generic(cls, df: pd.DataFrame, file_path: str) -> Optional[pd.DataFrame]:
        """Euristica generica basata su keyword, usata come fallback."""
        if df.empty or len(df.columns) <= 1:
            return None

        col_data = cls.detect_column(df.columns, cls.DATE_KEYWORDS)
        col_token = cls.detect_column(df.columns, cls.TOKEN_KEYWORDS)
        col_type = cls.detect_column(df.columns, cls.TYPE_KEYWORDS)
        col_amount = cls.detect_column(df.columns, cls.AMOUNT_KEYWORDS)
        col_price = cls.detect_column(df.columns, cls.PRICE_KEYWORDS)
        col_fee = cls.detect_column(df.columns, cls.FEE_KEYWORDS)
        col_notes = cls.detect_column(df.columns, cls.NOTES_KEYWORDS)

        rename_dict = {}
        if col_data:
            rename_dict[col_data] = 'Date (UTC+1:00)'
        if col_token:
            rename_dict[col_token] = 'Token'
        if col_type:
            rename_dict[col_type] = 'Type'
        if col_amount:
            rename_dict[col_amount] = 'Amount'
        if col_price:
            rename_dict[col_price] = 'Price'
        if col_fee:
            rename_dict[col_fee] = 'Fee'
        if col_notes:
            rename_dict[col_notes] = 'Notes'

        detected_currency = 'EUR'
        if col_price and 'USD' in col_price.upper():
            detected_currency = 'USD'

        df = df.rename(columns=rename_dict)

        if 'Token' not in df.columns:
            df['Token'] = os.path.basename(file_path).split('.')[0].upper()
        if 'Price' not in df.columns:
            df['Price'] = 0
        if 'Fee' not in df.columns:
            df['Fee'] = 0
        if 'Notes' not in df.columns:
            df['Notes'] = ""

        df['Original Currency'] = detected_currency

        for col in ['Amount', 'Price', 'Fee']:
            if col in df.columns:
                val_str = df[col].astype(str).replace(['nan', 'None', ''], '0')
                val_str = val_str.str.replace(',', '', regex=False)
                df[col] = pd.to_numeric(val_str, errors='coerce').fillna(0)

        df['Notes'] = df['Notes'].fillna("").astype(str)

        if 'Type' in df.columns:
            df['Type'] = df['Type'].astype(str).str.lower()
            df['Type'] = df['Type'].apply(
                lambda x: 'buy' if 'in' in x or 'buy' in x or 'receive' in x
                else ('sell' if 'out' in x or 'sell' in x or 'send' in x else 'unknown')
            )
        else:
            df['Type'] = df['Amount'].apply(lambda x: 'sell' if x < 0 else 'buy')
            df['Amount'] = df['Amount'].abs()

        for col in cls.FINAL_COLUMNS:
            if col not in df.columns:
                df[col] = "" if col == 'Notes' else 0

        return df[cls.FINAL_COLUMNS]

    @classmethod
    def import_from_csv(cls, file_paths: List[str]) -> List[pd.DataFrame]:
        """
        Import transactions from multiple CSV files.

        Args:
            file_paths (List[str]): List of CSV file paths.

        Returns:
            List[pd.DataFrame]: List of cleaned DataFrames (one per file).
        """
        dfs = []
        for file_path in file_paths:
            try:
                try:
                    df = pd.read_csv(file_path)
                except Exception:
                    df = pd.read_csv(file_path, sep=';')

                if df.empty or len(df.columns) <= 1:
                    continue

                df.columns = [c.strip() for c in df.columns]
                columns_set = set(df.columns)

                if cls.CRYPTO_COM_SIGNATURE.issubset(columns_set):
                    parsed = cls._parse_crypto_com(df)
                elif cls.NEXO_SIGNATURE.issubset(columns_set):
                    parsed = cls._parse_nexo(df)
                else:
                    parsed = cls._parse_generic(df, file_path)

                if parsed is not None and not parsed.empty:
                    dfs.append(parsed)

            except Exception as e:
                print(f"Errore importazione {file_path}: {e}")

        return dfs
