import yfinance as yf
from datetime import datetime, timedelta

def fetch_earnings_data(symbol, days_back=1):
    """Fetch recent earnings data if available"""
    try:
        ticker = yf.Ticker(symbol)
        
        # Get earnings dates
        earnings_dates = ticker.earnings_dates
        if earnings_dates is None or earnings_dates.empty:
            return None
        
        # Filter for PAST earnings only (dates before now)
        from datetime import timezone
        now = datetime.now(timezone.utc)
        past_earnings = earnings_dates[earnings_dates.index < now]
        
        if past_earnings.empty:
            return None
        
        # Check if the most recent past earnings happened in the last N days
        cutoff_date = now - timedelta(days=days_back)
        most_recent = past_earnings.index[0]  # Most recent is first
        
        if most_recent < cutoff_date:
            return None
        
        # Get the most recent earnings data
        recent_earnings = past_earnings.iloc[[0]]
        
        # Get financials
        info = ticker.info
        
        # Build comprehensive earnings data
        earnings_data = {
            'earnings_date': recent_earnings.index[0].strftime('%Y-%m-%d'),
            'reported_eps': recent_earnings['Reported EPS'].iloc[0] if 'Reported EPS' in recent_earnings else None,
            'estimated_eps': recent_earnings['EPS Estimate'].iloc[0] if 'EPS Estimate' in recent_earnings else None,
            'surprise': recent_earnings['Surprise(%)'].iloc[0] if 'Surprise(%)' in recent_earnings else None,
        }
        
        # Core financials from info
        if info:
            earnings_data.update({
                # Revenue
                'revenue': info.get('totalRevenue'),
                'revenue_yoy_growth': info.get('revenueGrowth'),
                
                # Earnings
                'net_income': info.get('netIncomeToCommon'),
                'eps': info.get('trailingEps'),
                'forward_eps': info.get('forwardEps'),
                
                # Margins
                'gross_margin': info.get('grossMargins'),
                'operating_margin': info.get('operatingMargins'),
                'profit_margin': info.get('profitMargins'),
                'ebitda_margin': info.get('ebitdaMargins'),
                
                # Cash flow
                'free_cash_flow': info.get('freeCashflow'),
                'operating_cash_flow': info.get('operatingCashflow'),
                
                # Balance sheet
                'total_cash': info.get('totalCash'),
                'total_debt': info.get('totalDebt'),
                'current_ratio': info.get('currentRatio'),
                'quick_ratio': info.get('quickRatio'),
                
                # Valuation
                'market_cap': info.get('marketCap'),
                'pe_ratio': info.get('trailingPE'),
                'forward_pe': info.get('forwardPE'),
                'ps_ratio': info.get('priceToSalesTrailing12Months'),
                'price_to_book': info.get('priceToBook'),
                'ev_to_revenue': info.get('enterpriseToRevenue'),
                'ev_to_ebitda': info.get('enterpriseToEbitda'),
                
                # Growth metrics
                'earnings_growth': info.get('earningsGrowth'),
                'revenue_per_share': info.get('revenuePerShare'),
                
                # Guidance
                'target_high_price': info.get('targetHighPrice'),
                'target_low_price': info.get('targetLowPrice'),
                'target_mean_price': info.get('targetMeanPrice'),
                'recommendation': info.get('recommendationKey'),
            })
        
        return earnings_data
        
    except Exception as e:
        print(f"  Error fetching earnings for {symbol}: {e}")
        return None