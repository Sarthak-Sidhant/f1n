# main.py
import os
import yaml
import asyncio
from dotenv import load_dotenv
from typing import Annotated, List, Optional
from pydantic import Field

from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from mcp.server.auth.provider import AccessToken

import portfolio_manager as pm
from fmp_client import FMPClient
from models import StockHolding, CryptoHolding, MutualFundHolding

# --- Boilerplate and Setup ---
load_dotenv()
TOKEN, MY_NUMBER, FMP_API_KEY = os.getenv("AUTH_TOKEN"), os.getenv("MY_NUMBER"), os.getenv("FMP_API_KEY")
assert all([TOKEN, MY_NUMBER, FMP_API_KEY]), "Ensure AUTH_TOKEN, MY_NUMBER, and FMP_API_KEY are in .env"

class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token
    async def load_access_token(self, token: str) -> AccessToken | None:
        return AccessToken(token=token, client_id="puch-client", scopes=["*"]) if token == self.token else None

mcp = FastMCP("Puch Finance Hub v2.1 (Validated)", auth=SimpleBearerAuthProvider(TOKEN))
fmp = FMPClient(api_key=FMP_API_KEY)

# ==============================================================================
# --- CORE & UTILITY TOOLS ---
# ==============================================================================

@mcp.tool(description="A mandatory tool for Puch AI to verify the server owner upon connection.")
async def validate() -> str:
    """
    Returns the server owner's phone number. Required by Puch for handshake.
    """
    return MY_NUMBER

@mcp.tool(description="A utility to get the closing price of an asset on a specific historical date.")
async def get_price_on_date(ticker: str, date: Annotated[str, Field(description="Date in YYYY-MM-DD format")]) -> str:
    price_data = await fmp.get_historical_daily_price(ticker, date)
    if not price_data or 'close' not in price_data:
        return f"ERROR: Could not fetch price for {ticker} on {date}."
    return f"The closing price for {ticker} on {date} was {price_data['close']:.2f}."

@mcp.tool(description="Converts an amount from one currency to another using live exchange rates.")
async def convert_currency(from_currency: str, to_currency: str, amount: float = 1.0) -> str:
    rate_data = await fmp.convert_forex(from_currency, to_currency)
    if not rate_data or 'price' not in rate_data:
        return f"ERROR: Could not get conversion rate for {from_currency}/{to_currency}."
    converted_amount = amount * rate_data['price']
    return f"{amount} {from_currency.upper()} is equal to {converted_amount:,.2f} {to_currency.upper()}."

# ==============================================================================
# --- PORTFOLIO MANAGEMENT TOOLS ---
# ==============================================================================

@mcp.tool(description="Adds a stock holding to the portfolio. Updates the entry if it already exists.")
async def add_stock(puch_user_id: str, ticker: str, quantity: float, avg_cost: float, purchase_date: Optional[str] = None) -> str:
    stock = StockHolding(ticker=ticker, quantity=quantity, avg_cost=avg_cost, purchase_date=purchase_date)
    pm.add_asset_to_portfolio(puch_user_id, 'stock', stock.model_dump())
    return f"OK. I've added/updated {quantity} shares of {ticker.upper()} in your portfolio."

@mcp.tool(description="Adds a cryptocurrency holding to the portfolio.")
async def add_crypto(puch_user_id: str, ticker: str, quantity: float, avg_cost: float, purchase_date: Optional[str] = None) -> str:
    crypto = CryptoHolding(ticker=ticker, quantity=quantity, avg_cost=avg_cost, purchase_date=purchase_date)
    pm.add_asset_to_portfolio(puch_user_id, 'crypto', crypto.model_dump())
    return f"OK. I've added/updated {quantity} of {ticker.upper()} in your portfolio."

@mcp.tool(description="Removes any asset (stock, crypto, or mutual fund) from the user's portfolio.")
async def remove_asset(puch_user_id: str, ticker: str) -> str:
    ticker = ticker.upper()
    if pm.remove_asset_from_portfolio(puch_user_id, 'stock', ticker):
        return f"Done. I've removed stock {ticker} from your portfolio."
    if pm.remove_asset_from_portfolio(puch_user_id, 'crypto', ticker):
        return f"Done. I've removed crypto {ticker} from your portfolio."
    if pm.remove_asset_from_portfolio(puch_user_id, 'mutual_fund', ticker):
        return f"Done. I've removed fund {ticker} from your portfolio."
    return f"I couldn't find {ticker} in your portfolio to remove."

# ==============================================================================
# --- DATA RETRIEVAL & ANALYSIS TOOLS ---
# ==============================================================================

@mcp.tool(description="THE MOST IMPORTANT TOOL. Retrieves the user's complete portfolio, gets live market prices for all assets, and provides a full summary of their holdings, values, and performance. Use this for any general query about the portfolio's status.")
async def get_portfolio_summary(puch_user_id: str) -> str:
    portfolio = pm.get_user_portfolio(puch_user_id)
    all_tickers = [s.ticker for s in portfolio.stocks] + \
                  [m.ticker for m in portfolio.mutual_funds] + \
                  [f"{c.ticker}USD" for c in portfolio.crypto]
    
    if not all_tickers:
        return "Your portfolio is currently empty. You can add assets using tools like `add_stock` or `add_crypto`."
        
    live_quotes = await fmp.get_quotes(all_tickers)
    if not live_quotes:
        return "Sorry, I couldn't fetch live market prices right now. Please try again."

    price_map = {q['symbol']: q['price'] for q in live_quotes}
    summary_data = {}
    total_value, total_investment = 0.0, 0.0

    asset_types = [('stocks', portfolio.stocks, 'avg_cost'), ('crypto', portfolio.crypto, 'avg_cost')]
    for key, assets, cost_field in asset_types:
        details = []
        for asset in assets:
            symbol = f"{asset.ticker.upper()}USD" if key == 'crypto' else asset.ticker.upper()
            current_price = price_map.get(symbol)
            if current_price:
                cost_basis, quantity = getattr(asset, cost_field), asset.quantity
                current_value, investment_value = quantity * current_price, quantity * cost_basis
                gain_loss = current_value - investment_value
                total_value += current_value; total_investment += investment_value
                details.append({"ticker": asset.ticker, "quantity": f"{quantity:,.4f}", "current_price": f"${current_price:,.2f}", "current_value": f"${current_value:,.2f}", "total_gain_loss": f"${gain_loss:,.2f}"})
        if details: summary_data[key] = details

    total_gain_loss = total_value - total_investment
    summary_data["portfolio_overview"] = {"total_estimated_value": f"${total_value:,.2f}", "total_investment": f"${total_investment:,.2f}", "total_portfolio_gain_loss": f"${total_gain_loss:,.2f}"}

    yaml_output = yaml.dump(summary_data, sort_keys=False, indent=2)
    instructions = ("\n\n--- INSTRUCTIONS FOR AI ---\n"
                    "The above YAML contains a full summary of the user's portfolio.\n"
                    "1. Present this as a friendly, clear, and comprehensive report.\n"
                    "2. ALWAYS start with the 'portfolio_overview' section.\n"
                    "3. For each asset class (stocks, crypto), present the details in a table or clean list.\n"
                    "4. Act as a professional and insightful financial assistant.")
    
    return yaml_output + instructions

@mcp.tool(description="Gets detailed information (like Market Cap, P/E Ratio, Description) for a stock or fund.")
async def get_asset_details(ticker: str) -> str:
    profile = await fmp.get_company_profile(ticker)
    if not profile: return f"I couldn't find any details for {ticker}."
    details = {"company_name": profile.get('companyName'), "ticker": profile.get('symbol'), "current_price": f"${profile.get('price'):,.2f}", "market_cap": f"${profile.get('mktCap'):,}", "pe_ratio": profile.get('pe'), "description": profile.get('description'), "industry": profile.get('industry'), "website": profile.get('website')}
    return yaml.dump({"asset_details": details}, sort_keys=False) + "\n\nPresent these details to the user."

@mcp.tool(description="Gets the latest news headlines for a specific stock ticker.")
async def get_latest_news(ticker: str) -> str:
    news_items = await fmp.get_stock_news(ticker, limit=5)
    if not news_items: return f"No recent news found for {ticker.upper()}."
    output = f"📰 Latest News for {ticker.upper()}:\n" + "\n".join([f"- **{item['title']}** (Source: {item['site']})" for item in news_items])
    return output

@mcp.tool(description="Lists the top holdings for a given Mutual Fund or ETF ticker.")
async def get_fund_holdings(ticker: str) -> str:
    holdings = await fmp.get_fund_holdings(ticker)
    if not holdings: return f"Could not retrieve holdings for {ticker}. It might not be a fund or ETF."
    holding_list = [{"asset": h.get('asset'), "weight": f"{h.get('weightPercentage'):.2f}%"} for h in holdings[:10]]
    return yaml.dump({"top_10_holdings": holding_list}, sort_keys=False) + f"\n\nDisplay these top 10 holdings for {ticker.upper()}."

# --- Main Driver ---
async def main():
    print("🚀 Starting Puch Finance Hub v2.1 (Validated) MCP server on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    asyncio.run(main())
