"""
CryptoAssistant - Main Entry Point
A tool for managing cryptocurrency portfolios with fiscal reporting.
"""

import sys
import warnings
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore")

# PyQt6 imports
from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog
from PyQt6.QtCore import Qt

# Local imports (now absolute)
from api.frankfurter import HistoricalRatesWorker, get_live_exchange_rate
from api.coinmarketcap import CoinMarketCapAPI
from data.database import TransactionDatabase
from data.importer import CSVImporter
from gui.main_window import TradingTerminalWindow
from utils.config import get_user_data_dir, load_config, save_config


def get_project_root() -> Path:
    """Get the project root directory (usata solo per risorse di sola lettura, es. version.txt)."""
    return Path(__file__).parent.parent


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
    app.setStyle("Fusion")

    try:
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

        # Initialize database (i dati vengono salvati nella cartella utente scrivibile)
        db_file = get_user_data_dir() / config.get("data_file", "transactions.csv")
        database = TransactionDatabase(str(db_file))
    except OSError as e:
        QMessageBox.critical(
            None,
            "Errore di configurazione",
            f"Impossibile leggere o salvare i dati dell'applicazione:\n\n{e}\n\n"
            "Verifica di avere i permessi di scrittura nella cartella utente."
        )
        sys.exit(1)
    
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
