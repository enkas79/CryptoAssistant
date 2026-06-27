"""
CSV Importer Module for CryptoAssistant
Handles importing transactions from various CSV formats (Binance, CoinMarketCap, etc.).
"""

import os
import pandas as pd
from typing import List, Optional


class CSVImporter:
    """
    Imports transactions from CSV files with various formats.
    """
    
    # Mappings for column detection
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
    
    @classmethod
    def detect_column(cls, columns: List[str], keywords: List[str]) -> Optional[str]:
        """
        Detect a column by keywords in its name.
        
        Args:
            columns (List[str]): List of column names.
            keywords (List[str]): Keywords to match.
        
        Returns:
            Optional[str]: Matching column name or None.
        """
        for col in columns:
            if any(keyword in col.upper() for keyword in keywords):
                return col
        return None
    
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
                # Try reading with default separator
                try:
                    df = pd.read_csv(file_path)
                except:
                    # Try with semicolon separator
                    df = pd.read_csv(file_path, sep=';')
                
                if df.empty or len(df.columns) <= 1:
                    continue
                
                # Clean column names
                df.columns = [c.strip() for c in df.columns]
                
                # Detect columns
                col_data = cls.detect_column(df.columns, cls.DATE_KEYWORDS)
                col_token = cls.detect_column(df.columns, cls.TOKEN_KEYWORDS)
                col_type = cls.detect_column(df.columns, cls.TYPE_KEYWORDS)
                col_amount = cls.detect_column(df.columns, cls.AMOUNT_KEYWORDS)
                col_price = cls.detect_column(df.columns, cls.PRICE_KEYWORDS)
                col_fee = cls.detect_column(df.columns, cls.FEE_KEYWORDS)
                col_notes = cls.detect_column(df.columns, cls.NOTES_KEYWORDS)
                
                # Create rename dictionary
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
                
                # Detect currency from price column
                detected_currency = 'EUR'
                if col_price and 'USD' in col_price.upper():
                    detected_currency = 'USD'
                
                # Rename columns
                df = df.rename(columns=rename_dict)
                
                # Add missing columns
                if 'Token' not in df.columns:
                    df['Token'] = os.path.basename(file_path).split('.')[0].upper()
                if 'Price' not in df.columns:
                    df['Price'] = 0
                if 'Fee' not in df.columns:
                    df['Fee'] = 0
                if 'Notes' not in df.columns:
                    df['Notes'] = ""
                
                # Set original currency
                df['Original Currency'] = detected_currency
                
                # Clean numeric columns
                for col in ['Amount', 'Price', 'Fee']:
                    if col in df.columns:
                        val_str = df[col].astype(str).replace(['nan', 'None', ''], '0')
                        val_str = val_str.str.replace(',', '', regex=False)
                        df[col] = pd.to_numeric(val_str, errors='coerce').fillna(0)
                
                df['Notes'] = df['Notes'].fillna("").astype(str)
                
                # Convert Type to lowercase and standardize
                if 'Type' in df.columns:
                    df['Type'] = df['Type'].astype(str).str.lower()
                    df['Type'] = df['Type'].apply(
                        lambda x: 'buy' if 'in' in x or 'buy' in x or 'receive' in x 
                        else ('sell' if 'out' in x or 'sell' in x or 'send' in x else 'unknown')
                    )
                else:
                    # Infer type from Amount sign
                    df['Type'] = df['Amount'].apply(lambda x: 'sell' if x < 0 else 'buy')
                    df['Amount'] = df['Amount'].abs()
                
                # Ensure all final columns exist
                for col in cls.FINAL_COLUMNS:
                    if col not in df.columns:
                        df[col] = "" if col == 'Notes' else 0
                
                dfs.append(df[cls.FINAL_COLUMNS])
                
            except Exception as e:
                print(f"Errore importazione {file_path}: {e}")
        
        return dfs
