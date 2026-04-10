"""
Sector context — maps stocks to sector classes via yfinance industry fields,
fetches ETF performance + news, and synthesizes a sector narrative via LLM.
"""

import json
import os
from datetime import datetime, timedelta

import yfinance as yf

from stock.cache import stock_cache
from utils.debug import debug_log

_sector_context_cache: dict = {}
_sector_classes_cache: dict | None = None


def _load_sector_classes() -> dict:
    global _sector_classes_cache
    if _sector_classes_cache is None:
        config_path = os.path.join(os.path.dirname(__file__), '../../data/sector_classes.json')
        with open(config_path) as f:
            _sector_classes_cache = json.load(f)
    return _sector_classes_cache


def get_sector_class(ticker: str) -> tuple[str, dict] | tuple[None, None]:
    """
    Map a ticker to its sector class using its yfinance industry field.
    Returns (class_name, config) or (None, None) if no match.
    """
    info = stock_cache.get_info(ticker)
    if not info:
        return None, None

    industry = info.get('industry', '')
    sector_classes = _load_sector_classes()

    for class_name, config in sector_classes.items():
        if industry in config.get('industries', []):
            return class_name, config

    return None, None


def _parse_etf_news(raw_news: list, days_back: int = 3) -> list:
    """Parse raw yfinance news into normalized article dicts."""
    cutoff = datetime.now() - timedelta(days=days_back)
    articles = []
    for article in raw_news or []:
        content = article.get('content') or {}
        pub_str = content.get('pubDate', '')
        try:
            pub_date = datetime.fromisoformat(pub_str.replace('Z', '+00:00')).replace(tzinfo=None)
        except Exception:
            pub_date = datetime.min
        if pub_date < cutoff:
            continue
        provider = content.get('provider') or {}
        articles.append({
            'title': content.get('title', ''),
            'publisher': provider.get('displayName', ''),
            'published': pub_date.strftime('%Y-%m-%d %H:%M'),
            'summary': content.get('summary', ''),
        })
    return articles


def fetch_sector_context(class_name: str, config: dict) -> dict | None:
    """
    Fetch ETF % change + news for a sector class, then synthesize via LLM.
    Cached per sector so multiple stocks in the same class only trigger one call.
    """
    if class_name in _sector_context_cache:
        return _sector_context_cache[class_name]

    etf = config['etf']
    print(f"  Fetching sector context: {class_name} ({etf})...")

    try:
        ticker = yf.Ticker(etf)

        hist = ticker.history(period="2d")
        if hist.empty or len(hist) < 2:
            return None
        change_pct = (
            (hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]
        ) * 100

        articles = _parse_etf_news(ticker.news)
        debug_log(
            f"SECTOR NEWS — {class_name} ({etf})",
            "\n".join(f"[{a['published']}] {a['title']}" for a in articles) or "(none)",
        )

        news_text = ""
        for i, a in enumerate(articles[:10], 1):
            news_text += f"{i}. {a['title']} ({a['publisher']}, {a['published']})\n"
            if a['summary']:
                news_text += f"   {a['summary']}\n"

        if not news_text:
            news_text = "No recent sector news found."

        from os import getenv
        from llm.llm_providers import get_provider
        provider = get_provider(getenv('LLM_PROVIDER', 'claude').lower())

        prompt = f"""You are a financial analyst. Summarize the current state of the {class_name} sector in 2-3 sentences.

Sector ETF ({etf}): {change_pct:+.2f}% today

Recent sector news:
{news_text}

Be specific and factual about what is driving the sector right now. Do not use a preamble."""

        debug_log(f"SECTOR PROMPT — {class_name}", prompt)
        summary = provider.generate(prompt).strip()
        debug_log(f"SECTOR SUMMARY — {class_name}", summary)

        context = {
            'class_name': class_name,
            'etf': etf,
            'change_pct': change_pct,
            'summary': summary,
        }
        _sector_context_cache[class_name] = context
        return context

    except Exception as e:
        print(f"  Could not generate sector context for {class_name}: {e}")
        return None


def clear_sector_cache() -> None:
    global _sector_context_cache
    _sector_context_cache.clear()
