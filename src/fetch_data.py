import yfinance as yf
from datetime import datetime, timedelta, timezone
import json
from fetch_news import fetch_stock_news
from fetch_earnings import fetch_earnings_data
from stock.cache import stock_cache
from stock.news_enricher import enrich_articles
from db.queries import get_recent_articles, save_articles

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
            'info': info,
            'history': hist,
        }
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

def _fetch_news_with_cache(symbol: str, company_name: str) -> list:
    """
    Return news articles for symbol, using DB cache when available.
    Cache window: 3 days on Monday (covers weekend), 1 day otherwise.
    """
    now = datetime.utcnow()
    days_back = 3 if now.weekday() == 0 else 1
    since = now - timedelta(days=days_back)

    cached = get_recent_articles(symbol, since)
    if cached:
        articles = [
            {
                'title': a.title,
                'publisher': a.publisher,
                'link': a.url,
                'published': a.published_at.strftime('%Y-%m-%d %H:%M') if a.published_at else '',
                'summary': a.summary or '',
            }
            for a in cached
        ]
        print(f"  [{symbol}] Using {len(articles)} cached articles from DB")
        return articles

    raw_news = fetch_stock_news(symbol)
    enriched = enrich_articles(raw_news, symbol, company_name)
    save_articles(enriched, symbol)
    print(f"  [{symbol}] Fetched {len(enriched)} new articles from yFinance")
    return enriched


def fetch_all_data(watchlist):
    """Fetch data, news, and earnings for all stocks in watchlist"""
    results = []
    
    for symbol in watchlist:
        print(f"Fetching data for {symbol}...")
        
        stock_data = fetch_stock_data(symbol)
        if stock_data:
            stock_data['news'] = _fetch_news_with_cache(symbol, stock_data['name'])
            stock_data['earnings'] = fetch_earnings_data(symbol)
            stock_cache.store(symbol, stock_data['info'], stock_data['news'], stock_data['history'])
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