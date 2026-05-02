"""
Earnings report renderer — builds Jinja2 context from extracted fields
and renders src/templates/earnings/report.html.
"""

import logging
import os
from datetime import datetime
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

log = logging.getLogger(__name__)

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates')


# ---------------------------------------------------------------------------
# Jinja2 filters
# ---------------------------------------------------------------------------

def _fmt_currency(val, signed=False) -> str:
    if val is None:
        return '—'
    try:
        v = float(val)
        neg = v < 0
        a = abs(v)
        if a >= 1_000_000_000:
            s = f'{a / 1_000_000_000:.2f}B'
        elif a >= 1_000_000:
            s = f'{a / 1_000_000:.0f}M' if a % 1_000_000 == 0 else f'{a / 1_000_000:.1f}M'
        elif a >= 1_000:
            s = f'{a / 1_000:.0f}K' if a % 1_000 == 0 else f'{a / 1_000:.1f}K'
        else:
            s = f'{a:.2f}'
        if signed:
            return f'-${s}' if neg else f'+${s}'
        return f'-${s}' if neg else f'${s}'
    except (TypeError, ValueError):
        return '—'


def _fmt_pct(val, signed=False) -> str:
    if val is None:
        return '—'
    try:
        v = float(val)
        return f'{v:+.1f}%' if signed else f'{v:.1f}%'
    except (TypeError, ValueError):
        return '—'


def _fmt_pp(val) -> str:
    """Format a percentage-point change: +5.0pp, -2.3pp."""
    if val is None:
        return '—'
    try:
        return f'{float(val):+.1f}pp'
    except (TypeError, ValueError):
        return '—'


def _sign_class(val) -> str:
    if val is None:
        return ''
    try:
        return 'pos' if float(val) >= 0 else 'neg'
    except (TypeError, ValueError):
        return ''


def _get_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=select_autoescape(['html']),
    )
    env.filters['currency'] = _fmt_currency
    env.filters['pct'] = _fmt_pct
    env.filters['pp'] = _fmt_pp
    env.globals['sign_class'] = _sign_class
    return env


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _any(*vals) -> bool:
    return any(v is not None for v in vals)


def _pct_change(current, prior) -> Optional[float]:
    """% change from prior to current."""
    if current is None or prior is None or prior == 0:
        return None
    try:
        return (float(current) - float(prior)) / abs(float(prior)) * 100
    except (TypeError, ValueError):
        return None


def _pp_change(current, prior) -> Optional[float]:
    """Percentage-point change (for margins/rates already expressed as %)."""
    if current is None or prior is None:
        return None
    try:
        return float(current) - float(prior)
    except (TypeError, ValueError):
        return None


def _build_context(
    symbol: str,
    earnings_date: datetime,
    yf_snapshot: dict,
    llm_fields: Optional[dict],
    news: list[dict],
    thesis=None,
) -> dict:
    f = llm_fields or {}

    # Price
    price = None
    if yf_snapshot.get('current_price') is not None:
        price = {
            'current': yf_snapshot['current_price'],
            'change_pct': yf_snapshot.get('price_change_pct'),
        }

    # EPS — YoY as % change
    eps = None
    if _any(f.get('eps_gaap'), f.get('eps_non_gaap'), f.get('eps_estimate')):
        eps = {
            'gaap': f.get('eps_gaap'),
            'non_gaap': f.get('eps_non_gaap'),
            'estimate': f.get('eps_estimate'),
            'beat_miss': f.get('eps_beat_miss'),
            'surprise_pct': yf_snapshot.get('eps_surprise_pct'),
            'gaap_yoy_pct': _pct_change(f.get('eps_gaap'), f.get('eps_gaap_prior_year')),
            'non_gaap_yoy_pct': _pct_change(f.get('eps_non_gaap'), f.get('eps_non_gaap_prior_year')),
        }

    # Revenue
    revenue = None
    if f.get('revenue_reported') is not None:
        revenue = {
            'reported': f.get('revenue_reported'),
            'estimate': f.get('revenue_estimate'),
            'yoy_growth_pct': f.get('revenue_yoy_growth_pct'),
            'beat_miss': f.get('revenue_beat_miss'),
        }

    # Margins — YoY as pp change (percentage points)
    margins = None
    if _any(
        f.get('gross_margin_pct'), f.get('gross_margin_gaap'), f.get('gross_margin_non_gaap'),
        f.get('operating_margin_pct'), f.get('operating_margin_gaap'), f.get('operating_margin_non_gaap'),
        f.get('operating_income_gaap'), f.get('operating_income_non_gaap'),
    ):
        margins = {
            'gross_single': f.get('gross_margin_pct'),
            'gross_single_pp': _pp_change(f.get('gross_margin_pct'), f.get('gross_margin_pct_prior_year')),
            'gross_gaap': f.get('gross_margin_gaap'),
            'gross_gaap_pp': _pp_change(f.get('gross_margin_gaap'), f.get('gross_margin_gaap_prior_year')),
            'gross_non_gaap': f.get('gross_margin_non_gaap'),
            'gross_non_gaap_pp': _pp_change(f.get('gross_margin_non_gaap'), f.get('gross_margin_non_gaap_prior_year')),
            'operating_single': f.get('operating_margin_pct'),
            'operating_single_pp': _pp_change(f.get('operating_margin_pct'), f.get('operating_margin_pct_prior_year')),
            'operating_gaap': f.get('operating_margin_gaap'),
            'operating_gaap_pp': _pp_change(f.get('operating_margin_gaap'), f.get('operating_margin_gaap_prior_year')),
            'operating_non_gaap': f.get('operating_margin_non_gaap'),
            'operating_non_gaap_pp': _pp_change(f.get('operating_margin_non_gaap'), f.get('operating_margin_non_gaap_prior_year')),
            'income_gaap': f.get('operating_income_gaap'),
            'income_non_gaap': f.get('operating_income_non_gaap'),
        }

    # Cash flow — YoY as % change
    cash_flow = None
    if _any(f.get('free_cash_flow'), f.get('operating_cash_flow'), f.get('cash_and_equivalents')):
        cash_flow = {
            'free': f.get('free_cash_flow'),
            'free_yoy_pct': _pct_change(f.get('free_cash_flow'), f.get('free_cash_flow_prior_year')),
            'operating': f.get('operating_cash_flow'),
            'operating_yoy_pct': _pct_change(f.get('operating_cash_flow'), f.get('operating_cash_flow_prior_year')),
            'cash': f.get('cash_and_equivalents'),
        }

    # SaaS / key metrics — NRR as pp change, ARR as % change
    saas = None
    if _any(
        f.get('nrr_pct'), f.get('arr'), f.get('remaining_performance_obligations'),
        f.get('customer_count'), f.get('customer_count_yoy_growth_pct'),
        f.get('large_customer_count'), f.get('churn_pct'),
    ):
        saas = {
            'nrr_pct': f.get('nrr_pct'),
            'nrr_pp': _pp_change(f.get('nrr_pct'), f.get('nrr_pct_prior_year')),
            'arr': f.get('arr'),
            'arr_yoy_pct': _pct_change(f.get('arr'), f.get('arr_prior_year')),
            'rpo': f.get('remaining_performance_obligations'),
            'customers': f.get('customer_count'),
            'customers_yoy_pct': f.get('customer_count_yoy_growth_pct'),
            'large_customers': f.get('large_customer_count'),
            'churn_pct': f.get('churn_pct'),
        }

    # Guidance
    guidance = None
    if _any(
        f.get('guidance_revenue_low'), f.get('guidance_revenue_high'),
        f.get('guidance_eps_low'), f.get('guidance_eps_high'),
        f.get('guidance_operating_margin_low'), f.get('guidance_operating_margin_high'),
        f.get('guidance_raised'),
    ):
        guidance = {
            'revenue_low': f.get('guidance_revenue_low'),
            'revenue_high': f.get('guidance_revenue_high'),
            'eps_low': f.get('guidance_eps_low'),
            'eps_high': f.get('guidance_eps_high'),
            'margin_low': f.get('guidance_operating_margin_low'),
            'margin_high': f.get('guidance_operating_margin_high'),
            'raised': f.get('guidance_raised'),
        }

    # Management
    management = None
    topics = f.get('forward_looking_topics') or []
    if f.get('management_tone') or topics:
        management = {
            'tone': f.get('management_tone'),
            'topics': topics,
        }

    highlights = f.get('key_highlights') or None
    risks = f.get('key_risks') or None

    # Thesis
    thesis_ctx = None
    if f.get('thesis_verdict') or f.get('thesis_commentary'):
        thesis_ctx = {
            'verdict': f.get('thesis_verdict'),
            'commentary': f.get('thesis_commentary'),
        }

    # News — pre-format dates to avoid strftime in template
    news_ctx = []
    for a in (news or [])[:8]:
        pub = a.get('published_at')
        pub_str = pub.strftime('%b %-d') if pub else ''
        news_ctx.append({
            'title': a.get('title', ''),
            'url': a.get('url', ''),
            'publisher': a.get('publisher', ''),
            'published_str': pub_str,
        })

    date_str = (
        earnings_date.strftime('%B %-d, %Y')
        if isinstance(earnings_date, datetime)
        else str(earnings_date)
    )

    return {
        'symbol': symbol,
        'company_name': yf_snapshot.get('company_name') or symbol,
        'earnings_date': date_str,
        'headline': f.get('headline_summary') or None,
        'price': price,
        'eps': eps,
        'revenue': revenue,
        'margins': margins,
        'cash_flow': cash_flow,
        'saas': saas,
        'guidance': guidance,
        'management': management,
        'highlights': highlights or None,
        'risks': risks or None,
        'thesis': thesis_ctx,
        'news': news_ctx or None,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_earnings_report(
    symbol: str,
    earnings_date: datetime,
    edgar_data,
    yf_snapshot: dict,
    llm_fields: Optional[dict],
    news: list[dict],
    thesis=None,
) -> str:
    """Render the earnings report as an HTML email string."""
    ctx = _build_context(symbol, earnings_date, yf_snapshot, llm_fields, news, thesis)
    env = _get_env()
    template = env.get_template('earnings/report.html')
    html = template.render(**ctx)
    log.info(f"[renderer] {symbol}: rendered {len(html):,} chars")
    return html
