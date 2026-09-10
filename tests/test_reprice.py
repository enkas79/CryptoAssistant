"""Test della rivalutazione dei prezzi storici delle transazioni."""

import pandas as pd
import pytest

from utils.reprice import rivaluta_transazioni


def _df(rows):
    return pd.DataFrame(
        rows,
        columns=["Date (UTC+1:00)", "Token", "Type", "Amount", "Price", "Fee", "Original Currency"],
    )


def _prezzi_finti(mapping):
    def fn(symbol, on_date):
        key = (str(symbol).upper(), pd.Timestamp(on_date).strftime("%Y-%m-%d"))
        return mapping.get(key)
    return fn


def test_mode_missing_valorizza_solo_le_righe_a_zero():
    df = _df([
        ["2025-01-10", "ETH", "buy", 1.0, 2000.0, 0.0, "EUR"],   # gia' valorizzata
        ["2025-06-01", "ETH", "buy", 0.5, 0.0, 0.0, "EUR"],      # da valorizzare
    ])
    df['Date (UTC+1:00)'] = pd.to_datetime(df['Date (UTC+1:00)'])

    out, report = rivaluta_transazioni(
        df, _prezzi_finti({("ETH", "2025-06-01"): 2500.0}), mode="missing"
    )

    assert out.loc[0, "Price"] == pytest.approx(2000.0)   # invariata
    assert out.loc[1, "Price"] == pytest.approx(2500.0)   # riprezzata
    assert report["aggiornate"] == 1
    assert report["non_trovate"] == []


def test_mode_all_riprezza_tutto():
    df = _df([
        ["2021-05-09", "BTC", "buy", 0.05, 58831.86, 0.0, "EUR"],
    ])
    df['Date (UTC+1:00)'] = pd.to_datetime(df['Date (UTC+1:00)'])

    out, report = rivaluta_transazioni(
        df, _prezzi_finti({("BTC", "2021-05-09"): 48000.0}), mode="all"
    )

    assert out.loc[0, "Price"] == pytest.approx(48000.0)
    assert report["aggiornate"] == 1


def test_prezzo_non_trovato_lascia_la_riga_invariata():
    df = _df([["2025-06-01", "GRAM", "buy", 3.0, 0.0, 0.0, "EUR"]])
    df['Date (UTC+1:00)'] = pd.to_datetime(df['Date (UTC+1:00)'])

    out, report = rivaluta_transazioni(df, _prezzi_finti({}), mode="missing")

    assert out.loc[0, "Price"] == pytest.approx(0.0)
    assert report["aggiornate"] == 0
    assert ("GRAM", "2025-06-01") in report["non_trovate"]


def test_non_tocca_i_trasferimenti_in_uscita_a_zero():
    """Una 'sell' a prezzo 0 e' un trasferimento: non va valorizzata."""
    df = _df([["2023-12-23", "BTC", "sell", 0.0016, 0.0, 0.0, "EUR"]])
    df['Date (UTC+1:00)'] = pd.to_datetime(df['Date (UTC+1:00)'])

    out, report = rivaluta_transazioni(
        df, _prezzi_finti({("BTC", "2023-12-23"): 40000.0}), mode="missing"
    )

    assert out.loc[0, "Price"] == pytest.approx(0.0)
    assert report["aggiornate"] == 0
