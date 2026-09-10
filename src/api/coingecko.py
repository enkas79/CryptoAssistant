"""
CoinGecko API Module
Recupero delle quotazioni STORICHE in EUR delle cripto-attività, necessarie
per valorizzare il Quadro RW e per rivalutare i prezzi delle transazioni.
Usa l'API pubblica; una chiave "demo" gratuita (facoltativa) alza di molto i
limiti di frequenza. Cache su file per non ripetere le chiamate.
"""

import json
import os
import time
from datetime import date, datetime, timezone
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

    def __init__(self, cache_path: Optional[str] = None, api_key: Optional[str] = None):
        """
        Args:
            cache_path: percorso di un file JSON dove salvare i prezzi già
                scaricati. Se None la cache è solo in memoria.
            api_key: chiave "demo" gratuita di CoinGecko (facoltativa ma
                consigliata: senza chiave l'API pubblica è fortemente limitata).
        """
        self.cache_path = cache_path
        self._headers = {"accept": "application/json"}
        if api_key:
            self._headers["x-cg-demo-api-key"] = api_key
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

        price = None
        for tentativo in range(4):
            try:
                resp = requests.get(
                    f"{self.BASE_URL}/coins/{coin_id}/history",
                    params={"date": date_str, "localization": "false"},
                    timeout=self.REQUEST_TIMEOUT,
                    headers=self._headers,
                )
                if resp.status_code == 429:  # rate limit: attende e riprova
                    time.sleep(6 * (tentativo + 1))
                    continue
                payload = resp.json()
                price = payload.get("market_data", {}).get("current_price", {}).get(vs)
                break
            except Exception:
                return None

        if price is None:
            return None
        price = float(price)
        self._cache[key] = price
        self._save_cache()
        return price

    def get_price_series(self, symbol: str, start_date, end_date, vs: str = "eur") -> Dict[str, float]:
        """
        Serie storica giornaliera EUR di `symbol` tra le due date (incluse), in
        UNA sola chiamata (endpoint market_chart/range). Chiave: "YYYY-MM-DD".
        Dizionario vuoto per token non mappati o in caso di errore.
        """
        coin_id = self.SYMBOL_TO_ID.get(str(symbol).upper())
        if not coin_id:
            return {}

        def _ts(d):
            if isinstance(d, datetime):
                return int(d.replace(tzinfo=timezone.utc).timestamp())
            return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())

        # margine di 2 giorni per coprire i bordi
        frm = _ts(start_date) - 172800
        to = _ts(end_date) + 172800
        try:
            resp = requests.get(
                f"{self.BASE_URL}/coins/{coin_id}/market_chart/range",
                params={"vs_currency": vs, "from": frm, "to": to},
                timeout=self.REQUEST_TIMEOUT,
                headers=self._headers,
            )
            payload = resp.json()
            punti = payload.get("prices") or []
        except Exception:
            return {}

        serie: Dict[str, float] = {}
        for ts_ms, price in punti:
            giorno = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            serie[giorno] = float(price)  # ultimo punto del giorno prevale
        return serie

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
