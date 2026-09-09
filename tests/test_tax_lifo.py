"""Test del metodo LIFO per il calcolo delle plusvalenze (Italia)."""

import pandas as pd
import pytest

from utils.tax_calculator import TaxCalculator


def _df(rows):
    return pd.DataFrame(
        rows,
        columns=["Date (UTC+1:00)", "Token", "Type", "Amount", "Price", "Fee", "Original Currency"],
    )


def test_italia_usa_lifo_non_fifo():
    """Con due lotti a prezzo diverso, la vendita chiude l'ULTIMO acquistato."""
    df = _df([
        ["2025-01-10", "BTC", "buy", 1.0, 100.0, 0.0, "EUR"],
        ["2025-02-10", "BTC", "buy", 1.0, 200.0, 0.0, "EUR"],
        ["2025-03-10", "BTC", "sell", 1.0, 300.0, 0.0, "EUR"],
    ])
    calc = TaxCalculator(country_code="IT")

    result = calc.calculate_taxes(df, 2025)

    # LIFO: 300 - 200 = 100 (FIFO darebbe 300 - 100 = 200)
    assert result.capital_gain == pytest.approx(100.0)


def test_le_commissioni_non_riducono_la_plusvalenza():
    """Art. 68 c.9-bis TUIR: le fee non sono deducibili."""
    df = _df([
        ["2025-01-10", "ETH", "buy", 1.0, 1000.0, 50.0, "EUR"],
        ["2025-06-10", "ETH", "sell", 1.0, 1500.0, 50.0, "EUR"],
    ])
    calc = TaxCalculator(country_code="IT")

    result = calc.calculate_taxes(df, 2025)

    assert result.capital_gain == pytest.approx(500.0)


def test_vendita_a_prezzo_zero_non_e_cessione():
    """Un trasferimento tra wallet (sell con Price 0) non genera minusvalenza."""
    df = _df([
        ["2024-01-10", "BTC", "buy", 1.0, 40000.0, 0.0, "EUR"],
        ["2025-05-10", "BTC", "sell", 0.1, 0.0, 0.0, "EUR"],
    ])
    calc = TaxCalculator(country_code="IT")

    result = calc.calculate_taxes(df, 2025)

    assert result.capital_gain == pytest.approx(0.0)
    assert result.taxable_transactions == []
