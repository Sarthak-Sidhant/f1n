# models.py
from pydantic import BaseModel, Field
from typing import List, Optional

class StockHolding(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float = Field(..., description="The average price paid per share")
    purchase_date: Optional[str] = Field(None, description="The date of purchase in YYYY-MM-DD format")

class MutualFundHolding(BaseModel):
    ticker: str
    units: float
    avg_nav: float = Field(..., description="The average Net Asset Value paid per unit")
    purchase_date: Optional[str] = Field(None, description="The date of purchase in YYYY-MM-DD format")

class CryptoHolding(BaseModel):
    ticker: str # e.g., BTC, ETH
    quantity: float
    avg_cost: float = Field(..., description="The average price paid per coin")
    purchase_date: Optional[str] = Field(None, description="The date of purchase in YYYY-MM-DD format")

class Portfolio(BaseModel):
    stocks: List[StockHolding] = []
    mutual_funds: List[MutualFundHolding] = []
    crypto: List[CryptoHolding] = []
