"""Test della costruzione del Quadro RW e dell'imposta cripto-attività (0,2%)."""

import pandas as pd
import pytest

from utils.tax_calculator import TaxCalculator


def _df(rows):
    return pd.DataFrame(
        rows,
        columns=["Date (UTC+1:00)", "Token", "Type", "Amount", "Price", "Fee", "Original Currency"],
    )


def test_asset_detenuto_tutto_l_anno():
    df = _df([
        ["2023-06-01", "BTC", "buy", 2.0, 30000.0, 0.0, "EUR"],
    ])
    calc = TaxCalculator(country_code="IT")

    righe = calc.build_quadro_rw(
        df, 2025,
        prices_start={"BTC": 40000.0},
        prices_end={"BTC": 50000.0},
    )

    assert len(righe) == 1
    r = righe[0]
    assert r.quantita_iniziale == pytest.approx(2.0)
    assert r.quantita_finale == pytest.approx(2.0)
    assert r.valore_iniziale == pytest.approx(80000.0)
    assert r.valore_finale == pytest.approx(100000.0)
    assert r.giorni_possesso == 365
    assert r.quota == pytest.approx(1.0)
    # IC = 0,2% del valore finale, pro-rata giorni (tutto l'anno)
    assert r.ivafe == pytest.approx(200.0)


def test_asset_acquistato_durante_l_anno():
    df = _df([
        ["2025-07-02", "ETH", "buy", 1.0, 2000.0, 0.0, "EUR"],
    ])
    calc = TaxCalculator(country_code="IT")

    righe = calc.build_quadro_rw(
        df, 2025, prices_start={"ETH": 0.0}, prices_end={"ETH": 2500.0},
    )

    r = righe[0]
    assert r.quantita_iniziale == pytest.approx(0.0)
    # valore iniziale = costo del primo acquisto nel periodo di detenzione
    assert r.valore_iniziale == pytest.approx(2000.0)
    assert r.valore_finale == pytest.approx(2500.0)
    # dal 2 luglio al 31 dicembre inclusi
    assert r.giorni_possesso == 183
    assert r.ivafe == pytest.approx(2500.0 * 0.002 * 183 / 365)


def test_asset_azzerato_prima_di_fine_anno_non_e_nel_rw_finale():
    df = _df([
        ["2024-01-10", "SOL", "buy", 10.0, 100.0, 0.0, "EUR"],
        ["2025-03-10", "SOL", "sell", 10.0, 150.0, 0.0, "EUR"],
    ])
    calc = TaxCalculator(country_code="IT")

    righe = calc.build_quadro_rw(
        df, 2025, prices_start={"SOL": 120.0}, prices_end={"SOL": 200.0},
    )

    r = next(x for x in righe if x.token == "SOL")
    assert r.quantita_finale == pytest.approx(0.0)
    assert r.quantita_iniziale == pytest.approx(10.0)
    # detenuto dall'1/1 al 10/3
    assert r.giorni_possesso == 69
