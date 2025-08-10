# portfolio_manager.py
import json
from typing import Dict, Any, Literal
from pathlib import Path
from models import Portfolio

DATA_FILE = Path("user_data.json")
USER_DATA: Dict[str, Dict[str, Any]] = {}

def load_data():
    """Loads user data from the JSON file into memory at startup."""
    global USER_DATA
    if DATA_FILE.exists():
        with open(DATA_FILE, "r") as f:
            try:
                USER_DATA = json.load(f)
            except json.JSONDecodeError:
                USER_DATA = {} # Start fresh if the file is corrupted
    else:
        USER_DATA = {}

def save_data():
    """Saves the current state of USER_DATA to the JSON file on any change."""
    with open(DATA_FILE, "w") as f:
        json.dump(USER_DATA, f, indent=4)

def get_user_portfolio(puch_user_id: str) -> Portfolio:
    """Retrieves a user's portfolio, creating one if it doesn't exist."""
    user_data = USER_DATA.setdefault(puch_user_id, {"stocks": [], "mutual_funds": [], "crypto": []})
    return Portfolio.model_validate(user_data)

def add_asset_to_portfolio(puch_user_id: str, asset_type: Literal['stock', 'mutual_fund', 'crypto'], asset_data: dict):
    """Adds or updates an asset in a user's portfolio."""
    portfolio = get_user_portfolio(puch_user_id).model_dump()
    asset_list_key = f"{asset_type}s"
    ticker = asset_data['ticker'].upper()
    
    found = False
    for i, asset in enumerate(portfolio[asset_list_key]):
        if asset['ticker'] == ticker:
            # Update the existing asset
            portfolio[asset_list_key][i] = asset_data
            found = True
            break
            
    if not found:
        portfolio[asset_list_key].append(asset_data)

    USER_DATA[puch_user_id] = portfolio
    save_data() # Save after every modification
    print(f"Portfolio saved for user {puch_user_id} after adding/updating {ticker}")

def remove_asset_from_portfolio(puch_user_id: str, asset_type: Literal['stock', 'mutual_fund', 'crypto'], ticker: str) -> bool:
    """Removes an asset from a user's portfolio by ticker."""
    portfolio = get_user_portfolio(puch_user_id).model_dump()
    asset_list_key = f"{asset_type}s"
    
    initial_count = len(portfolio[asset_list_key])
    portfolio[asset_list_key] = [asset for asset in portfolio[asset_list_key] if asset['ticker'].upper() != ticker.upper()]
    
    if len(portfolio[asset_list_key]) < initial_count:
        USER_DATA[puch_user_id] = portfolio
        save_data() # Save after every modification
        print(f"Portfolio saved for user {puch_user_id} after removing {ticker}")
        return True
    return False

# Load data when the application starts
load_data()
