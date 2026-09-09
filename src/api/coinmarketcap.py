"""
CoinMarketCap API Module
Handles fetching live and historical cryptocurrency prices from CoinMarketCap.
"""

import json
import os
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests
from PyQt6.QtCore import QThread, pyqtSignal


class CoinMarketCapAPI:
    """
    Client for CoinMarketCap API to fetch live and historical prices.
    """

    BASE_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    HISTORICAL_URL = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/historical"
    REQUEST_TIMEOUT = 15  # seconds

    def __init__(self, api_key, cache_path: Optional[str] = None):
        """
        Initialize the client with an API key.

        Args:
            api_key (str): CoinMarketCap API key.
            cache_path (Optional[str]): file JSON dove memorizzare le quotazioni
                storiche gia' scaricate (l'endpoint historical e' a consumo).
        """
        self.api_key = api_key
        self.headers = {'X-CMC_PRO_API_KEY': self.api_key}
        self.cache_path = cache_path
        self._cache: Dict[str, float] = {}
        if cache_path and os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as fh:
                    self._cache = json.load(fh)
            except Exception:
                self._cache = {}

    def _save_cache(self) -> None:
        if not self.cache_path:
            return
        try:
            with open(self.cache_path, "w", encoding="utf-8") as fh:
                json.dump(self._cache, fh)
        except Exception:
            pass

    def get_historical_price(self, symbol: str, on_date, convert: str = "EUR") -> Optional[float]:
        """
        Quotazione di `symbol` alla data indicata (chiusura giornaliera), nella
        valuta `convert`. Restituisce None se l'endpoint historical non e'
        disponibile per il piano dell'API key o in caso di errore/rete assente.
        """
        sym = str(symbol).upper()
        day = on_date.strftime("%Y-%m-%d") if isinstance(on_date, (datetime, date)) else str(on_date)
        key = f"{sym}|{day}|{convert}"
        if key in self._cache:
            return self._cache[key]

        try:
            start = datetime.strptime(day, "%Y-%m-%d")
            resp = requests.get(
                self.HISTORICAL_URL,
                params={
                    "symbol": sym,
                    "convert": convert,
                    "time_start": start.strftime("%Y-%m-%dT00:00:00Z"),
                    "time_end": (start + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z"),
                    "interval": "24h",
                    "count": 1,
                },
                headers=self.headers,
                timeout=self.REQUEST_TIMEOUT,
            )
            payload = resp.json()
            data = payload.get("data")
            if not data:
                return None
            entry = data.get(sym) if isinstance(data, dict) else None
            if isinstance(entry, list):
                entry = entry[0] if entry else None
            quotes = (entry or {}).get("quotes") or []
            if not quotes:
                return None
            price = quotes[0].get("quote", {}).get(convert, {}).get("price")
            if price is None:
                return None
            price = float(price)
        except Exception:
            return None

        self._cache[key] = price
        self._save_cache()
        return price

    def get_prices_for_year_bounds(
        self, symbols: List[str], year: int, convert: str = "EUR"
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Restituisce (prezzi_1_gennaio, prezzi_31_dicembre) in EUR."""
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        prices_start: Dict[str, float] = {}
        prices_end: Dict[str, float] = {}
        for sym in {str(s).upper() for s in symbols}:
            ps = self.get_historical_price(sym, start, convert)
            pe = self.get_historical_price(sym, end, convert)
            if ps is not None:
                prices_start[sym] = ps
            if pe is not None:
                prices_end[sym] = pe
        return prices_start, prices_end

    def get_live_prices(self, symbols, convert="USD"):
        """
        Fetch live prices for a list of cryptocurrency symbols.

        Args:
            symbols (list): List of cryptocurrency symbols (e.g., ["BTC", "ETH"]).
            convert (str): Currency to convert prices to (default: "USD").

        Returns:
            dict: Dictionary of {symbol: price} in the target currency.
        """
        prices = {symbol: 0 for symbol in symbols}
        try:
            params = {'symbol': ",".join(symbols), 'convert': convert}
            response = requests.get(
                self.BASE_URL,
                headers=self.headers,
                params=params,
                timeout=self.REQUEST_TIMEOUT
            ).json()

            if 'data' in response:
                for symbol in symbols:
                    try:
                        price = response['data'][symbol]['quote'][convert]['price']
                        prices[symbol] = price if price is not None else 0
                    except KeyError:
                        prices[symbol] = 0
            else:
                print(f"Errore API CoinMarketCap: {response.get('status', {}).get('error_message', 'Unknown error')}")
        except Exception as e:
            print(f"Errore API CoinMarketCap: {e}")

        return prices


class LivePricesWorker(QThread):
    """
    Worker thread to fetch live cryptocurrency prices from CoinMarketCap
    without blocking the GUI thread.
    """
    finished = pyqtSignal(dict)

    def __init__(self, cmc_api: CoinMarketCapAPI, symbols, convert="USD"):
        """
        Initialize the worker.

        Args:
            cmc_api (CoinMarketCapAPI): API client to use for the request.
            symbols (list): List of cryptocurrency symbols to fetch.
            convert (str): Currency to convert prices to (default: "USD").
        """
        super().__init__()
        self.cmc_api = cmc_api
        self.symbols = symbols
        self.convert = convert

    def run(self):
        """Fetch live prices and emit the result."""
        prices = self.cmc_api.get_live_prices(self.symbols, convert=self.convert)
        self.finished.emit(prices)
