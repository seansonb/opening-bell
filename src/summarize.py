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
    
    if not news:
        return f"**{name} ({symbol})**: ${price:.2f} ({change:+.2f}%)\n\nNo recent news available.\n"
    
    # Build context for the LLM
    news_text = ""
    for i, article in enumerate(news, 1):
        news_text += f"{i}. {article['title']} ({article['publisher']}, {article['published']})\n"
        if article['summary']:
            news_text += f"   {article['summary']}\n"
    
    prompt = f"""You are a financial analyst providing daily stock updates. Summarize the following information concisely and actionably.

Stock: {name} ({symbol})
Current Price: ${price:.2f}
Change: {change:+.2f}%

Recent News:
{news_text}

Provide a brief paragraph summary highlighting:
1. Key developments or themes in the news
2. Any notable price movement context
3. What investors should know
4. What the general sentiment shift has been around the stock

Keep it concise, factual, and avoid speculation. Write in a professional but conversational tone."""

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