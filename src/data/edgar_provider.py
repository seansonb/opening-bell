"""
EDGAR data provider — fetches earnings press releases and upcoming earnings dates.

Press releases come from SEC EDGAR 8-K filings (Item 2.02, EX-99.1 exhibit).
Earnings dates fall back to yFinance since EDGAR submissions only cover past filings.

Requires EDGAR_USER_AGENT in .env: "OpeningBell your@email.com"
"""

import os
import re
import time
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

_SEC_BASE = "https://www.sec.gov"
_SEC_DATA = "https://data.sec.gov"
_RATE_DELAY = 0.15   # SEC limit: max 10 req/sec
_MAX_CHARS  = 80_000

_cik_map: dict | None = None  # module-level cache, loaded once


def _get(url: str, accept: str = "application/json") -> Optional[requests.Response]:
    time.sleep(_RATE_DELAY)
    agent = os.getenv("EDGAR_USER_AGENT", "")
    if not agent:
        print("  [edgar] WARNING: EDGAR_USER_AGENT not set — SEC may reject requests")
    try:
        r = requests.get(
            url,
            headers={"User-Agent": agent, "Accept": accept},
            timeout=20,
        )
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  [edgar] GET failed: {e} — {url}")
        return None


def _load_cik_map() -> dict:
    global _cik_map
    if _cik_map is not None:
        return _cik_map
    r = _get(f"{_SEC_BASE}/files/company_tickers.json")
    if r is None:
        return {}
    _cik_map = {v["ticker"].upper(): str(v["cik_str"]) for v in r.json().values()}
    return _cik_map


def _get_cik(symbol: str) -> Optional[str]:
    return _load_cik_map().get(symbol.upper())


def _get_recent_8k_accession(cik: str) -> Optional[str]:
    """Return the accession number of the most recent 8-K containing Item 2.02."""
    cik_padded = cik.zfill(10)
    r = _get(f"{_SEC_DATA}/submissions/CIK{cik_padded}.json")
    if r is None:
        return None
    recent = r.json().get("filings", {}).get("recent", {})
    for form, items, accession in zip(
        recent.get("form", []),
        recent.get("items", []),
        recent.get("accessionNumber", []),
    ):
        if form == "8-K" and "2.02" in str(items):
            return accession
    return None


def _find_ex991_url(index_html: str) -> Optional[str]:
    """Parse the filing index page and return the full URL of the EX-99.1 document."""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", index_html, re.DOTALL | re.IGNORECASE)
    for row in rows:
        if re.search(r"EX-99\.1", row, re.IGNORECASE):
            href = re.search(r'href="(/Archives/edgar/data/[^"]+)"', row, re.IGNORECASE)
            if href:
                return _SEC_BASE + href.group(1)
    return None


def _strip_html(html: str) -> str:
    """Strip HTML tags and entities; collapse whitespace to readable plain text."""
    # Drop script/style blocks entirely
    text = re.sub(
        r"<(script|style)[^>]*>.*?</(script|style)>",
        " ", html, flags=re.DOTALL | re.IGNORECASE,
    )
    # Strip all remaining tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Named entities
    for entity, char in {
        "&amp;": "&", "&lt;": "<", "&gt;": ">", "&nbsp;": " ",
        "&quot;": '"', "&#39;": "'", "&apos;": "'",
        "&mdash;": "—", "&ndash;": "–",
        "&ldquo;": "“", "&rdquo;": "”",
        "&lsquo;": "‘", "&rsquo;": "’",
    }.items():
        text = text.replace(entity, char)
    # Numeric entities
    text = re.sub(r"&#(\d+);",    lambda m: chr(int(m.group(1))),     text)
    text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@dataclass
class EarningsData:
    symbol: str
    press_release_text: Optional[str] = None
    press_release_url: Optional[str] = None


class EDGARProvider:

    def get_earnings_press_release(self, symbol: str) -> EarningsData:
        """
        Fetch the most recent earnings press release for symbol.
        Returns EarningsData with press_release_text=None on any failure — never raises.
        """
        try:
            cik = _get_cik(symbol)
            if not cik:
                print(f"  [edgar] {symbol}: no CIK found")
                return EarningsData(symbol=symbol)

            accession = _get_recent_8k_accession(cik)
            if not accession:
                print(f"  [edgar] {symbol}: no earnings 8-K (Item 2.02) found")
                return EarningsData(symbol=symbol)

            acc_nodash = accession.replace("-", "")
            index_url = (
                f"{_SEC_BASE}/Archives/edgar/data/{cik}/{acc_nodash}/{accession}-index.htm"
            )

            index_r = _get(index_url, accept="text/html")
            if index_r is None:
                return EarningsData(symbol=symbol)

            doc_url = _find_ex991_url(index_r.text)
            if not doc_url:
                print(f"  [edgar] {symbol}: no EX-99.1 found in filing index")
                return EarningsData(symbol=symbol)

            doc_r = _get(doc_url, accept="text/html")
            if doc_r is None:
                return EarningsData(symbol=symbol)

            text = _strip_html(doc_r.text)

            if len(text) < 100:
                print(f"  [edgar] {symbol}: press release text suspiciously short after stripping")
                return EarningsData(symbol=symbol)

            if len(text) > _MAX_CHARS:
                text = text[:_MAX_CHARS] + "\n[TRUNCATED]"

            print(f"  [edgar] {symbol}: fetched press release ({len(text):,} chars) — {doc_url}")
            return EarningsData(symbol=symbol, press_release_text=text, press_release_url=doc_url)

        except Exception as e:
            print(f"  [edgar] {symbol}: unexpected error — {e}")
            return EarningsData(symbol=symbol)

    def get_next_earnings_date(self, symbol: str) -> Optional[datetime]:
        """
        Return the nearest upcoming earnings date for symbol via yFinance.
        EDGAR submissions only cover past filings, so yFinance is the reliable source here.
        """
        try:
            import yfinance as yf
            dates = yf.Ticker(symbol).earnings_dates
            if dates is None or dates.empty:
                return None
            now = datetime.now(timezone.utc)
            future = dates[dates.index > now]
            if future.empty:
                return None
            # earnings_dates is sorted descending; min() gives the nearest upcoming date
            return future.index.min().to_pydatetime()
        except Exception as e:
            print(f"  [edgar] {symbol}: get_next_earnings_date error — {e}")
            return None
