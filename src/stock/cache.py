"""
StockCache — shared yFinance data cache.

Populated by fetch_data.py so that downstream consumers (e.g. thesis_agent.py)
can read ticker data without making duplicate API calls.
"""


class StockCache:
    def __init__(self):
        self._data: dict[str, dict] = {}

    def store(self, symbol: str, info: dict, news: list, history) -> None:
        """Store info, news, and history for a symbol."""
        self._data[symbol.upper()] = {
            'info': info or {},
            'news': news or [],
            'history': history,
        }

    def get(self, symbol: str) -> dict | None:
        """Return the full cached dict for a symbol, or None if not cached."""
        return self._data.get(symbol.upper())

    def get_info(self, symbol: str) -> dict | None:
        """Return just the info dict for a symbol, or None if not cached."""
        entry = self._data.get(symbol.upper())
        return entry['info'] if entry is not None else None

    def clear(self) -> None:
        """Wipe the entire cache."""
        self._data.clear()

    def __contains__(self, symbol: str) -> bool:
        return symbol.upper() in self._data


# Module-level singleton — import this directly
stock_cache = StockCache()
