"""Test del client CoinGecko per le quotazioni storiche in EUR."""

from datetime import date

import pytest

from api.coingecko import CoinGeckoAPI


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


def test_restituisce_il_prezzo_eur_alla_data(monkeypatch):
    chiamate = []

    def fake_get(url, params=None, timeout=None, headers=None):
        chiamate.append((url, params))
        return _FakeResp({"market_data": {"current_price": {"eur": 41234.56}}})

    monkeypatch.setattr("api.coingecko.requests.get", fake_get)
    api = CoinGeckoAPI(cache_path=None)

    prezzo = api.get_historical_price("BTC", date(2024, 12, 31))

    assert prezzo == pytest.approx(41234.56)
    assert "bitcoin/history" in chiamate[0][0]
    assert chiamate[0][1]["date"] == "31-12-2024"


def test_usa_la_cache_e_non_richiama_la_rete(monkeypatch, tmp_path):
    n = {"c": 0}

    def fake_get(url, params=None, timeout=None, headers=None):
        n["c"] += 1
        return _FakeResp({"market_data": {"current_price": {"eur": 100.0}}})

    monkeypatch.setattr("api.coingecko.requests.get", fake_get)
    cache = tmp_path / "cg.json"

    api1 = CoinGeckoAPI(cache_path=str(cache))
    api1.get_historical_price("ETH", date(2025, 1, 1))
    api2 = CoinGeckoAPI(cache_path=str(cache))
    api2.get_historical_price("ETH", date(2025, 1, 1))

    assert n["c"] == 1


def test_token_sconosciuto_restituisce_none(monkeypatch):
    monkeypatch.setattr(
        "api.coingecko.requests.get",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("non deve chiamare la rete")),
    )
    api = CoinGeckoAPI(cache_path=None)

    assert api.get_historical_price("TOKENFANTASMA", date(2025, 1, 1)) is None
