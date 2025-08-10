# fmp_client.py
import httpx
from typing import List, Dict, Any, Optional

class FMPClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://financialmodelingprep.com/api/v3"

    async def _make_request(self, endpoint: str, params: Dict = None) -> Any:
        if params is None:
            params = {}
        params["apikey"] = self.api_key
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/{endpoint}", params=params, timeout=20.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                print(f"FMP API Error: {e.response.status_code} - {e.response.text}")
                return None
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                return None

    async def get_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Fetches batch quotes for multiple symbols."""
        if not symbols: return []
        symbols_str = ",".join(symbols)
        return await self._make_request(f"quote/{symbols_str}")

    async def get_historical_daily_price(self, symbol: str, date: str) -> Optional[Dict[str, Any]]:
        """Gets historical daily price data for a symbol on a specific date."""
        # The endpoint gets a range, so we query for the same start/end date
        data = await self._make_request(f"historical-price-full/{symbol.upper()}", {"from": date, "to": date})
        # Return the first result if the 'historical' key exists and is not empty
        return data['historical'][0] if data and data.get('historical') else None

    async def get_company_profile(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Gets company profile info."""
        profiles = await self._make_request(f"profile/{symbol.upper()}")
        return profiles[0] if profiles else None

    async def get_stock_news(self, symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Gets the latest news for a stock symbol."""
        news = await self._make_request("stock_news", {"tickers": symbol.upper(), "limit": limit})
        return news if news else []
        
    async def get_fund_holdings(self, symbol: str) -> List[Dict[str, Any]]:
        """Gets top holdings for a fund."""
        holdings = await self._make_request(f"etf-holder/{symbol.upper()}")
        return holdings if holdings else []
        
    async def convert_forex(self, from_currency: str, to_currency: str) -> Optional[Dict[str, Any]]:
        """Gets the conversion rate for a forex pair."""
        pair = f"{from_currency.upper()}{to_currency.upper()}"
        rates = await self._make_request(f"quote/{pair}")
        return rates[0] if rates else None
