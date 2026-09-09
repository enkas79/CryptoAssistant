"""Smoke test della generazione del PDF fiscale con Quadro RW."""

import pandas as pd

from utils.pdf_generator import FiscalReportGenerator
from utils.tax_calculator import TaxCalculator


def test_genera_pdf_con_quadro_rw(tmp_path):
    df = pd.DataFrame(
        [
            ["2023-01-10", "BTC", "buy", 1.0, 20000.0, 0.0, "EUR"],
            ["2025-04-10", "BTC", "sell", 0.5, 60000.0, 0.0, "EUR"],
            ["2025-02-01", "ETH", "buy", 0.0, 0.0, 0.0, "EUR"],  # riga da verificare
        ],
        columns=["Date (UTC+1:00)", "Token", "Type", "Amount", "Price", "Fee", "Original Currency"],
    )
    calc = TaxCalculator(country_code="IT")
    summary = calc.get_tax_summary(
        df, 2025, prices_start={"BTC": 40000.0}, prices_end={"BTC": 50000.0}
    )

    out = tmp_path / "report.pdf"
    ok = FiscalReportGenerator({"BTC": 50000.0}, 1.0, "EUR").generate_tax_report(summary, str(out))

    assert ok is True
    assert out.exists() and out.stat().st_size > 0
    assert summary["cost_basis_method"] == "LIFO"
    assert any(z["token"] == "ETH" for z in summary["zero_price_rows"])
