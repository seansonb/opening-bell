"""
Thesis Manager — read/validate/append thesis files.
Write operations are restricted to appending dated entries to the Thesis Log section only.
"""

import os
import glob
import yaml
from datetime import date

THESES_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'theses')

REQUIRED_FIELDS = ['ticker', 'status', 'sector_theses', 'macro_theses']
VALID_STATUSES = {'holding', 'watchlist', 'candidate'}

LOG_SECTION_HEADER = '## Thesis Log'


def _thesis_path(ticker: str, theses_dir: str | None = None) -> str:
    return os.path.join(theses_dir or THESES_DIR, f"{ticker.upper()}.md")


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Split YAML frontmatter from body. Returns (frontmatter_dict, body_text)."""
    if not content.startswith('---'):
        raise ValueError("Thesis file missing YAML frontmatter (expected '---' at start)")
    parts = content.split('---', 2)
    if len(parts) < 3:
        raise ValueError("Thesis file has malformed frontmatter (missing closing '---')")
    frontmatter = yaml.safe_load(parts[1])
    body = parts[2].lstrip('\n')
    return frontmatter, body


def validate_thesis(ticker: str, theses_dir: str | None = None) -> None:
    """
    Validate that a thesis file has all required frontmatter fields with valid values.
    Raises ValueError with a descriptive message if validation fails.
    """
    path = _thesis_path(ticker, theses_dir)
    if not os.path.exists(path):
        raise FileNotFoundError(f"No thesis file found for {ticker} at {path}")

    with open(path, 'r') as f:
        content = f.read()

    frontmatter, _ = _parse_frontmatter(content)

    if not isinstance(frontmatter, dict):
        raise ValueError(f"{ticker}: frontmatter parsed as empty or non-dict")

    for field in REQUIRED_FIELDS:
        if field not in frontmatter:
            raise ValueError(f"{ticker}: missing required frontmatter field '{field}'")

    status = frontmatter.get('status')
    if status not in VALID_STATUSES:
        raise ValueError(
            f"{ticker}: invalid status '{status}'. Must be one of: {sorted(VALID_STATUSES)}"
        )

    for list_field in ('sector_theses', 'macro_theses'):
        if not isinstance(frontmatter[list_field], list):
            raise ValueError(f"{ticker}: '{list_field}' must be a list")


def load_thesis(ticker: str, theses_dir: str | None = None) -> dict:
    """
    Load a thesis file and return a structured dict with frontmatter and raw body text.
    Validates frontmatter schema before returning.
    """
    validate_thesis(ticker, theses_dir)
    path = _thesis_path(ticker, theses_dir)

    with open(path, 'r') as f:
        content = f.read()

    frontmatter, body = _parse_frontmatter(content)
    return {'frontmatter': frontmatter, 'body': body}


def get_all_tickers() -> list[str]:
    """
    Scan the theses/ directory and return a list of tickers with thesis files.
    Excludes _template.md and any file not matching the TICKER.md pattern.
    """
    pattern = os.path.join(THESES_DIR, '*.md')
    tickers = []
    for path in glob.glob(pattern):
        filename = os.path.basename(path)
        if filename.startswith('_'):
            continue
        ticker = os.path.splitext(filename)[0].upper()
        tickers.append(ticker)
    return sorted(tickers)


def append_to_log(ticker: str, entry: str) -> None:
    """
    Append a dated entry to the Thesis Log section of a thesis file.
    This is the ONLY write operation. Never modifies content above the log section.
    Validates frontmatter schema before writing.
    """
    validate_thesis(ticker)
    path = _thesis_path(ticker)

    with open(path, 'r') as f:
        content = f.read()

    if LOG_SECTION_HEADER not in content:
        raise ValueError(
            f"{ticker}: thesis file is missing the '{LOG_SECTION_HEADER}' section"
        )

    today = date.today().isoformat()
    dated_entry = f"\n### {today}\n{entry.strip()}\n"

    # Insert after the log section header line
    log_index = content.index(LOG_SECTION_HEADER) + len(LOG_SECTION_HEADER)
    updated = content[:log_index] + dated_entry + content[log_index:]

    with open(path, 'w') as f:
        f.write(updated)
