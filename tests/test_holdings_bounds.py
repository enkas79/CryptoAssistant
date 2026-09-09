"""Test dell'elenco token da valorizzare per il Quadro RW."""

import pandas as pd
import pytest

from utils.tax_calculator import TaxCalculator


def _df(rows):
    return pd.DataFrame(
        rows,
        columns=["Date (UTC+1:00)", "Token", "Type", "Amount", "Price", "Fee", "Original Currency"],
    )


def test_elenca_token_detenuti_o_movimentati_nell_anno():
    df = _df([
        ["2023-01-01", "BTC", "buy", 1.0, 100.0, 0.0, "EUR"],   # detenuto tutto il 2025
        ["2025-06-01", "ETH", "buy", 2.0, 10.0, 0.0, "EUR"],    # acquistato nel 2025
        ["2022-01-01", "OLD", "buy", 1.0, 5.0, 0.0, "EUR"],
        ["2024-01-01", "OLD", "sell", 1.0, 9.0, 0.0, "EUR"],    # azzerato prima del 2025
    ])
    calc = TaxCalculator(country_code="IT")

    bounds = {t: (s, e) for t, s, e in calc.holdings_bounds(df, 2025)}

    assert bounds["BTC"] == pytest.approx((1.0, 1.0))
    assert bounds["ETH"] == pytest.approx((0.0, 2.0))
    assert "OLD" not in bounds
