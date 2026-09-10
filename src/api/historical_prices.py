"""
Provider a catena per le quotazioni storiche.

Interroga i provider in ordine (es. CoinMarketCap con l'API key dell'utente,
poi CoinGecko come fallback gratuito) e unisce i risultati: ogni token viene
valorizzato dal primo provider che lo restituisce.
"""

from typing import Dict, List, Tuple


class ChainedHistoricalPrices:
    """Combina piu' provider con interfaccia get_prices_for_year_bounds()."""

    def __init__(self, providers: List[object]):
        self._providers = list(providers)

    def get_price_series(self, symbol: str, start_date, end_date) -> Dict[str, float]:
        """Serie giornaliera unendo i provider (il primo che copre un giorno vince)."""
        serie: Dict[str, float] = {}
        for provider in self._providers:
            fn = getattr(provider, "get_price_series", None)
            if fn is None:
                continue
            try:
                parziale = fn(symbol, start_date, end_date) or {}
            except Exception:
                parziale = {}
            for giorno, prezzo in parziale.items():
                serie.setdefault(giorno, prezzo)
        return serie

    def get_historical_price(self, symbol: str, on_date):
        """Prezzo di `symbol` alla data: primo provider che lo restituisce."""
        for provider in self._providers:
            fn = getattr(provider, "get_historical_price", None)
            if fn is None:
                continue
            try:
                price = fn(symbol, on_date)
            except Exception:
                continue
            if price is not None:
                return price
        return None

    def get_prices_for_year_bounds(
        self, symbols: List[str], year: int
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        richiesti = {str(s).upper() for s in symbols}
        start: Dict[str, float] = {}
        end: Dict[str, float] = {}

        for provider in self._providers:
            mancanti = [s for s in richiesti if s not in start or s not in end]
            if not mancanti:
                break
            try:
                p_start, p_end = provider.get_prices_for_year_bounds(mancanti, year)
            except Exception:
                continue
            for sym, val in (p_start or {}).items():
                start.setdefault(str(sym).upper(), val)
            for sym, val in (p_end or {}).items():
                end.setdefault(str(sym).upper(), val)

        return start, end
