"""Test dell'esposizione del metodo e del Quadro RW nel riepilogo fiscale."""

import pandas as pd
import pytest

from utils.tax_calculator import TaxCalculator


def _df(rows):
    return pd.DataFrame(
        rows,
        columns=["Date (UTC+1:00)", "Token", "Type", "Amount", "Price", "Fee", "Original Currency"],
    )


def test_summary_espone_il_metodo_lifo_per_italia():
    df = _df([["2025-01-10", "BTC", "buy", 1.0, 100.0, 0.0, "EUR"]])
    calc = TaxCalculator(country_code="IT")

    summary = calc.get_tax_summary(df, 2025)

    assert summary["cost_basis_method"] == "LIFO"


def test_summary_include_quadro_rw_quando_forniti_i_prezzi():
    df = _df([["2023-01-10", "BTC", "buy", 1.0, 100.0, 0.0, "EUR"]])
    calc = TaxCalculator(country_code="IT")

    summary = calc.get_tax_summary(
        df, 2025,
        prices_start={"BTC": 200.0},
        prices_end={"BTC": 300.0},
    )

    assert len(summary["quadro_rw"]) == 1
    assert summary["quadro_rw"][0]["token"] == "BTC"
    assert summary["quadro_rw"][0]["valore_finale"] == pytest.approx(300.0)
    assert summary["imposta_cripto_totale"] == pytest.approx(0.6)
