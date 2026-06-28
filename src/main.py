"""
CryptoAssistant - Main Entry Point
A tool for managing cryptocurrency portfolios with fiscal reporting.
"""

import sys
import os
import json
import warnings
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore")

# PyQt6 imports
from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog
from PyQt6.QtCore import Qt

# Local imports (now absolute)
from src.api.frankfurter import HistoricalRatesWorker, get_live_exchange_rate
from src.api.coinmarketcap import CoinMarketCapAPI
from src.data.database import TransactionDatabase
from src.data.importer import CSVImporter
from src.gui.main_window import TradingTerminalWindow


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def load_config() -> dict:
    """Load configuration from config/config.json."""
    config_path = get_project_root() / "config" / "config.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            return json.load(f)
    return {"api_key": None, "default_currency": "EUR"}


def save_config(config: dict) -> None:
    """Save configuration to config/config.json."""
    config_path = get_project_root() / "config" / "config.json"
    config_dir = config_path.parent
    if not config_dir.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)


def get_api_key_from_user() -> str:
    """
    Show a dialog to input the CoinMarketCap API Key.
    Returns the API Key if provided, empty string otherwise.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Show input dialog
    key, ok = QInputDialog.getText(
        None,
        "Configurazione API",
        "Inserisci la tua API Key di CoinMarketCap:\n\n"
        "(Puoi ottenerla gratuitamente da: https://coinmarketcap.com/api/)"
    )
    
    if ok and key:
        return key.strip()
    return ""


def main():
    """Main entry point for the application."""
    # Create QApplication first to ensure GUI is available
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Load configuration
    config = load_config()
    api_key = config.get("api_key")
    
    # If API Key is missing or placeholder, ask the user
    if not api_key or api_key == "INSERISCI_LA_TUA_API_KEY_COINMARKETCAP":
        api_key = get_api_key_from_user()
        if api_key:
            config["api_key"] = api_key
            save_config(config)
        else:
            # User cancelled, exit gracefully
            sys.exit(0)
    
    # Initialize database
    db_file = get_project_root() / config.get("data_file", "data/transactions.csv")
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
