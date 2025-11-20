import yfinance as yf
from datetime import datetime, timedelta

def fetch_stock_news(symbol, days_back=7):
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