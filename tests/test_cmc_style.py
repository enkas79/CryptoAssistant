"""Test del calcolo P/L in stile CoinMarketCap (media ponderata, all-time)."""

import pandas as pd
import pytest

from utils.calculations import calculate_cmc_style_stats


def _df(rows):
    return pd.DataFrame(
        rows,
        columns=["Date (UTC+1:00)", "Token", "Type", "Amount", "Price", "Fee", "Original Currency"],
    )


def test_costo_base_non_ridotto_dalle_vendite_e_pl_all_time():
    df = _df([
        ["2025-01-01", "X", "buy", 1.0, 100.0, 0.0, "EUR"],
        ["2025-02-01", "X", "buy", 1.0, 200.0, 0.0, "EUR"],
        ["2025-03-01", "X", "sell", 1.0, 300.0, 0.0, "EUR"],
    ])
    s = calculate_cmc_style_stats(df, live_price=250.0, exchange_rate=1.0)

    assert s["cost_basis"] == pytest.approx(300.0)      # non 150
    assert s["avg_buy_price"] == pytest.approx(150.0)
    assert s["realized_pl"] == pytest.approx(150.0)     # 300 - 150*1
    assert s["quantity"] == pytest.approx(1.0)
    assert s["unrealized_pl"] == pytest.approx(100.0)   # (250-150)*1
    assert s["total_pl"] == pytest.approx(250.0)
    assert s["total_pl_pct"] == pytest.approx(250.0 / 300.0 * 100)


def test_posizione_chiusa_conserva_il_realizzato():
    df = _df([
        ["2024-01-01", "LINK", "buy", 10.0, 10.0, 0.0, "EUR"],
        ["2024-06-01", "LINK", "sell", 10.0, 15.0, 0.0, "EUR"],
    ])
    s = calculate_cmc_style_stats(df, live_price=20.0, exchange_rate=1.0)

    assert s["quantity"] == pytest.approx(0.0)
    assert s["realized_pl"] == pytest.approx(50.0)
    assert s["total_pl"] == pytest.approx(50.0)


def test_trasferimento_in_uscita_non_crea_perdita_fittizia():
    df = _df([
        ["2025-01-01", "BTC", "buy", 1.0, 100.0, 0.0, "EUR"],
        ["2025-05-01", "BTC", "sell", 0.1, 0.0, 0.0, "EUR"],  # move to another wallet
    ])
    s = calculate_cmc_style_stats(df, live_price=100.0, exchange_rate=1.0)

    assert s["realized_pl"] == pytest.approx(0.0)
    assert s["quantity"] == pytest.approx(0.9)
    assert s["total_pl"] == pytest.approx(0.0)


def test_caso_di_validazione_ufficiale_cmc():
    """Test case dalla specifica CMC.md (docs/calcolo_pl_coinmarketcap.md, §4)."""
    # Nella specifica gli importi sono passati alle formule come Q*P (totale
    # di riga): Buy 2 vale 6.000 in totale su 0,5 BTC -> prezzo unitario 12.000;
    # Sell 1 incassa 12.000 su 0,75 BTC -> prezzo unitario 16.000.
    df = _df([
        ["2024-01-01", "BTC", "buy", 1.0, 10000.0, 50.0, "EUR"],
        ["2024-02-01", "BTC", "buy", 0.5, 12000.0, 30.0, "EUR"],
        ["2024-03-01", "BTC", "sell", 0.75, 16000.0, 60.0, "EUR"],
    ])
    s = calculate_cmc_style_stats(df, live_price=18000.0, exchange_rate=1.0)

    assert s["cost_basis"] == pytest.approx(16080.0)
    assert s["avg_buy_price"] == pytest.approx(10720.0)
    assert s["realized_pl"] == pytest.approx(3900.0)
    assert s["unrealized_pl"] == pytest.approx(5460.0)
    assert s["total_pl"] == pytest.approx(9360.0)
    assert s["total_pl_pct"] == pytest.approx(58.2089, abs=1e-3)


def test_prezzo_live_convertito_da_usd_a_eur():
    df = _df([["2025-01-01", "ETH", "buy", 2.0, 1000.0, 0.0, "EUR"]])
    # live_price in USD, cambio 0.9 -> prezzo EUR 900, sotto il costo medio 1000
    s = calculate_cmc_style_stats(df, live_price=1000.0, exchange_rate=0.9)

    assert s["unrealized_pl"] == pytest.approx((900.0 - 1000.0) * 2.0)
