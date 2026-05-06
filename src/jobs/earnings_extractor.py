"""
Earnings data extraction — yFinance snapshot + LLM extraction from EDGAR press release.

One haiku call per symbol when a press release is available; zero calls otherwise.
eps_estimate and eps_beat_miss are Python-computed from yFinance, not LLM-extracted.
thesis_verdict/commentary require thesis context — pass thesis=None to skip.
"""

import json
import logging
import math
import re
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

_HAIKU   = 'claude-haiku-4-5-20251001'
_SONNET  = 'claude-sonnet-4-6'

_LIST_FIELDS = {'forward_looking_topics', 'key_highlights', 'key_risks'}

_ALL_LLM_FIELDS = [
    'headline_summary',
    'revenue_reported', 'revenue_estimate', 'revenue_yoy_growth_pct', 'revenue_beat_miss',
    'gross_margin_pct', 'gross_margin_gaap', 'gross_margin_non_gaap',
    'gross_margin_pct_prior_year', 'gross_margin_gaap_prior_year', 'gross_margin_non_gaap_prior_year',
    'operating_margin_pct', 'operating_margin_gaap', 'operating_margin_non_gaap',
    'operating_margin_pct_prior_year', 'operating_margin_gaap_prior_year', 'operating_margin_non_gaap_prior_year',
    'operating_income_gaap', 'operating_income_non_gaap',
    'eps_gaap', 'eps_non_gaap',
    'eps_gaap_prior_year', 'eps_non_gaap_prior_year',
    'free_cash_flow', 'operating_cash_flow', 'cash_and_equivalents',
    'free_cash_flow_prior_year', 'operating_cash_flow_prior_year',
    'nrr_pct', 'arr', 'remaining_performance_obligations',
    'nrr_pct_prior_year', 'arr_prior_year',
    'customer_count', 'customer_count_yoy_growth_pct', 'large_customer_count', 'churn_pct',
    'guidance_revenue_low', 'guidance_revenue_high',
    'guidance_eps_low', 'guidance_eps_high',
    'guidance_operating_margin_low', 'guidance_operating_margin_high',
    'guidance_raised',
    'management_tone',
    'forward_looking_topics', 'key_highlights', 'key_risks',
]

_FIELD_DESCRIPTIONS = """\
- headline_summary: One sentence takeaway from the quarter
- revenue_reported: Total quarterly revenue in dollars (e.g. 1500000000 for $1.5B)
- revenue_estimate: Analyst consensus revenue estimate if cited in the press release
- revenue_yoy_growth_pct: Revenue growth vs same quarter last year (e.g. 15.3 for 15.3%)
- revenue_beat_miss: Revenue above/below consensus in dollars (positive=beat, negative=miss)
- gross_margin_pct: Gross margin % — use only if a single undifferentiated figure is given
- gross_margin_gaap: GAAP gross margin %
- gross_margin_non_gaap: Non-GAAP gross margin % (excludes stock-based comp, etc.)
- gross_margin_pct_prior_year: Prior year gross margin % (single figure, same quarter last year)
- gross_margin_gaap_prior_year: Prior year GAAP gross margin %
- gross_margin_non_gaap_prior_year: Prior year Non-GAAP gross margin %
- operating_margin_pct: Operating margin % — use only if a single undifferentiated figure is given
- operating_margin_gaap: GAAP operating margin %
- operating_margin_non_gaap: Non-GAAP operating margin %
- operating_margin_pct_prior_year: Prior year operating margin % (single figure, same quarter last year)
- operating_margin_gaap_prior_year: Prior year GAAP operating margin %
- operating_margin_non_gaap_prior_year: Prior year Non-GAAP operating margin %
- operating_income_gaap: GAAP operating income in dollars
- operating_income_non_gaap: Non-GAAP operating income in dollars
- eps_gaap: GAAP earnings (or loss) per share
- eps_non_gaap: Non-GAAP EPS (most commonly cited by management)
- eps_gaap_prior_year: GAAP EPS from the same quarter last year (for YoY comparison)
- eps_non_gaap_prior_year: Non-GAAP EPS from the same quarter last year (for YoY comparison)
- free_cash_flow: Operating cash flow minus capex, in dollars
- operating_cash_flow: Cash generated from operations, in dollars
- cash_and_equivalents: Cash and equivalents at end of quarter, in dollars
- free_cash_flow_prior_year: Free cash flow from the same quarter last year, in dollars
- operating_cash_flow_prior_year: Operating cash flow from the same quarter last year, in dollars
- nrr_pct: Net Revenue Retention as a percentage (e.g. 120 for 120%)
- arr: Annual Recurring Revenue in dollars
- remaining_performance_obligations: RPO or contracted backlog in dollars
- nrr_pct_prior_year: NRR from the same quarter last year as a percentage
- arr_prior_year: ARR from the same quarter last year in dollars
- customer_count: Total customer count
- customer_count_yoy_growth_pct: Customer count growth vs same quarter last year as %
- large_customer_count: Customers above a significant spend threshold (e.g. >$100K ARR)
- churn_pct: Gross churn rate as a percentage
- guidance_revenue_low: Low end of next-quarter or full-year revenue guidance in dollars
- guidance_revenue_high: High end of revenue guidance in dollars
- guidance_eps_low: Low end of EPS guidance
- guidance_eps_high: High end of EPS guidance
- guidance_operating_margin_low: Low end of operating margin guidance as %
- guidance_operating_margin_high: High end of operating margin guidance as %
- guidance_raised: true if company raised prior guidance, false if maintained or cut, null if not comparable
- management_tone: Overall tone — exactly one of: confident / cautious / mixed
- forward_looking_topics: Array of 2-5 themes management is emphasizing this quarter
- key_highlights: Array of 2-4 most important positive takeaways
- key_risks: Array of 1-3 risks or concerns raised\
"""

_SYSTEM = (
    "You are a financial data extractor. Extract structured fields from an earnings press release "
    "and return ONLY a valid JSON object. No explanation, no markdown, no text before or after the JSON. "
    "All numeric values are bare numbers — no units, currency symbols, or commas. "
    "Percentages are bare numbers (e.g. 62.5 not '62.5%'). "
    "Dollar amounts are in full dollars (e.g. 1500000000 not 1.5 or '$1.5B'). "
    "Use null for any field not found in the source material."
)


def fetch_yfinance_snapshot(symbol: str) -> dict:
    """
    Pull company name, price movement, and EPS data from yFinance.
    All values may be None if unavailable — never raises.
    """
    result = {
        'company_name': symbol,
        'current_price': None,
        'prev_close': None,
        'price_change_pct': None,
        'eps_estimate': None,
        'eps_reported_yf': None,
        'eps_surprise_pct': None,
    }
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)

        try:
            info = ticker.info
            result['company_name'] = info.get('longName') or info.get('shortName') or symbol
        except Exception:
            pass

        try:
            hist = ticker.history(period='2d')
            if not hist.empty:
                result['current_price'] = float(hist['Close'].iloc[-1])
                if len(hist) >= 2:
                    result['prev_close'] = float(hist['Close'].iloc[-2])
                    result['price_change_pct'] = (
                        (result['current_price'] - result['prev_close'])
                        / result['prev_close'] * 100
                    )
        except Exception as e:
            log.warning(f"[extractor] {symbol}: price history error — {e}")

        try:
            dates = ticker.earnings_dates
            if dates is not None and not dates.empty:
                now = datetime.now(timezone.utc)
                past = dates[dates.index <= now]
                if not past.empty:
                    row = past.iloc[0]
                    result['eps_estimate'] = _safe_float(row.get('EPS Estimate'))
                    result['eps_reported_yf'] = _safe_float(row.get('Reported EPS'))
                    result['eps_surprise_pct'] = _safe_float(row.get('Surprise(%)'))
        except Exception as e:
            log.warning(f"[extractor] {symbol}: earnings_dates error — {e}")

    except Exception as e:
        log.warning(f"[extractor] {symbol}: yFinance snapshot failed — {e}")

    return result


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _build_prompt(edgar_data, yf_snapshot: dict, thesis, news: list[dict]) -> str:
    lines = [f"# Earnings Extraction — {edgar_data.symbol}\n"]

    lines.append("## Press Release\n")
    lines.append(edgar_data.press_release_text)
    lines.append("")

    ctx = []
    if yf_snapshot.get('eps_estimate') is not None:
        ctx.append(f"Analyst EPS estimate (yFinance): {yf_snapshot['eps_estimate']}")
    if yf_snapshot.get('current_price') is not None:
        price = f"${yf_snapshot['current_price']:.2f}"
        if yf_snapshot.get('price_change_pct') is not None:
            price += f" ({yf_snapshot['price_change_pct']:+.2f}% today)"
        ctx.append(f"Stock price: {price}")
    if ctx:
        lines.append("## Market Context\n")
        lines.extend(f"- {c}" for c in ctx)
        lines.append("")

    if thesis is not None:
        lines.append("## Investment Thesis\n")
        if thesis.sector_theses:
            lines.append("Sector theses: " + " | ".join(thesis.sector_theses))
        if thesis.macro_theses:
            lines.append("Macro theses: " + " | ".join(thesis.macro_theses))
        if thesis.body:
            lines.append(thesis.body[:2500])
        lines.append("")

    if news:
        lines.append("## Recent News Headlines\n")
        for a in news[:10]:
            pub = a.get('published_at', '')
            if hasattr(pub, 'strftime'):
                pub = pub.strftime('%Y-%m-%d')
            lines.append(f"- [{pub}] {a.get('title', '')}")
        lines.append("")

    lines.append("## Extraction Instructions\n")
    lines.append(
        "Extract the following fields from the press release above. "
        "Return ONLY a JSON object starting with { and ending with }. "
        "All numbers are bare numeric values. "
        "Use null for any field not found.\n"
    )
    lines.append(_FIELD_DESCRIPTIONS)

    return "\n".join(lines)


def _parse_response(raw: str, symbol: str) -> dict:
    text = raw.strip()

    fence = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', text)
    if fence:
        text = fence.group(1).strip()
    else:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end > start:
            text = text[start:end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        log.error(f"[extractor] {symbol}: JSON parse error — {e}")
        log.debug(f"[extractor] {symbol}: raw snippet: {raw[:400]}")
        return {}

    result = {}
    for field in _ALL_LLM_FIELDS:
        val = data.get(field)
        result[field] = val if field not in _LIST_FIELDS else (val if isinstance(val, list) else [])

    return result


def run_llm_extraction(edgar_data, yf_snapshot: dict, thesis, news: list[dict]) -> dict:
    """
    Call haiku to extract earnings fields from the press release.
    Returns the extracted dict; empty dict on failure.
    Adds eps_estimate and eps_beat_miss from yFinance (not LLM-extracted).
    """
    from llm.llm_providers import get_provider

    symbol = edgar_data.symbol
    prompt = _build_prompt(edgar_data, yf_snapshot, thesis, news)
    log.info(f"[extractor] {symbol}: prompt {len(prompt):,} chars — calling haiku")

    try:
        provider = get_provider('claude', model=_HAIKU)
        raw = provider.generate(prompt, system=_SYSTEM, max_tokens=2048)
        log.info(f"[extractor] {symbol}: response {len(raw)} chars")
    except Exception as e:
        log.error(f"[extractor] {symbol}: LLM call failed — {e}")
        return {}

    fields = _parse_response(raw, symbol)
    if not fields:
        return {}

    # Python-computed EPS fields — not delegated to the LLM
    eps_estimate = yf_snapshot.get('eps_estimate')
    fields['eps_estimate'] = eps_estimate
    eps_reported = (
        fields.get('eps_non_gaap') if fields.get('eps_non_gaap') is not None
        else fields.get('eps_gaap')
    )
    fields['eps_beat_miss'] = (
        round(eps_reported - eps_estimate, 4)
        if eps_estimate is not None and eps_reported is not None
        else None
    )
    yf_surprise = yf_snapshot.get('eps_surprise_pct')
    if yf_surprise is not None:
        fields['eps_surprise_pct'] = yf_surprise
    elif eps_estimate is not None and eps_reported is not None and eps_estimate != 0:
        fields['eps_surprise_pct'] = round((eps_reported - eps_estimate) / abs(eps_estimate) * 100, 2)
    else:
        fields['eps_surprise_pct'] = None

    log.info(
        f"[extractor] {symbol}: extracted — "
        f"tone={fields.get('management_tone')}, "
        f"highlights={len(fields.get('key_highlights', []))}, "
        f"nrr={fields.get('nrr_pct')}"
    )
    return fields


def run_thesis_evaluation(edgar_data, llm_fields: dict, thesis) -> tuple[str | None, str | None]:
    """
    Evaluate how this quarter's results relate to a user's specific thesis.
    Uses Sonnet for the nuanced judgment call. Returns (verdict, commentary).
    """
    from llm.llm_providers import get_provider

    symbol = edgar_data.symbol

    lines = [f"# Thesis Evaluation — {symbol}\n"]

    lines.append("## Quarter Results\n")
    kv = [
        ('Headline',        llm_fields.get('headline_summary')),
        ('Revenue YoY',     f"{llm_fields['revenue_yoy_growth_pct']}%" if llm_fields.get('revenue_yoy_growth_pct') is not None else None),
        ('Non-GAAP EPS',    llm_fields.get('eps_non_gaap')),
        ('EPS vs estimate', f"{llm_fields['eps_beat_miss']:+.4f}" if llm_fields.get('eps_beat_miss') is not None else None),
        ('EPS surprise',    f"{llm_fields['eps_surprise_pct']:+.1f}%" if llm_fields.get('eps_surprise_pct') is not None else None),
        ('Guidance raised', llm_fields.get('guidance_raised')),
        ('Management tone', llm_fields.get('management_tone')),
    ]
    for label, val in kv:
        if val is not None:
            lines.append(f"- {label}: {val}")
    if llm_fields.get('key_highlights'):
        lines.append(f"- Highlights: {'; '.join(llm_fields['key_highlights'])}")
    if llm_fields.get('key_risks'):
        lines.append(f"- Risks: {'; '.join(llm_fields['key_risks'])}")
    lines.append("")

    lines.append("## Investment Thesis\n")
    if thesis.sector_theses:
        lines.append("Sector theses: " + " | ".join(thesis.sector_theses))
    if thesis.macro_theses:
        lines.append("Macro theses: " + " | ".join(thesis.macro_theses))
    if thesis.body:
        lines.append(thesis.body[:2500])
    lines.append("")

    lines.append(
        "Evaluate how this quarter's results relate to the investment thesis above.\n\n"
        "Return only a JSON object:\n"
        '{"verdict": "validates" | "weakens" | "neutral" | "monitor", '
        '"commentary": "2-3 sentences explaining the verdict"}\n\n'
        "verdict definitions:\n"
        "- validates: results clearly support a key thesis assumption\n"
        "- weakens: results clearly contradict a key thesis assumption\n"
        "- monitor: mixed signals — thesis is neither confirmed nor broken, but warrants watching\n"
        "- neutral: results are not meaningfully related to the thesis\n\n"
        "No preamble, no markdown."
    )

    prompt = "\n".join(lines)

    try:
        provider = get_provider('claude', model=_SONNET)
        raw = provider.generate(prompt, max_tokens=400).strip()
        if raw.startswith('```'):
            raw = re.sub(r'^```[a-z]*\n?', '', raw)
            raw = re.sub(r'\n?```$', '', raw).strip()
        data = json.loads(raw)
        verdict = data.get('verdict')
        commentary = data.get('commentary')
        log.info(f"[extractor] {symbol}: thesis verdict={verdict}")
        return verdict, commentary
    except Exception as e:
        log.error(f"[extractor] {symbol}: thesis evaluation failed — {e}")
        return None, None
