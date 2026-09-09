"""Test del provider a catena per le quotazioni storiche (CMC -> CoinGecko)."""

from api.historical_prices import ChainedHistoricalPrices


class _Provider:
    def __init__(self, start, end):
        self._start = start
        self._end = end
        self.chiamato = False

    def get_prices_for_year_bounds(self, symbols, year):
        self.chiamato = True
        return dict(self._start), dict(self._end)


def test_completa_i_buchi_col_provider_successivo():
    primo = _Provider({"BTC": 100.0}, {"BTC": 200.0})           # manca ETH
    secondo = _Provider({"ETH": 10.0}, {"ETH": 20.0, "BTC": 999.0})

    chained = ChainedHistoricalPrices([primo, secondo])
    start, end = chained.get_prices_for_year_bounds(["BTC", "ETH"], 2025)

    assert start == {"BTC": 100.0, "ETH": 10.0}
    # BTC gia' valorizzato dal primo: il secondo non lo sovrascrive
    assert end == {"BTC": 200.0, "ETH": 20.0}


def test_non_interroga_il_secondo_se_il_primo_copre_tutto():
    primo = _Provider({"BTC": 1.0}, {"BTC": 2.0})
    secondo = _Provider({}, {})

    chained = ChainedHistoricalPrices([primo, secondo])
    chained.get_prices_for_year_bounds(["BTC"], 2025)

    assert secondo.chiamato is False
