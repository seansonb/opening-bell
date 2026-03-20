"""
News injection utilities for thesis agent testing.
Loads fake articles from data/test/injected_news.json to replace real yFinance
news in the thesis prompt — without touching the digest summarization path.
"""

import json
import os

VALID_SCENARIOS = ('confirms', 'weakens', 'monitor')


def load_injected_news(path: str = 'data/test/injected_news.json') -> dict:
    """
    Load and return injected news fixtures keyed by symbol.
    Raises FileNotFoundError with a clear message if the file doesn't exist.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"[--inject-news] Injected news file not found: {path}\n"
            f"Create it before running with --inject-news."
        )
    with open(path, 'r') as f:
        return json.load(f)


def validate_injected_news(symbols: list[str], injected: dict) -> None:
    """
    Verify every symbol has an entry with all three scenario keys
    (confirms, weakens, monitor), each containing signal and noise keys.
    Raises SystemExit with a clear message if anything is missing.
    """
    injected_upper = {k.upper(): v for k, v in injected.items()}
    missing_symbols = [s for s in symbols if s.upper() not in injected_upper]
    if missing_symbols:
        print(f"[--inject-news] Aborting: missing test articles for: {', '.join(missing_symbols)}")
        print("Add these symbols to data/test/injected_news.json before running with --inject-news")
        raise SystemExit(1)

    for symbol in symbols:
        entry = injected_upper[symbol.upper()]
        for scenario in VALID_SCENARIOS:
            if scenario not in entry:
                print(f"[--inject-news] Aborting: {symbol} is missing scenario '{scenario}'")
                raise SystemExit(1)
            for key in ('signal', 'noise'):
                if key not in entry[scenario]:
                    print(f"[--inject-news] Aborting: {symbol}.{scenario} is missing '{key}' key")
                    raise SystemExit(1)


def get_injected_articles(symbol: str, injected: dict, scenario: str = 'confirms') -> list[dict]:
    """
    Return signal + noise articles for the given symbol and scenario as a flat list.
    Raises SystemExit with a clear message if the scenario key is not found.
    """
    injected_upper = {k.upper(): v for k, v in injected.items()}
    entry = injected_upper.get(symbol.upper(), {})

    if scenario not in entry:
        print(f"[--inject-news] Aborting: no '{scenario}' scenario for {symbol}")
        raise SystemExit(1)

    scenario_data = entry[scenario]
    return scenario_data.get('signal', []) + scenario_data.get('noise', [])
