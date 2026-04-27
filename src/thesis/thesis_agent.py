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

from llm.llm_providers import LLMProvider, get_provider
from stock.cache import stock_cache
from utils.debug import debug_log
from db.queries import get_thesis, save_verdict
from utils.news_injector import get_injected_articles

from stock.fetch_news import fetch_stock_news
from stock.fetch_earnings import fetch_earnings_data

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
    detail: str
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

    return f"""You are an investment thesis analyst. Your job is to evaluate whether recent data materially changes the investment case described below.

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
  "summary": "2-3 sentence high-level explanation for the thesis watch digest",
  "detail": "Detailed breakdown — see requirements below",
  "suggested_log_entry": "Full text of a dated log entry to append to the thesis file",
  "is_significant": true|false
}}

== VERDICT CRITERIA ==
Use EXACTLY one of the four verdicts below. When in doubt, prefer NEUTRAL or MONITOR over CONFIRMS or WEAKENS.

CONFIRMS — Use only when:
- A key thesis assumption is directly validated by hard data (earnings beat on a thesis-critical metric, product launch success, market share gain, etc.)
- The data meaningfully reduces a bear case risk that was central to the thesis
- Multiple signals point in the same direction and all reinforce the core investment case

WEAKENS — Use only when:
- A core thesis assumption is contradicted by hard data (e.g. thesis depends on margin expansion, margins materially contracted)
- A risk the thesis explicitly acknowledged has now materialized in a measurable way
- Do NOT use for: general macro headwinds, sector rotation, analyst downgrades without new fundamental data, short-term price moves, or negative sentiment that doesn't contradict a specific thesis claim

MONITOR — Use when:
- A new risk or development has emerged that is NOT yet reflected in fundamentals but could become thesis-relevant
- An assumption in the thesis is now uncertain but not yet disproven
- You need more data before making a directional call
- Macro or sector-level signals that could affect the thesis but haven't yet

NEUTRAL — Use when:
- The data is consistent with existing expectations and neither confirms nor challenges any thesis assumption
- News is company-relevant but thesis-irrelevant (e.g. executive hire unrelated to the investment case)
- Normal business activity with no meaningful signal in either direction

== DETAIL FIELD REQUIREMENTS ==
The "detail" field must be specific to the verdict:

If CONFIRMS:
- Which specific thesis claim or assumption is being confirmed
- What data point(s) directly support it (cite numbers where available)
- Whether this strengthens conviction or simply validates an existing assumption
- Any nuance or offsetting factor that tempers the confirmation

If WEAKENS:
- Which specific thesis claim or assumption is being contradicted
- What data point(s) directly contradict it (cite numbers where available)
- Whether this is a structural change or potentially temporary
- What would need to happen for the thesis to recover

If MONITOR:
- What specific development or signal triggered the MONITOR verdict
- Which thesis assumption it puts at risk and why
- What data, event, or timeframe would resolve the uncertainty
- Suggested thesis update or new risk to add to the thesis file

If NEUTRAL:
- Brief confirmation of why the data is thesis-irrelevant (1-2 sentences is fine)

== RULES ==
- verdict must be exactly one of: CONFIRMS, WEAKENS, NEUTRAL, MONITOR
- is_significant must be true if verdict is CONFIRMS or WEAKENS, false otherwise
- summary must reference which specific thesis claim or assumption the data relates to — do not give a generic market summary
- suggested_log_entry should be concise, factual, and reference specific data points
- detail must follow the requirements above for the given verdict
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
        injected_news: dict | None = None,
        scenario: str = 'confirms',
    ) -> ThesisUpdate:
        ticker = ticker.upper()

        # Load thesis from DB
        thesis_obj = get_thesis(user_id, ticker) if user_id is not None else None
        if thesis_obj is None:
            raise ValueError(f"No thesis found in DB for {ticker} (user_id={user_id})")
        thesis = {
            'frontmatter': {
                'status': thesis_obj.status,
                'sector_theses': thesis_obj.sector_theses,
                'macro_theses': thesis_obj.macro_theses,
            },
            'body': thesis_obj.body,
        }

        # Inject fake news if requested, otherwise use real news
        if injected_news is not None:
            news = get_injected_articles(ticker, injected_news, scenario)
            debug_content = "\n\n".join(
                f"[{a.get('published', '')}] {a.get('title', '')}\n  {a.get('summary', '')}"
                for a in news
            )
            debug_log(f"INJECTED NEWS — {ticker} ({scenario})", debug_content)
        else:
            if news is None:
                news = fetch_stock_news(ticker)

        if earnings is None:
            earnings = fetch_earnings_data(ticker)

        prompt = _build_prompt(ticker, thesis, news, earnings)
        debug_log(f"THESIS PROMPT — {ticker}", prompt)

        raw = self.provider.generate(prompt, max_tokens=2048)
        debug_log(f"THESIS VERDICT — {ticker}", raw)

        # Strip markdown code fences if the LLM wrapped the response
        cleaned = raw.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[-1]
            cleaned = cleaned.rsplit('```', 1)[0].strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned non-JSON response: {e}\n\nRaw response:\n{raw}")

        verdict = data.get('verdict', 'NEUTRAL')
        summary = data.get('summary', '')
        detail = data.get('detail', '')
        save_verdict(thesis_obj.id, verdict, summary)

        return ThesisUpdate(
            ticker=ticker,
            verdict=verdict,
            summary=summary,
            detail=detail,
            suggested_log_entry=data.get('suggested_log_entry', ''),
            is_significant=verdict in SIGNIFICANT_VERDICTS,
        )
