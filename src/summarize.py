import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.5-flash')

def format_earnings_data(earnings):
    """Format earnings data for LLM prompt"""
    if not earnings:
        return None
    
    def fmt_num(val, prefix='$', suffix='', is_pct=False):
        if val is None:
            return 'N/A'
        if is_pct:
            return f"{val*100:.2f}%"
        if prefix == '$' and val > 1e9:
            return f"${val/1e9:.2f}B"
        if prefix == '$' and val > 1e6:
            return f"${val/1e6:.2f}M"
        return f"{prefix}{val:.2f}{suffix}"
    
    sections = []
    
    # Core Financials
    core = f"""CORE FINANCIALS:
- Revenue: {fmt_num(earnings.get('revenue'))} (YoY Growth: {fmt_num(earnings.get('revenue_yoy_growth'), '', '', True)})
- Net Income: {fmt_num(earnings.get('net_income'))}
- EPS: {fmt_num(earnings.get('eps'), '$')} (Forward: {fmt_num(earnings.get('forward_eps'), '$')})
- Earnings Growth: {fmt_num(earnings.get('earnings_growth'), '', '', True)}
- Gross Margin: {fmt_num(earnings.get('gross_margin'), '', '', True)}
- Operating Margin: {fmt_num(earnings.get('operating_margin'), '', '', True)}
- Net Margin: {fmt_num(earnings.get('profit_margin'), '', '', True)}
- EBITDA Margin: {fmt_num(earnings.get('ebitda_margin'), '', '', True)}
- Free Cash Flow: {fmt_num(earnings.get('free_cash_flow'))}
- Operating Cash Flow: {fmt_num(earnings.get('operating_cash_flow'))}"""
    sections.append(core)
    
    # Balance Sheet
    balance = f"""BALANCE SHEET:
- Total Cash: {fmt_num(earnings.get('total_cash'))}
- Total Debt: {fmt_num(earnings.get('total_debt'))}
- Current Ratio: {fmt_num(earnings.get('current_ratio'), '')}
- Quick Ratio: {fmt_num(earnings.get('quick_ratio'), '')}"""
    sections.append(balance)
    
    # Valuation
    valuation = f"""VALUATION:
- Market Cap: {fmt_num(earnings.get('market_cap'))}
- P/E Ratio: {fmt_num(earnings.get('pe_ratio'), '')} (Forward: {fmt_num(earnings.get('forward_pe'), '')})
- P/S Ratio: {fmt_num(earnings.get('ps_ratio'), '')}
- Price-to-Book: {fmt_num(earnings.get('price_to_book'), '')}
- EV/Revenue: {fmt_num(earnings.get('ev_to_revenue'), '')}
- EV/EBITDA: {fmt_num(earnings.get('ev_to_ebitda'), '')}
- Revenue per Share: {fmt_num(earnings.get('revenue_per_share'), '$')}"""
    sections.append(valuation)
    
    # Earnings Performance
    if earnings.get('reported_eps') or earnings.get('estimated_eps'):
        performance = f"""EARNINGS PERFORMANCE:
- Reported EPS: {fmt_num(earnings.get('reported_eps'), '$')}
- Expected EPS: {fmt_num(earnings.get('estimated_eps'), '$')}
- Surprise: {fmt_num(earnings.get('surprise'), '', '%', False)}"""
        sections.append(performance)
    
    # Analyst Guidance
    if earnings.get('target_mean_price'):
        guidance = f"""ANALYST GUIDANCE:
- Target Price Range: {fmt_num(earnings.get('target_low_price'), '$')} - {fmt_num(earnings.get('target_high_price'), '$')}
- Mean Target: {fmt_num(earnings.get('target_mean_price'), '$')}
- Recommendation: {earnings.get('recommendation', 'N/A').upper()}"""
        sections.append(guidance)
    
    return "\n\n".join(sections)

def summarize_stock_news(stock_data):
    """
    Generate a summary for a single stock's news and earnings
    
    Args:
        stock_data: Dict with keys: symbol, name, current_price, change_percent, news, earnings
    
    Returns:
        String summary of the stock's news, earnings, and performance
    """
    symbol = stock_data['symbol']
    name = stock_data['name']
    price = stock_data['current_price']
    change = stock_data['change_percent']
    news = stock_data['news']
    earnings = stock_data.get('earnings')
    
    # Check if there's earnings data
    has_earnings = earnings is not None
    earnings_text = format_earnings_data(earnings) if has_earnings else ""
    
    # Build context for the LLM
    if news or has_earnings:
        prompt_parts = [f"""You are a financial analyst providing daily stock updates.

Stock: {name} ({symbol})
Current Price: ${price:.2f}
Change: {change:+.2f}%"""]
        
        if has_earnings:
            prompt_parts.append(f"""
EARNINGS REPORT (Recent):
Earnings Date: {earnings.get('earnings_date')}

{earnings_text}""")
        
        if news:
            news_text = ""
            for i, article in enumerate(news, 1):
                news_text += f"{i}. {article['title']} ({article['publisher']}, {article['published']})\n"
                if article['summary']:
                    news_text += f"   {article['summary']}\n"
            prompt_parts.append(f"""
Recent News:
{news_text}""")
        
        prompt_parts.append("""
Provide a 3-4 sentence summary. DO NOT include any preamble like "Here's your update" or "Let me summarize". Start directly with the key information.""")
        
        if has_earnings:
            prompt_parts.append("""
Focus on:
1. Key earnings metrics and whether they beat/missed expectations
2. Most important financial trends (margins, growth, cash position)
3. How the market reacted and why
4. Critical news developments if any

Be analytical and data-driven. Highlight the most important numbers.""")
        else:
            prompt_parts.append("""
Focus on:
1. The most important news developments
2. How they relate to the price movement
3. What investors should watch for

Be concise, factual, and actionable. No fluff.""")
        
        prompt = "\n".join(prompt_parts)
        
    else:
        prompt = f"""You are a financial analyst providing daily stock updates.

Stock: {name} ({symbol})
Current Price: ${price:.2f}
Change: {change:+.2f}%

No news articles or earnings reports were published recently for this stock.

Provide a 3-4 sentence summary analyzing the stock's performance. DO NOT include any preamble. Start directly with analysis. Cover:
1. The price movement and what it suggests
2. Whether this aligns with broader market trends
3. Any technical observations worth noting

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