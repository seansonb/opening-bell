import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.5-flash')

def summarize_stock_news(stock_data):
    """
    Generate a summary for a single stock's news
    
    Args:
        stock_data: Dict with keys: symbol, name, current_price, change_percent, news
    
    Returns:
        String summary of the stock's news and performance
    """
    symbol = stock_data['symbol']
    name = stock_data['name']
    price = stock_data['current_price']
    change = stock_data['change_percent']
    news = stock_data['news']
    
    # Build context for the LLM
    if news:
        news_text = ""
        for i, article in enumerate(news, 1):
            news_text += f"{i}. {article['title']} ({article['publisher']}, {article['published']})\n"
            if article['summary']:
                news_text += f"   {article['summary']}\n"
        
        prompt = f"""You are a financial analyst providing daily stock updates.

Stock: {name} ({symbol})
Current Price: ${price:.2f}
Change: {change:+.2f}%

Recent News:
{news_text}

Provide a 3-4 sentence summary. DO NOT include any preamble like "Here's your update" or "Let me summarize". Start directly with the key information. Focus on:
1. The most important news developments
2. How they relate to the price movement
3. What investors should watch for
4. What the sentiment is around the stock
5. How its movement relates to the broader market

Be concise, factual, and actionable. No fluff."""
    else:
        prompt = f"""You are a financial analyst providing daily stock updates.

Stock: {name} ({symbol})
Current Price: ${price:.2f}
Change: {change:+.2f}%

No news articles were published today for this stock.

Provide a 2-3 sentence summary analyzing the stock's performance. DO NOT include any preamble. Start directly with analysis. Cover:
1. The price movement and what it suggests
2. Whether this aligns with broader market trends
3. Any technical observations worth noting
4. What the sentiment is around the stock
5. How its movement relates to the broader market

Be concise and factual. Mention that no news was available."""

    try:
        response = model.generate_content(prompt)
        summary = response.text
        
        # Format the output
        output = f"**{name} ({symbol})**: ${price:.2f} ({change:+.2f}%)\n\n{summary}\n"
        return output
    
    except Exception as e:
        print(f"Error generating summary for {symbol}: {e}")
        return f"**{name} ({symbol})**: ${price:.2f} ({change:+.2f}%)\n\nError generating summary.\n"

def generate_digest(stocks_data):
    """
    Generate a complete daily digest for all stocks
    
    Args:
        stocks_data: List of stock data dicts
    
    Returns:
        Complete formatted digest string
    """
    from datetime import datetime
    
    digest = f"# Daily Stock Digest - {datetime.now().strftime('%B %d, %Y')}\n\n"
    digest += "=" * 60 + "\n\n"
    
    for stock_data in stocks_data:
        summary = summarize_stock_news(stock_data)
        digest += summary + "\n" + "-" * 60 + "\n\n"
    
    return digest

if __name__ == "__main__":
    # Test with sample data
    from fetch_data import load_watchlist, fetch_all_data
    
    print("Fetching stock data...")
    watchlist = load_watchlist()
    stocks_data = fetch_all_data(watchlist[:2])  # Test with first 2 stocks
    
    print("\nGenerating summaries...\n")
    digest = generate_digest(stocks_data)
    print(digest)