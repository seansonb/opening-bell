"""
EarningsScheduleJob — runs weekly (Sunday 08:00 UTC) to discover upcoming
earnings dates for all watchlist symbols and schedule EarningsReportJob instances.
"""

import logging
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from jobs.base_job import BaseScheduledJob

log = logging.getLogger(__name__)

_EASTERN = ZoneInfo('America/New_York')


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
            update_scheduled_earnings_job_id,
        )
        from data.edgar_provider import EDGARProvider
        from jobs.earnings_report_job import trigger as report_trigger

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

            # Check for an existing pending row for this symbol (any date)
            existing = get_pending_scheduled_earnings_for_symbol(symbol)

            if existing:
                if existing.earnings_date.date() == normalized.date():
                    skipped_count += 1
                    continue
                # Company rescheduled — update the existing row and job
                run_at = _run_at(normalized)
                job_id = _job_id(symbol, normalized)
                _schedule_apscheduler_job(report_trigger, job_id, run_at, symbol, existing.id)
                update_scheduled_earnings_job_id(existing.id, job_id)
                log.info(f"[schedule] {symbol}: rescheduled to {run_at.isoformat()}")
                updated_count += 1
                continue

            # Skip if a completed/failed row already exists for this exact date
            if get_scheduled_earnings(symbol, normalized):
                skipped_count += 1
                continue

            record = create_scheduled_earnings(symbol, normalized)
            if record is None:
                continue

            run_at = _run_at(normalized)
            job_id = _job_id(symbol, normalized)
            _schedule_apscheduler_job(report_trigger, job_id, run_at, symbol, record.id)
            update_scheduled_earnings_job_id(record.id, job_id)
            log.info(f"[schedule] {symbol}: scheduled for {run_at.isoformat()}")
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


def _run_at(earnings_date_utc: datetime) -> datetime:
    """Return 4:00 PM ET on the earnings date."""
    d = earnings_date_utc.astimezone(_EASTERN).date()
    return datetime(d.year, d.month, d.day, 16, 0, 0, tzinfo=_EASTERN)


def _job_id(symbol: str, earnings_date_utc: datetime) -> str:
    return f"earnings_report_{symbol}_{earnings_date_utc.strftime('%Y%m%d')}"


def _schedule_apscheduler_job(
    func, job_id: str, run_at: datetime, symbol: str, record_id: str
) -> None:
    from scheduler import scheduler
    scheduler.add_job(
        func,
        trigger='date',
        run_date=run_at,
        id=job_id,
        kwargs={'symbol': symbol, 'record_id': record_id},
        replace_existing=True,
    )
