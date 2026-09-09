"""
CoinGecko API Module
Recupero delle quotazioni STORICHE in EUR delle cripto-attività, necessarie
per valorizzare il Quadro RW (valore all'1/1 e al 31/12) e l'imposta
cripto-attività. Usa l'endpoint pubblico gratuito (nessuna API key) e una
cache su file per non ripetere le chiamate a ogni calcolo.
"""

import json
import os
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import requests

try:  # PyQt6 è assente in ambiente di test puro
    from PyQt6.QtCore import QThread, pyqtSignal
except Exception:  # pragma: no cover - fallback per i test
    QThread = object

    def pyqtSignal(*_a, **_k):
        return None


class CoinGeckoAPI:
    """Client per le quotazioni storiche giornaliere di CoinGecko."""

    BASE_URL = "https://api.coingecko.com/api/v3"
    REQUEST_TIMEOUT = 15  # secondi

    # Mappa simbolo -> id CoinGecko per i token presenti nei portafogli.
    SYMBOL_TO_ID = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "LINK": "chainlink",
        "XLM": "stellar",
        "LTC": "litecoin",
        "TRX": "tron",
        "TON": "the-open-network",
        "GRAM": "the-open-network",  # i "Gram" delle prevendite Telegram sono confluiti in TON
        "USDT": "tether",
        "USDC": "usd-coin",
        "ADA": "cardano",
        "DOT": "polkadot",
        "MATIC": "matic-network",
        "AVAX": "avalanche-2",
        "XRP": "ripple",
        "DOGE": "dogecoin",
        "BNB": "binancecoin",
        "NEAR": "near",
        "SUI": "sui",
        "RENDER": "render-token",
        "INJ": "injective-protocol",
        "ONDO": "ondo-finance",
        "JUP": "jupiter-exchange-solana",
    }

    def __init__(self, cache_path: Optional[str] = None):
        """
        Args:
            cache_path: percorso di un file JSON dove salvare i prezzi già
                scaricati. Se None la cache è solo in memoria.
        """
        self.cache_path = cache_path
        self._cache: Dict[str, float] = {}
        if cache_path and os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as fh:
                    self._cache = json.load(fh)
            except Exception:
                self._cache = {}

    @staticmethod
    def _date_str(on_date) -> str:
        if isinstance(on_date, (datetime, date)):
            return on_date.strftime("%d-%m-%Y")
        return str(on_date)

    def _save_cache(self) -> None:
        if not self.cache_path:
            return
        try:
            with open(self.cache_path, "w", encoding="utf-8") as fh:
                json.dump(self._cache, fh)
        except Exception:
            pass

    def get_historical_price(self, symbol: str, on_date, vs: str = "eur") -> Optional[float]:
        """
        Quotazione di `symbol` alla data indicata, nella valuta `vs` (default EUR).
        Restituisce None per token non mappati o in caso di errore/rete assente.
        """
        coin_id = self.SYMBOL_TO_ID.get(str(symbol).upper())
        if not coin_id:
            return None

        date_str = self._date_str(on_date)
        key = f"{coin_id}|{date_str}|{vs}"
        if key in self._cache:
            return self._cache[key]

        try:
            resp = requests.get(
                f"{self.BASE_URL}/coins/{coin_id}/history",
                params={"date": date_str, "localization": "false"},
                timeout=self.REQUEST_TIMEOUT,
                headers={"accept": "application/json"},
            )
            payload = resp.json()
            price = payload.get("market_data", {}).get("current_price", {}).get(vs)
            if price is None:
                return None
            price = float(price)
        except Exception:
            return None

        self._cache[key] = price
        self._save_cache()
        return price

    def get_prices_for_year_bounds(
        self, symbols: List[str], year: int
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Restituisce (prezzi_1_gennaio, prezzi_31_dicembre) in EUR per i simboli
        indicati. I token non recuperabili restano assenti dai dizionari.
        """
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        prices_start: Dict[str, float] = {}
        prices_end: Dict[str, float] = {}
        for sym in {str(s).upper() for s in symbols}:
            ps = self.get_historical_price(sym, start)
            pe = self.get_historical_price(sym, end)
            if ps is not None:
                prices_start[sym] = ps
            if pe is not None:
                prices_end[sym] = pe
        return prices_start, prices_end


class HistoricalPricesWorker(QThread):
    """Recupera in background le quotazioni di inizio/fine anno."""

    finished = pyqtSignal(dict, dict)

    def __init__(self, api: "CoinGeckoAPI", symbols: List[str], year: int):
        super().__init__()
        self.api = api
        self.symbols = symbols
        self.year = year

    def run(self) -> None:  # pragma: no cover - thread Qt
        start, end = self.api.get_prices_for_year_bounds(self.symbols, self.year)
        self.finished.emit(start, end)
