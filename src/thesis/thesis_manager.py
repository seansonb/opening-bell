"""
Thesis Manager — DB-backed thesis read/write operations.
"""

from datetime import date

from db.queries import get_thesis, get_all_theses_for_user, append_to_thesis_log


def load_thesis(ticker: str, user_id: str) -> dict:
    """
    Load a thesis from the DB. Returns a dict with 'frontmatter' and 'body' keys.
    Raises ValueError if no thesis exists for this user/ticker.
    """
    thesis = get_thesis(user_id, ticker.upper())
    if thesis is None:
        raise ValueError(f"No thesis found for {ticker} (user_id={user_id})")
    return {
        'frontmatter': {
            'ticker': thesis.symbol,
            'status': thesis.status,
            'sector_theses': thesis.sector_theses,
            'macro_theses': thesis.macro_theses,
        },
        'body': thesis.body,
    }


def get_all_tickers(user_id: str) -> list[str]:
    """Return a sorted list of tickers with theses for a given user."""
    theses = get_all_theses_for_user(user_id)
    return sorted(t.symbol for t in theses)


def append_to_log(ticker: str, entry: str, user_id: str) -> None:
    """Append a dated entry to the thesis_log for the given ticker and user."""
    thesis = get_thesis(user_id, ticker.upper())
    if thesis is None:
        raise ValueError(f"No thesis found for {ticker} (user_id={user_id})")
    today = date.today().isoformat()
    dated_entry = f"\n### {today}\n{entry.strip()}\n"
    append_to_thesis_log(thesis.thesis_id, dated_entry)
