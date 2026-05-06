"""
EarningsScheduleJob — runs weekly (Sunday 08:00 UTC) to discover upcoming
earnings dates for all watchlist symbols and create/update scheduled_earnings rows.
The hourly EarningsPollJob is responsible for actually firing reports.
"""

import logging
import time
from datetime import datetime, timezone

from jobs.base_job import BaseScheduledJob

log = logging.getLogger(__name__)


def trigger() -> None:
    """Top-level callable registered with APScheduler as the weekly cron."""
    EarningsScheduleJob(job_id='earnings_schedule_weekly').execute()


class EarningsScheduleJob(BaseScheduledJob):

    def run(self) -> str:
        from db.queries import (
            get_all_watchlist_symbols,
            get_scheduled_earnings,
            get_pending_scheduled_earnings_for_symbol,
            create_scheduled_earnings,
            update_scheduled_earnings_date,
        )
        from data.edgar_provider import EDGARProvider

        edgar = EDGARProvider()
        symbols = get_all_watchlist_symbols()
        new_count = updated_count = skipped_count = 0

        for symbol in symbols:
            time.sleep(0.15)
            next_date = edgar.get_next_earnings_date(symbol)

            if next_date is None:
                log.info(f"[schedule] {symbol}: no upcoming earnings date")
                skipped_count += 1
                continue

            normalized = _normalize(next_date)
            existing = get_pending_scheduled_earnings_for_symbol(symbol)

            if existing:
                if existing.earnings_date.date() == normalized.date():
                    skipped_count += 1
                    continue
                # Company rescheduled — update the date so the poll job picks it up correctly
                update_scheduled_earnings_date(existing.id, normalized)
                log.info(f"[schedule] {symbol}: rescheduled to {normalized.date()}")
                updated_count += 1
                continue

            # Skip if a completed/failed row already exists for this exact date
            if get_scheduled_earnings(symbol, normalized):
                skipped_count += 1
                continue

            record = create_scheduled_earnings(symbol, normalized)
            if record is None:
                continue

            log.info(f"[schedule] {symbol}: registered for {normalized.date()}")
            new_count += 1

        summary = (
            f"Checked {len(symbols)} symbols — "
            f"{new_count} new, {updated_count} rescheduled, {skipped_count} skipped"
        )
        log.info(f"[schedule] done: {summary}")
        return summary


def _normalize(dt: datetime) -> datetime:
    """Normalize an earnings datetime to midnight UTC (stable unique key)."""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
