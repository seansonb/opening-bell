import yfinance as yf
from datetime import datetime, timedelta
import json
import time

def load_watchlist(filepath='data/watchlist.json'):
    """Load stock symbols from watchlist file"""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            return data.get('symbols', [])
    except FileNotFoundError:
        print(f"Watchlist not found at {filepath}")
        return []

def fetch_stock_data(symbol):
    """Fetch current price, change, and basic info for a stock"""
    try:
        # Add delay to avoid rate limiting
        time.sleep(2)
        
        # Let yfinance handle the session (it uses curl_cffi automatically)
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

def fetch_stock_news(symbol, days_back=1):
    """Fetch recent news for a stock"""
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        
        if not news:
            return []
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        recent_news = []
        
        for article in news:
            # Handle potential None values
            if not article:
                continue
                
            content = article.get('content')
            if not content:
                continue
            
            # pubDate is in ISO format like '2025-11-18T16:00:39Z'
            pub_date_str = content.get('pubDate', '')
            
            try:
                # Parse ISO format date
                pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                # Convert to local time (remove timezone info for comparison)
                pub_date = pub_date.replace(tzinfo=None)
            except:
                pub_date = datetime.min
            
            if pub_date >= cutoff_date:
                provider = content.get('provider') or {}
                click_through = content.get('clickThroughUrl') or {}
                
                recent_news.append({
                    'title': content.get('title', 'No title'),
                    'publisher': provider.get('displayName', 'Unknown'),
                    'link': click_through.get('url', ''),
                    'published': pub_date.strftime('%Y-%m-%d %H:%M'),
                    'summary': content.get('summary', '')
                })
        
        return recent_news
    except Exception as e:
        print(f"Error fetching news for {symbol}: {e}")
        return []

def fetch_all_data(watchlist):
    """Fetch data and news for all stocks in watchlist"""
    results = []
    
    for symbol in watchlist:
        print(f"Fetching data for {symbol}...")
        
        stock_data = fetch_stock_data(symbol)
        if stock_data:
            stock_data['news'] = fetch_stock_news(symbol)
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
            print(f"\nRecent News ({len(stock['news'])} articles):")
            for article in stock['news'][:3]:  # Show first 3
                print(f"  - {article['title']}")
                print(f"    {article['publisher']} | {article['published']}")