"""
Rivalutazione dei prezzi storici delle transazioni.

I CSV di alcuni wallet non contengono prezzi EUR affidabili: righe a prezzo 0
(reward/airdrop) e talvolta prezzi presi da fonti diverse (o in USD). Questo
modulo ri-scarica il prezzo di mercato alla data di ogni transazione tramite
un provider storico (CoinMarketCap con fallback CoinGecko).
"""

from typing import Callable, Dict, List, Tuple

import pandas as pd

try:  # PyQt6 assente in ambiente di test puro
    from PyQt6.QtCore import QThread, pyqtSignal
except Exception:  # pragma: no cover
    QThread = object

    def pyqtSignal(*_a, **_k):
        return None


def _righe_target(df: pd.DataFrame, mode: str) -> pd.Index:
    tipo = df['Type'].astype(str).str.lower()
    is_buy = tipo == 'buy'
    is_sell = tipo == 'sell'
    if mode == 'all':
        mask = is_buy | (is_sell & (df['Price'] > 0))
    else:  # 'missing'
        mask = is_buy & (df['Price'] <= 0)
    return df.index[mask]


def _lookup_serie(serie: Dict[str, float], giorno_str: str) -> float:
    """Prezzo del giorno, con tolleranza +/- 2 giorni se il giorno esatto manca."""
    if giorno_str in serie:
        return serie[giorno_str]
    base = pd.Timestamp(giorno_str)
    for delta in (1, -1, 2, -2):
        k = (base + pd.Timedelta(days=delta)).strftime("%Y-%m-%d")
        if k in serie:
            return serie[k]
    return None


def rivaluta_transazioni(
    df: pd.DataFrame,
    price_fn: Callable[[str, object], float],
    mode: str = "missing",
    progress_cb: Callable[[int, int], None] = None,
    series_fn: Callable[[str, object, object], Dict[str, float]] = None,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Args:
        df: transazioni (colonne standard, 'Date (UTC+1:00)' in datetime).
        price_fn: funzione (symbol, data) -> prezzo EUR o None (fallback per
            singolo giorno).
        mode: "missing" (solo acquisti a prezzo 0) o "all" (tutti gli
            acquisti e le vendite gia' valorizzate).
        progress_cb: callback opzionale (fatte, totale).
        series_fn: funzione (symbol, data_inizio, data_fine) -> {"YYYY-MM-DD": prezzo}.
            Se fornita, si scarica UNA serie per token (molto piu' veloce e
            rispettoso dei rate limit) invece di una chiamata per giorno.

    Returns:
        (df aggiornato, report) con report = {"aggiornate": int,
        "non_trovate": list[(token, "YYYY-MM-DD")]}.
    """
    out = df.copy()
    target = _righe_target(out, mode)

    # Coppie (token, giorno) da valorizzare e range date per ogni token.
    coppie: List[Tuple[str, pd.Timestamp]] = []
    per_token_range: Dict[str, list] = {}
    for idx in target:
        tok = str(out.at[idx, 'Token'])
        giorno = pd.Timestamp(out.at[idx, 'Date (UTC+1:00)']).normalize()
        if (tok, giorno) not in coppie:
            coppie.append((tok, giorno))
        r = per_token_range.setdefault(tok, [giorno, giorno])
        r[0], r[1] = min(r[0], giorno), max(r[1], giorno)

    prezzi: Dict[Tuple[str, str], float] = {}
    non_trovate: List[Tuple[str, str]] = []

    serie_per_token: Dict[str, Dict[str, float]] = {}
    if series_fn is not None:
        for tok, (dmin, dmax) in per_token_range.items():
            try:
                serie_per_token[tok] = series_fn(tok, dmin.date(), dmax.date()) or {}
            except Exception:
                serie_per_token[tok] = {}

    for i, (tok, giorno) in enumerate(coppie):
        giorno_str = giorno.strftime("%Y-%m-%d")
        p = _lookup_serie(serie_per_token.get(tok, {}), giorno_str)
        if p is None:
            p = price_fn(tok, giorno) if price_fn is not None else None
        if p is not None and p > 0:
            prezzi[(tok.upper(), giorno_str)] = float(p)
        else:
            non_trovate.append((tok, giorno_str))
        if progress_cb:
            progress_cb(i + 1, len(coppie))

    aggiornate = 0
    for idx in target:
        tok = str(out.at[idx, 'Token']).upper()
        giorno_str = pd.Timestamp(out.at[idx, 'Date (UTC+1:00)']).strftime("%Y-%m-%d")
        if (tok, giorno_str) in prezzi:
            out.at[idx, 'Price'] = prezzi[(tok, giorno_str)]
            aggiornate += 1

    return out, {"aggiornate": aggiornate, "non_trovate": non_trovate}


class RepriceWorker(QThread):
    """Esegue rivaluta_transazioni in background."""

    progresso = pyqtSignal(int, int)
    finito = pyqtSignal(object, dict)

    def __init__(self, df: pd.DataFrame, provider, mode: str = "missing"):
        super().__init__()
        self._df = df
        self._provider = provider
        self._mode = mode

    def run(self) -> None:  # pragma: no cover - thread Qt
        prov = self._provider
        out, report = rivaluta_transazioni(
            self._df,
            price_fn=getattr(prov, "get_historical_price", None),
            mode=self._mode,
            progress_cb=lambda a, b: self.progresso.emit(a, b),
            series_fn=getattr(prov, "get_price_series", None),
        )
        self.finito.emit(out, report)
