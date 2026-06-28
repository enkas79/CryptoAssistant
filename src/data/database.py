"""
Database Module for CryptoAssistant
Handles loading, saving, and cleaning transaction data from CSV.
"""

import os
import logging
import pandas as pd
from datetime import datetime
from typing import Optional
from models import Transaction, CurrentData

# Get module logger
logger = logging.getLogger(__name__)


class TransactionDatabase:
    """
    Manages transaction data stored in a CSV file.
    """
    
    DEFAULT_COLUMNS = [
        'Date (UTC+1:00)', 'Token', 'Type', 'Amount', 
        'Price', 'Fee', 'Notes', 'Original Currency'
    ]
    
    def __init__(self, db_file: str = "data_history.csv", enable_backup: bool = True):
        """
        Initialize the database with a CSV file path.
        
        Args:
            db_file (str): Path to the CSV file.
            enable_backup (bool): Whether to enable automatic backups.
        """
        self.db_file = db_file
        self.enable_backup = enable_backup
        self.backup_manager = None
        
        logger.info(f"Initializing TransactionDatabase with file: {db_file}")
        
        # Initialize backup manager if enabled
        if enable_backup:
            try:
                from utils.backup import BackupManager
                self.backup_manager = BackupManager(
                    data_file=db_file,
                    retention_days=30,
                    max_backups=10,
                    enabled=True
                )
                logger.info("Backup manager initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize backup manager: {e}")
                self.enable_backup = False
        
        self.df = self._load_existing_database()
        if self.df is not None:
            logger.info(f"Database loaded successfully with {len(self.df)} transactions")
        else:
            logger.warning(f"No existing database found at {db_file}, starting with empty database")
    
    def _load_existing_database(self) -> Optional[pd.DataFrame]:
        """Load existing database from CSV file."""
        if os.path.exists(self.db_file):
            try:
                logger.debug(f"Loading database from {self.db_file}")
                df = pd.read_csv(self.db_file)
                cleaned_df = self._clean_dataframe(df)
                logger.debug(f"Database loaded and cleaned, shape: {cleaned_df.shape}")
                return cleaned_df
            except Exception as e:
                logger.error(f"Error loading database: {e}")
                return None
        else:
            logger.debug(f"Database file not found: {self.db_file}")
        return None
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and normalize the DataFrame.
        
        Args:
            df (pd.DataFrame): Raw DataFrame from CSV.
        
        Returns:
            pd.DataFrame: Cleaned DataFrame.
        """
        logger.debug(f"Cleaning DataFrame with shape: {df.shape}")
        
        # Rename columns for compatibility
        rename_map = {
            'Price (USD)': 'Price',
            'Total value (USD)': 'Total value'
        }
        df = df.rename(columns=rename_map)
        
        # Add missing columns
        if 'Price' not in df.columns:
            logger.debug("Adding missing Price column")
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
        logger.debug(f"DataFrame cleaned, final shape: {df.shape}")
        return df
    
    def save(self) -> bool:
        """Save the current DataFrame to CSV."""
        if self.df is not None:
            try:
                logger.debug(f"Saving database to {self.db_file}")
                
                # Create backup before saving
                if self.enable_backup and self.backup_manager is not None:
                    self.backup_manager.create_backup(reason="before_save")
                
                self.df.to_csv(self.db_file, index=False)
                logger.info(f"Database saved successfully with {len(self.df)} transactions")
                return True
            except Exception as e:
                logger.error(f"Error saving database: {e}")
                return False
        else:
            logger.warning("Cannot save: DataFrame is None")
        return False
    
    def add_transactions(self, new_df: pd.DataFrame) -> int:
        """
        Add new transactions to the database.
        
        Args:
            new_df (pd.DataFrame): New transactions to add.
        
        Returns:
            int: Number of rows added.
        """
        logger.debug(f"Adding {len(new_df)} new transactions")
        
        if self.df is None:
            self.df = new_df
            logger.info(f"Database was empty, set to new DataFrame with {len(new_df)} transactions")
            return len(new_df)
        
        # Create backup before modifying
        if self.enable_backup and self.backup_manager is not None:
            self.backup_manager.create_backup(reason="before_add")
        
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
        
        logger.info(f"Added {rows_added} new transactions, total: {len(self.df)}")
        return rows_added
    
    def get_dataframe(self) -> Optional[pd.DataFrame]:
        """Get the current DataFrame."""
        logger.debug("Getting current DataFrame")
        return self.df
    
    def get_tokens(self) -> list:
        """Get list of unique tokens in the database."""
        if self.df is not None and not self.df.empty:
            tokens = sorted(self.df['Token'].astype(str).unique())
            logger.debug(f"Found {len(tokens)} unique tokens")
            return tokens
        logger.debug("No tokens found (empty database)")
        return []
    
    def get_transactions_for_token(self, token: str) -> pd.DataFrame:
        """Get all transactions for a specific token."""
        logger.debug(f"Getting transactions for token: {token}")
        if self.df is not None:
            result = self.df[self.df['Token'] == token]
            logger.debug(f"Found {len(result)} transactions for {token}")
            return result
        return pd.DataFrame()
    
    def get_backup_list(self) -> list:
        """
        Get a list of all available backups.
        
        Returns:
            list: List of backup info dictionaries.
        """
        if self.backup_manager is not None:
            return self.backup_manager.get_backup_list()
        return []
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        Restore a backup file to the original location.
        
        Args:
            backup_path (str): Path to the backup file to restore.
        
        Returns:
            bool: True if restore was successful.
        """
        if self.backup_manager is not None:
            return self.backup_manager.restore_backup(backup_path)
        return False
