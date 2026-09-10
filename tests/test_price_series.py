"""Test del recupero di una serie storica di prezzi (una chiamata per token)."""

from datetime import date

import pytest

from api.coingecko import CoinGeckoAPI
from api.historical_prices import ChainedHistoricalPrices


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_coingecko_series_mappa_data_prezzo(monkeypatch):
    # due punti giornalieri (timestamp ms)
    payload = {"prices": [
        [1704067200000, 100.0],   # 2024-01-01
        [1704153600000, 110.0],   # 2024-01-02
    ]}

    def fake_get(url, params=None, timeout=None, headers=None):
        assert "market_chart/range" in url
        return _FakeResp(payload)

    monkeypatch.setattr("api.coingecko.requests.get", fake_get)
    api = CoinGeckoAPI(cache_path=None)

    serie = api.get_price_series("BTC", date(2024, 1, 1), date(2024, 1, 2))

    assert serie["2024-01-01"] == pytest.approx(100.0)
    assert serie["2024-01-02"] == pytest.approx(110.0)


def test_chained_series_completa_i_buchi():
    class P1:
        def get_price_series(self, s, a, b):
            return {"2024-01-01": 1.0}

    class P2:
        def get_price_series(self, s, a, b):
            return {"2024-01-01": 999.0, "2024-01-02": 2.0}

    chained = ChainedHistoricalPrices([P1(), P2()])
    serie = chained.get_price_series("BTC", date(2024, 1, 1), date(2024, 1, 2))

    assert serie == {"2024-01-01": 1.0, "2024-01-02": 2.0}
