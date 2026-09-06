"""
Dates Module for CryptoAssistant
Parsing robusto delle date delle transazioni.
"""

import pandas as pd


def parse_dates_safe(series: pd.Series) -> pd.Series:
    """
    Converte una colonna di date in datetime, gestendo sia il formato ISO
    (YYYY-MM-DD, usato da Nexo e dagli export generici) sia formati
    ambigui con giorno/mese invertibili (es. DD/MM/YYYY).

    Applicare 'dayfirst=True' direttamente a date ISO le corrompe: pandas
    può scambiare giorno e mese (o restituire NaT) quando il giorno è <= 12,
    perché l'anno a 4 cifre in prima posizione non basta a disambiguare la
    posizione di giorno/mese per il parser interno. Si prova quindi prima
    un parsing "naturale" (corretto per l'ISO, che non è mai ambiguo);
    solo i valori rimasti NaT vengono ritentati con dayfirst=True, per non
    perdere il supporto a formati DD/MM/YYYY da altre fonti.
    """
    parsed = pd.to_datetime(series, errors='coerce')
    if parsed.isna().any():
        mask = parsed.isna() & series.notna()
        if mask.any():
            fallback = pd.to_datetime(series[mask], dayfirst=True, errors='coerce')
            parsed.loc[mask] = fallback
    return parsed
