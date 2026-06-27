"""
CoinMarketCap API Module
Handles fetching live cryptocurrency prices from CoinMarketCap API.
"""

import requests


class CoinMarketCapAPI:
    """
    Client for CoinMarketCap API to fetch live cryptocurrency prices.
    """
    
    BASE_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    
    def __init__(self, api_key):
        """
        Initialize the client with an API key.
        
        Args:
            api_key (str): CoinMarketCap API key.
        """
        self.api_key = api_key
        self.headers = {'X-CMC_PRO_API_KEY': self.api_key}
    
    def get_live_prices(self, symbols, convert="USD"):
        """
        Fetch live prices for a list of cryptocurrency symbols.
        
        Args:
            symbols (list): List of cryptocurrency symbols (e.g., ["BTC", "ETH"]).
            convert (str): Currency to convert prices to (default: "USD").
        
        Returns:
            dict: Dictionary of {symbol: price} in the target currency.
        """
        prices = {}
        try:
            params = {'symbol': ",".join(symbols), 'convert': convert}
            response = requests.get(
                self.BASE_URL,
                headers=self.headers,
                params=params
            ).json()
            
            if 'data' in response:
                for symbol in symbols:
                    try:
                        prices[symbol] = response['data'][symbol]['quote'][convert]['price']
                    except KeyError:
                        prices[symbol] = 0
            else:
                print(f"Errore API CoinMarketCap: {response.get('status', {}).get('error_message', 'Unknown error')}")
        except Exception as e:
            print(f"Errore API CoinMarketCap: {e}")
        
        return prices
