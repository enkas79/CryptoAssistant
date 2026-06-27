"""
CryptoAssistant - Main Entry Point
A tool for managing cryptocurrency portfolios with fiscal reporting.
"""

import sys
import os
import json
import warnings
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Suppress warnings
warnings.filterwarnings("ignore")

# PyQt6 imports
from PyQt6.QtWidgets import QApplication

# Local imports (now absolute)
from api.frankfurter import HistoricalRatesWorker, get_live_exchange_rate
from api.coinmarketcap import CoinMarketCapAPI
from data.database import TransactionDatabase
from data.importer import CSVImporter
from gui.main_window import TradingTerminalWindow


def load_config() -> dict:
    """Load configuration from config/config.json."""
    config_path = project_root / "config" / "config.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            return json.load(f)
    return {"api_key": None, "default_currency": "EUR"}


def main():
    """Main entry point for the application."""
    # Load configuration
    config = load_config()
    api_key = config.get("api_key")
    
    if not api_key or api_key == "INSERISCI_LA_TUA_API_KEY_COINMARKETCAP":
        print("Errore: API Key CoinMarketCap non configurata.")
        print("Aggiungi la tua API Key in config/config.json")
        sys.exit(1)
    
    # Initialize database
    db_file = project_root / config.get("data_file", "data/transactions.csv")
    database = TransactionDatabase(str(db_file))
    
    # Initialize API clients
    cmc_api = CoinMarketCapAPI(api_key)
    
    # Initialize currency converter
    currency = config.get("default_currency", "EUR")
    from utils.currency import CurrencyConverter
    currency_converter = CurrencyConverter(default_currency=currency)
    
    # Set live exchange rate
    if currency == "EUR":
        live_rate = get_live_exchange_rate(base="USD", target="EUR")
        currency_converter.set_live_rate(live_rate)
    
    # Create and run the application
    app = QApplication(sys.argv)
    
    # Initialize the main window with all dependencies
    window = TradingTerminalWindow(
        database=database,
        cmc_api=cmc_api,
        currency_converter=currency_converter,
        config=config
    )
    
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
