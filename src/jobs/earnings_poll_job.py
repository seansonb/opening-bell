"""
EarningsPollJob — runs hourly to fire EarningsReportJob for any symbols
whose earnings_date is today and whose press release is now available on EDGAR.
Past-date pending rows that still have no press release are marked failed.
"""

import logging
from datetime import date

from jobs.base_job import BaseScheduledJob

log = logging.getLogger(__name__)


def trigger() -> None:
    """Top-level callable registered with APScheduler as the hourly cron."""
    EarningsPollJob(job_id='earnings_poll_hourly').execute()


class EarningsPollJob(BaseScheduledJob):

    def run(self) -> str:
        from data.edgar_provider import EDGARProvider
        from db.queries import (
            get_pending_earnings_on_or_before_today,
            update_scheduled_earnings_status,
        )
        from jobs.earnings_report_job import EarningsReportJob

        records = get_pending_earnings_on_or_before_today()
        if not records:
            log.info('[poll] no pending earnings today or earlier')
            return 'nothing pending'

        edgar = EDGARProvider()
        today = date.today()
        fired = skipped = failed = 0

        for record in records:
            log.info(f'[poll] checking {record.symbol} (earnings_date={record.earnings_date.date()})')
            edgar_data = edgar.get_earnings_press_release(record.symbol)

            if not edgar_data.press_release_text:
                if record.earnings_date.date() < today:
                    log.info(f'[poll] {record.symbol}: past date, still no press release — marking failed')
                    update_scheduled_earnings_status(
                        record.id, 'failed', 'No press release found after earnings date'
                    )
                    failed += 1
                else:
                    log.info(f'[poll] {record.symbol}: press release not available yet — retry next hour')
                    skipped += 1
                continue

            log.info(f'[poll] {record.symbol}: press release available — firing report')
            try:
                EarningsReportJob(job_id=record.id, symbol=record.symbol).execute()
                fired += 1
            except Exception as e:
                log.error(f'[poll] {record.symbol}: report job failed — {e}')

        summary = f'fired={fired}, retrying={skipped}, failed={failed}'
        log.info(f'[poll] done: {summary}')
        return summary
