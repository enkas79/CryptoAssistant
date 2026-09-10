"""Test del metodo PMC (media ponderata statica) per le plusvalenze."""

import pandas as pd
import pytest

from utils.tax_calculator import TaxCalculator


def _df(rows):
    return pd.DataFrame(
        rows,
        columns=["Date (UTC+1:00)", "Token", "Type", "Amount", "Price", "Fee", "Original Currency"],
    )


def test_pmc_usa_il_prezzo_medio_di_carico_statico():
    df = _df([
        ["2025-01-10", "BTC", "buy", 1.0, 100.0, 0.0, "EUR"],
        ["2025-02-10", "BTC", "buy", 1.0, 300.0, 0.0, "EUR"],   # PMC = 200
        ["2025-03-10", "BTC", "sell", 0.5, 400.0, 0.0, "EUR"],  # (400-200)*0.5 = 100
        ["2025-04-10", "BTC", "sell", 0.5, 500.0, 0.0, "EUR"],  # (500-200)*0.5 = 150
    ])
    calc = TaxCalculator(country_code="IT", cost_basis_method="PMC")

    result = calc.calculate_taxes(df, 2025)

    assert result.capital_gain == pytest.approx(250.0)   # LIFO darebbe 150


def test_pmc_selezionabile_via_setter_e_summary():
    df = _df([
        ["2025-01-10", "ETH", "buy", 2.0, 1000.0, 0.0, "EUR"],
        ["2025-06-10", "ETH", "sell", 1.0, 1500.0, 0.0, "EUR"],
    ])
    calc = TaxCalculator(country_code="IT")
    calc.set_cost_basis_method("PMC")

    summary = calc.get_tax_summary(df, 2025)

    assert summary["cost_basis_method"] == "PMC"
    assert summary["capital_gain"] == pytest.approx(500.0)


def test_default_italia_resta_lifo():
    calc = TaxCalculator(country_code="IT")
    assert calc.rule.cost_basis_method == "LIFO"
