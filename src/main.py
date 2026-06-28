"""
CryptoAssistant - Main Entry Point
A tool for managing cryptocurrency portfolios with fiscal reporting.
"""

import sys
import os
import json
import warnings
from pathlib import Path

# Add src directory to Python path
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Suppress warnings
warnings.filterwarnings("ignore")

# Initialize logging first
from utils.logger import setup_logging
logger = setup_logging(log_level="INFO")

# PyQt6 imports
from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog
from PyQt6.QtCore import Qt

# Local imports (now absolute)
from api.frankfurter import HistoricalRatesWorker, get_live_exchange_rate
from api.coinmarketcap import CoinMarketCapAPI
from data.database import TransactionDatabase
from data.importer import CSVImporter
from gui.main_window import TradingTerminalWindow


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
    logger.info("Starting CryptoAssistant application...")
    
    # Create QApplication first to ensure GUI is available
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    logger.info("QApplication initialized")
    
    # Load configuration
    config = load_config()
    logger.info(f"Configuration loaded: {config.get('default_currency', 'EUR')} currency")
    
    api_key = config.get("api_key")
    
    # If API Key is missing or placeholder, ask the user
    if not api_key or api_key == "INSERISCI_LA_TUA_API_KEY_COINMARKETCAP":
        logger.warning("API Key not found or is placeholder, requesting from user...")
        api_key = get_api_key_from_user()
        if api_key:
            config["api_key"] = api_key
            save_config(config)
            logger.info("API Key saved to configuration")
        else:
            logger.warning("User cancelled API Key input, exiting...")
            sys.exit(0)
    
    # Initialize database
    db_file = get_project_root() / config.get("data_file", "data/transactions.csv")
    logger.info(f"Initializing database from: {db_file}")
    database = TransactionDatabase(str(db_file))
    
    # Initialize API clients
    logger.info("Initializing CoinMarketCap API client...")
    cmc_api = CoinMarketCapAPI(api_key)
    
    # Initialize currency converter
    currency = config.get("default_currency", "EUR")
    logger.info(f"Initializing currency converter with currency: {currency}")
    from utils.currency import CurrencyConverter
    currency_converter = CurrencyConverter(default_currency=currency)
    
    # Set live exchange rate
    if currency == "EUR":
        logger.info("Fetching live exchange rate (USD to EUR)...")
        live_rate = get_live_exchange_rate(base="USD", target="EUR")
        currency_converter.set_live_rate(live_rate)
        logger.info(f"Live exchange rate set: {live_rate}")
    
    # Create and run the application
    logger.info("Creating main window...")
    window = TradingTerminalWindow(
        database=database,
        cmc_api=cmc_api,
        currency_converter=currency_converter,
        config=config
    )
    
    logger.info("Showing main window...")
    window.showMaximized()
    logger.info("Application started successfully")
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
