"""Test del recupero quotazioni storiche EUR da CoinMarketCap."""

from datetime import date

import pytest

from api.coinmarketcap import CoinMarketCapAPI


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


_PAYLOAD = {
    "data": {
        "BTC": [
            {
                "symbol": "BTC",
                "quotes": [
                    {"timestamp": "2024-12-31T00:00:00Z",
                     "quote": {"EUR": {"price": 88888.5, "timestamp": "2024-12-31T00:00:00Z"}}}
                ],
            }
        ]
    }
}


def test_restituisce_il_prezzo_eur_storico(monkeypatch):
    catturate = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        catturate["url"] = url
        catturate["params"] = params
        return _FakeResp(_PAYLOAD)

    monkeypatch.setattr("api.coinmarketcap.requests.get", fake_get)
    api = CoinMarketCapAPI("KEY", cache_path=None)

    prezzo = api.get_historical_price("BTC", date(2024, 12, 31))

    assert prezzo == pytest.approx(88888.5)
    assert "historical" in catturate["url"]
    assert catturate["params"]["convert"] == "EUR"
    assert catturate["params"]["symbol"] == "BTC"


def test_usa_la_cache(monkeypatch, tmp_path):
    n = {"c": 0}

    def fake_get(url, params=None, headers=None, timeout=None):
        n["c"] += 1
        return _FakeResp(_PAYLOAD)

    monkeypatch.setattr("api.coinmarketcap.requests.get", fake_get)
    cache = tmp_path / "cmc.json"

    CoinMarketCapAPI("KEY", cache_path=str(cache)).get_historical_price("BTC", date(2024, 12, 31))
    CoinMarketCapAPI("KEY", cache_path=str(cache)).get_historical_price("BTC", date(2024, 12, 31))

    assert n["c"] == 1


def test_errore_di_piano_restituisce_none(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResp({"status": {"error_code": 1006, "error_message": "plan not authorized"}})

    monkeypatch.setattr("api.coinmarketcap.requests.get", fake_get)
    api = CoinMarketCapAPI("KEY", cache_path=None)

    assert api.get_historical_price("BTC", date(2024, 12, 31)) is None
