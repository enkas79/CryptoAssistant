"""
Database Module for CryptoAssistant
Handles loading, saving, and cleaning transaction data from CSV.
"""

import os
import pandas as pd
from datetime import datetime
from typing import Optional
from .models import Transaction, CurrentData


class TransactionDatabase:
    """
    Manages transaction data stored in a CSV file.
    """
    
    DEFAULT_COLUMNS = [
        'Date (UTC+1:00)', 'Token', 'Type', 'Amount', 
        'Price', 'Fee', 'Notes', 'Original Currency'
    ]
    
    def __init__(self, db_file: str = "data_history.csv"):
        """
        Initialize the database with a CSV file path.
        
        Args:
            db_file (str): Path to the CSV file.
        """
        self.db_file = db_file
        self.df = self._load_existing_database()
    
    def _load_existing_database(self) -> Optional[pd.DataFrame]:
        """Load existing database from CSV file."""
        if os.path.exists(self.db_file):
            try:
                df = pd.read_csv(self.db_file)
                return self._clean_dataframe(df)
            except Exception as e:
                print(f"Errore caricamento database: {e}")
                return None
        return None
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and normalize the DataFrame.
        
        Args:
            df (pd.DataFrame): Raw DataFrame from CSV.
        
        Returns:
            pd.DataFrame: Cleaned DataFrame.
        """
        # Rename columns for compatibility
        rename_map = {
            'Price (USD)': 'Price',
            'Total value (USD)': 'Total value'
        }
        df = df.rename(columns=rename_map)
        
        # Add missing columns
        if 'Price' not in df.columns:
            df['Price'] = 0.0
        if 'Date (UTC+1:00)' in df.columns:
            df['Date (UTC+1:00)'] = pd.to_datetime(df['Date (UTC+1:00)'], dayfirst=True, errors='coerce')
        if 'Original Currency' not in df.columns:
            df['Original Currency'] = 'EUR'
        if 'Notes' not in df.columns:
            df['Notes'] = ""
        
        # Clean numeric columns
        numeric_cols = ['Amount', 'Price', 'Fee']
        for col in numeric_cols:
            if col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].astype(str).str.replace(',', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                df[col] = df[col].round(8)
        
        df['Notes'] = df['Notes'].fillna("").astype(str)
        
        # Auto-tagging for Earn/Staking/Airdrop
        def auto_tag_zero_cost(row):
            if str(row.get('Type', '')).lower() == 'buy' and float(row.get('Price', 0)) == 0:
                current_note = str(row['Notes'])
                tag = "Earn/Staking/Airdrop"
                if tag not in current_note:
                    return (current_note + " " + tag).strip()
            return row['Notes']
        
        df['Notes'] = df.apply(auto_tag_zero_cost, axis=1)
        return df
    
    def save(self) -> bool:
        """Save the current DataFrame to CSV."""
        if self.df is not None:
            try:
                self.df.to_csv(self.db_file, index=False)
                return True
            except Exception as e:
                print(f"Errore salvataggio database: {e}")
                return False
        return False
    
    def add_transactions(self, new_df: pd.DataFrame) -> int:
        """
        Add new transactions to the database.
        
        Args:
            new_df (pd.DataFrame): New transactions to add.
        
        Returns:
            int: Number of rows added.
        """
        if self.df is None:
            self.df = new_df
            return len(new_df)
        
        # Clean the new DataFrame
        new_df = self._clean_dataframe(new_df)
        
        # Combine and remove duplicates
        combined = pd.concat([self.df, new_df]).drop_duplicates(
            subset=['Date (UTC+1:00)', 'Token', 'Type', 'Amount', 'Notes'],
            keep='first'
        )
        
        rows_added = len(combined) - len(self.df)
        self.df = combined
        
        # Sort by date (newest first)
        if 'Date (UTC+1:00)' in self.df.columns:
            self.df = self.df.sort_values(by='Date (UTC+1:00)', ascending=False)
        
        return rows_added
    
    def get_dataframe(self) -> Optional[pd.DataFrame]:
        """Get the current DataFrame."""
        return self.df
    
    def get_tokens(self) -> list:
        """Get list of unique tokens in the database."""
        if self.df is not None and not self.df.empty:
            return sorted(self.df['Token'].astype(str).unique())
        return []
    
    def get_transactions_for_token(self, token: str) -> pd.DataFrame:
        """Get all transactions for a specific token."""
        if self.df is not None:
            return self.df[self.df['Token'] == token]
        return pd.DataFrame()
