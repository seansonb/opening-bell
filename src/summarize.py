import os
from dotenv import load_dotenv
import google.generativeai as genai
from rate_limiter import RateLimiter

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-flash-latest')

# Global rate limiter instance
rate_limiter = RateLimiter()

# Cache for market summary (so we only generate once per run)
_market_summary_cache = None

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
        # Wait if we're hitting rate limits
        rate_limiter.wait_if_needed()
        
        response = model.generate_content(prompt)
        summary = response.text
        
        # Format the output
        output = f"**{name} ({symbol})**: ${price:.2f} ({change:+.2f}%)\n\n{summary}\n"
        return output
    
    except Exception as e:
        print(f"Error generating summary for {symbol}: {e}")
        return f"**{name} ({symbol})**: ${price:.2f} ({change:+.2f}%)\n\nError generating summary.\n"

def build_stock_prompt(stock_data):
    """Build the detailed prompt for a single stock (same logic as summarize_stock_news)"""
    symbol = stock_data['symbol']
    name = stock_data['name']
    price = stock_data['current_price']
    change = stock_data['change_percent']
    news = stock_data['news']
    earnings = stock_data.get('earnings')
    
    has_earnings = earnings is not None
    earnings_text = format_earnings_data(earnings) if has_earnings else ""
    
    # Build context for the LLM (same as individual prompt)
    if news or has_earnings:
        prompt_parts = [f"""Stock: {name} ({symbol})
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
        
        return "\n".join(prompt_parts)
        
    else:
        return f"""Stock: {name} ({symbol})
Current Price: ${price:.2f}
Change: {change:+.2f}%

No news articles or earnings reports were published recently for this stock.

Cover:
1. The price movement and what it suggests
2. Whether this aligns with broader market trends
3. Any technical observations worth noting

Be concise and factual. Mention that no news was available."""

def generate_market_summary():
    """Generate a brief macro market summary using the latest market data"""
    global _market_summary_cache
    
    # Return cached version if available
    if _market_summary_cache is not None:
        print("  Using cached market overview...")
        return _market_summary_cache
    
    try:
        import yfinance as yf
        
        # Get major indices
        spy = yf.Ticker("SPY")  # S&P 500
        qqq = yf.Ticker("QQQ")  # Nasdaq
        dia = yf.Ticker("DIA")  # Dow
        
        # Get today's data
        spy_hist = spy.history(period="2d")
        qqq_hist = qqq.history(period="2d")
        dia_hist = dia.history(period="2d")
        
        if spy_hist.empty or qqq_hist.empty or dia_hist.empty:
            return None
        
        # Calculate changes
        spy_change = ((spy_hist['Close'].iloc[-1] - spy_hist['Close'].iloc[-2]) / spy_hist['Close'].iloc[-2]) * 100
        qqq_change = ((qqq_hist['Close'].iloc[-1] - qqq_hist['Close'].iloc[-2]) / qqq_hist['Close'].iloc[-2]) * 100
        dia_change = ((dia_hist['Close'].iloc[-1] - dia_hist['Close'].iloc[-2]) / dia_hist['Close'].iloc[-2]) * 100
        
        # Build prompt for macro summary
        prompt = f"""You are a financial analyst providing a brief market overview.

Today's Market Performance:
- S&P 500: {spy_change:+.2f}%
- Nasdaq: {qqq_change:+.2f}%
- Dow Jones: {dia_change:+.2f}%

Provide a concise 2-3 sentence summary of the overall market environment. Focus on:
1. The general market direction and sentiment
2. Any notable sector trends if obvious from the indices
3. Keep it high-level and factual

DO NOT use a preamble. Start directly with the market analysis."""

        rate_limiter.wait_if_needed()
        response = model.generate_content(prompt)
        
        market_summary = {
            'spy_change': spy_change,
            'qqq_change': qqq_change,
            'dia_change': dia_change,
            'summary': response.text.strip()
        }
        
        # Cache the result
        _market_summary_cache = market_summary
        
        return market_summary
        
    except Exception as e:
        print(f"  Could not generate market summary: {e}")
        return None

def generate_digest(stocks_data, batch_size=10, user_name=None):
    """
    Generate a complete daily digest for all stocks using batched API calls
    
    Args:
        stocks_data: List of stock data dicts
        batch_size: Number of stocks to process per API call (default 10)
        user_name: Optional name for personalized greeting
    
    Returns:
        Complete formatted digest string
    """
    from datetime import datetime
    
    if not stocks_data:
        return ""
    
    # Get current time for greeting
    now = datetime.now()
    hour = now.hour
    
    # Determine greeting
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"
    
    if user_name:
        greeting = f"{greeting}, {user_name}!"
    else:
        greeting = f"{greeting}!"
    
    # Build digest header with title first, then personalized greeting
    digest_parts = [
        f"**Daily Stock Digest - {now.strftime('%A, %B %d, %Y')}**",
        "",
        f"{greeting}",
        "",
        "=" * 60,
        ""
    ]
    
    # Add market summary
    print("  Generating market overview...")
    market_data = generate_market_summary()
    
    if market_data:
        digest_parts.append("**Market Overview**")
        digest_parts.append("")
        digest_parts.append(f"**Major Indices:** S&P 500: {market_data['spy_change']:+.2f}% | Nasdaq: {market_data['qqq_change']:+.2f}% | Dow Jones: {market_data['dia_change']:+.2f}%")
        digest_parts.append("")
        digest_parts.append(market_data['summary'])
        digest_parts.append("")
    
    digest_parts.append("=" * 60)
    digest_parts.append("")
    
    digest_header = "\n".join(digest_parts)
    
    all_summaries = []
    
    # Process stocks in batches
    for i in range(0, len(stocks_data), batch_size):
        batch = stocks_data[i:i + batch_size]
        
        print(f"  Processing batch {i//batch_size + 1} ({len(batch)} stocks)...")
        
        # Build prompt using the same detailed logic as individual summaries
        batch_prompt = f"""You are a financial analyst providing daily stock updates.

For EACH stock below, provide a 3-4 sentence summary. DO NOT include any preamble like "Here's your update" or "Let me summarize". Start directly with the key information.

Format EACH stock exactly as:

**[Company Name] ([SYMBOL])**: $[price] ([+/-]X.XX%)

[Your 3-4 sentence analysis]

---

IMPORTANT: Add "---" separator after each stock EXCEPT the last one. The last stock should have NO separator after it.

STOCKS TO ANALYZE:

{'='*60}

"""
        
        # Add each stock with its detailed prompt
        stock_prompts = []
        for stock_data in batch:
            stock_prompt = build_stock_prompt(stock_data)
            stock_prompts.append(stock_prompt + "\n\n" + "="*60)
        
        batch_prompt += "\n".join(stock_prompts)
        
        try:
            # Wait if we're hitting rate limits
            rate_limiter.wait_if_needed()
            
            response = model.generate_content(batch_prompt)
            all_summaries.append(response.text)
        except Exception as e:
            print(f"  Error in batch {i//batch_size + 1}: {e}")
            # Fallback to individual for this batch
            for stock_data in batch:
                summary = summarize_stock_news(stock_data)
                all_summaries.append(summary + "\n" + "-" * 60 + "\n")
    
    # Combine all summaries
    digest = digest_header + "\n\n".join(all_summaries)
    
    # Add dashed separators between stocks
    digest = digest.replace("---\n\n**", "-" * 60 + "\n\n**")
    
    return digest

def generate_digest_fallback(stocks_data):
    """Fallback: generate digest with individual API calls"""
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