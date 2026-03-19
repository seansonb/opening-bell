"""
ThesisAgent — uses an LLM provider to analyze whether recent news and earnings
confirm, weaken, or are neutral/monitor-worthy relative to a stored thesis.
"""

import json
import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Allow imports from src/ when running directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from llm_providers import LLMProvider, get_provider
from thesis.thesis_manager import _parse_frontmatter
from stock.cache import stock_cache
from utils.debug import debug_log
from db.queries import get_thesis, save_verdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from fetch_news import fetch_stock_news
from fetch_earnings import fetch_earnings_data

DEFAULT_LLM_PROVIDER = 'claude'

VERDICT_CONFIRMS = 'CONFIRMS'
VERDICT_WEAKENS = 'WEAKENS'
VERDICT_NEUTRAL = 'NEUTRAL'
VERDICT_MONITOR = 'MONITOR'
SIGNIFICANT_VERDICTS = {VERDICT_CONFIRMS, VERDICT_WEAKENS}


@dataclass
class ThesisUpdate:
    ticker: str
    verdict: str
    summary: str
    suggested_log_entry: str
    is_significant: bool


def _get_company_description(ticker: str) -> str:
    """Return longBusinessSummary from cache, falling back to a direct yFinance call."""
    info = stock_cache.get_info(ticker)
    if info is None:
        import yfinance as yf
        info = yf.Ticker(ticker).info
    return info.get('longBusinessSummary', '')


def _build_prompt(ticker: str, thesis: dict, news: list, earnings: dict | None) -> str:
    frontmatter = thesis['frontmatter']
    body = thesis['body']

    news_block = ""
    if news:
        items = []
        for a in news:
            items.append(
                f"- [{a['published']}] {a['title']} ({a['publisher']})\n"
                f"  {a['summary']}"
            )
        news_block = "\n".join(items)
    else:
        news_block = "No recent news found."

    earnings_block = ""
    if earnings:
        lines = [f"  {k}: {v}" for k, v in earnings.items() if v is not None]
        earnings_block = "\n".join(lines)
    else:
        earnings_block = "No recent earnings data."

    description = _get_company_description(ticker)

    return f"""You are an investment thesis analyst. Evaluate whether the recent data CONFIRMS, WEAKENS, is NEUTRAL toward, or requires MONITORING for the thesis below.

== THESIS FOR {ticker} ==
Status: {frontmatter.get('status')}
Sector theses: {frontmatter.get('sector_theses')}
Macro theses: {frontmatter.get('macro_theses')}

COMPANY DESCRIPTION:
{description}

{body}

== RECENT NEWS ==
{news_block}

== RECENT EARNINGS DATA ==
{earnings_block}

== INSTRUCTIONS ==
Respond with ONLY valid JSON in this exact format — no markdown, no commentary:
{{
  "verdict": "CONFIRMS|WEAKENS|NEUTRAL|MONITOR",
  "summary": "2-3 sentence explanation of how the data relates to the thesis",
  "suggested_log_entry": "Full text of a dated log entry to append to the thesis file",
  "is_significant": true|false
}}

Rules:
- verdict must be exactly one of: CONFIRMS, WEAKENS, NEUTRAL, MONITOR
- is_significant must be true if verdict is CONFIRMS or WEAKENS, false otherwise
- suggested_log_entry should be concise, factual, and reference specific data points
"""


class ThesisAgent:
    def __init__(self, provider: LLMProvider | None = None):
        if provider is None:
            provider_name = os.getenv('LLM_PROVIDER', DEFAULT_LLM_PROVIDER).lower()
            provider = get_provider(provider_name)
        self.provider = provider

    def analyze(
        self,
        ticker: str,
        user_id: int | None = None,
        news: list | None = None,
        earnings: dict | None = None,
    ) -> ThesisUpdate:
        ticker = ticker.upper()

        # Load thesis from DB
        thesis_obj = get_thesis(user_id, ticker) if user_id is not None else None
        if thesis_obj is None:
            raise ValueError(f"No thesis found in DB for {ticker} (user_id={user_id})")
        frontmatter, body = _parse_frontmatter(thesis_obj.content)
        thesis = {'frontmatter': frontmatter, 'body': body}

        if news is None:
            news = fetch_stock_news(ticker)
        if earnings is None:
            earnings = fetch_earnings_data(ticker)

        prompt = _build_prompt(ticker, thesis, news, earnings)
        debug_log(f"THESIS PROMPT — {ticker}", prompt)

        raw = self.provider.generate(prompt, max_tokens=2048)
        debug_log(f"THESIS VERDICT — {ticker}", raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned non-JSON response: {e}\n\nRaw response:\n{raw}")

        verdict = data.get('verdict', 'NEUTRAL')
        summary = data.get('summary', '')
        save_verdict(thesis_obj.id, verdict, summary)

        return ThesisUpdate(
            ticker=ticker,
            verdict=verdict,
            summary=summary,
            suggested_log_entry=data.get('suggested_log_entry', ''),
            is_significant=verdict in SIGNIFICANT_VERDICTS,
        )
