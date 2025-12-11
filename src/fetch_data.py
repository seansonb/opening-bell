import yfinance as yf
from datetime import datetime, timedelta
import json
from fetch_news import fetch_stock_news
from fetch_earnings import fetch_earnings_data

def load_watchlist(filepath='data/watchlist.json'):
    """Load stock symbols from watchlist file"""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            return data.get('symbols', [])
    except FileNotFoundError:
        print(f"Watchlist not found at {filepath}")
        return []
    
def load_users(filepath='data/users.json'):
    """Load all users and their watchlists"""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            return data.get('users', [])
    except FileNotFoundError:
        print(f"Users file not found at {filepath}")
        return []

def fetch_stock_data(symbol):
    """Fetch current price, change, and basic info for a stock"""
    try:
        ticker = yf.Ticker(symbol)
        
        # Try using history for price data - most reliable
        hist = ticker.history(period="2d")
        if hist.empty:
            print(f"  No price data for {symbol}")
            return None
            
        current_price = hist['Close'].iloc[-1]
        previous_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        change_percent = ((current_price - previous_close) / previous_close) * 100
        
        # Get basic info
        try:
            info = ticker.info
            name = info.get('longName', info.get('shortName', symbol))
        except:
            name = symbol
        
        return {
            'symbol': symbol,
            'name': name,
            'current_price': current_price,
            'previous_close': previous_close,
            'change_percent': change_percent,
            'volume': hist['Volume'].iloc[-1] if 'Volume' in hist else None,
            'market_cap': None,
        }
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

def fetch_all_data(watchlist):
    """Fetch data, news, and earnings for all stocks in watchlist"""
    results = []
    
    for symbol in watchlist:
        print(f"Fetching data for {symbol}...")
        
        stock_data = fetch_stock_data(symbol)
        if stock_data:
            stock_data['news'] = fetch_stock_news(symbol)
            stock_data['earnings'] = fetch_earnings_data(symbol)
            results.append(stock_data)
    
    return results

if __name__ == "__main__":
    # Test the fetcher
    watchlist = load_watchlist()
    
    if not watchlist:
        print("No stocks in watchlist. Add some to data/watchlist.json")
        print("Example format: {\"symbols\": [\"AAPL\", \"GOOGL\", \"MSFT\"]}")
    else:
        data = fetch_all_data(watchlist)
        
        # Pretty print results
        for stock in data:
            print(f"\n{'='*50}")
            print(f"{stock['name']} ({stock['symbol']})")
            print(f"Price: ${stock['current_price']:.2f}")
            if stock['change_percent']:
                print(f"Change: {stock['change_percent']:.2f}%")
            print(f"\nRecent News ({len(stock['news'])} articles)")
            if stock['earnings']:
                print(f"Recent Earnings: {stock['earnings']['earnings_date']}")