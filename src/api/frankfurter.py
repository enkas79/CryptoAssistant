"""
Frankfurter API Module
Handles fetching historical and live exchange rates (USD -> EUR) from Frankfurter API.
"""

import requests
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal


class HistoricalRatesWorker(QThread):
    """
    Worker thread to download historical exchange rates from Frankfurter API.
    Emits a signal with the rates dictionary when done.
    """
    finished = pyqtSignal(dict)

    def __init__(self, start_date, end_date, base="USD", target="EUR"):
        """
        Initialize the worker with date range and currency pair.
        
        Args:
            start_date (datetime): Start date for historical rates.
            end_date (datetime): End date for historical rates.
            base (str): Base currency (default: "USD").
            target (str): Target currency (default: "EUR").
        """
        super().__init__()
        self.start_date = start_date
        self.end_date = end_date
        self.base = base
        self.target = target

    def run(self):
        """Fetch historical rates and emit the result."""
        rates = {}
        try:
            start_str = self.start_date.strftime("%Y-%m-%d")
            end_str = self.end_date.strftime("%Y-%m-%d")
            url = f"https://api.frankfurter.app/{start_str}..{end_str}?from={self.base}&to={self.target}"
            res = requests.get(url).json()
            if 'rates' in res:
                for date_str, rate_dict in res['rates'].items():
                    rates[date_str] = rate_dict.get(self.target, 1.0)
        except Exception as e:
            print(f"Errore download storico cambi: {e}")
        self.finished.emit(rates)


def get_live_exchange_rate(base="USD", target="EUR"):
    """
    Fetch the live exchange rate from Frankfurter API.
    
    Args:
        base (str): Base currency (default: "USD").
        target (str): Target currency (default: "EUR").
    
    Returns:
        float: Exchange rate (target per 1 base). Falls back to 0.92 if error.
    """
    try:
        url = f"https://api.frankfurter.app/latest?from={base}&to={target}"
        res = requests.get(url).json()
        return res['rates'][target]
    except Exception as e:
        print(f"Errore download tasso live: {e}")
        return 0.92  # Fallback
