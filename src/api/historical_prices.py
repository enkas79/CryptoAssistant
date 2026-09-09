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
