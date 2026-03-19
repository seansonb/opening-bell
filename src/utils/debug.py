"""
Debug utilities for Opening Bell.

Usage:
    from utils.debug import set_debug, is_debug, debug_log
"""

import os
from datetime import date

DEBUG = False


def set_debug(enabled: bool) -> None:
    global DEBUG
    DEBUG = enabled


def is_debug() -> bool:
    return DEBUG


def _log_path() -> str:
    logs_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    return os.path.join(logs_dir, f"debug_{date.today().isoformat()}.log")


def debug_log(section: str, content: str) -> None:
    """Print and log a labelled debug section. No-op when debug mode is off."""
    if not DEBUG:
        return

    separator = "=" * 70
    output = f"\n{separator}\n[DEBUG] {section}\n{separator}\n{content}\n"

    print(output)

    try:
        with open(_log_path(), 'a', encoding='utf-8') as f:
            f.write(output)
    except Exception as e:
        print(f"[DEBUG] Warning: could not write to log file: {e}")
