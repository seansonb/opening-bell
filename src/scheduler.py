"""
Opening Bell Scheduler — APScheduler process hosted on Railway.
Manages dynamic earnings notification jobs backed by Neon.
"""

import logging
import os

from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL is not set')

jobstores = {
    'default': SQLAlchemyJobStore(url=DATABASE_URL)
}

scheduler = BlockingScheduler(jobstores=jobstores, timezone='America/New_York')


def _register_static_jobs() -> None:
    from jobs.earnings_schedule_job import trigger as earnings_schedule_trigger
    from jobs.earnings_poll_job import trigger as earnings_poll_trigger

    scheduler.add_job(
        earnings_schedule_trigger,
        trigger='cron',
        day_of_week='sun',
        hour=8,
        minute=0,
        id='earnings_schedule_weekly',
        replace_existing=True,
    )
    log.info('Registered weekly earnings schedule job (Sun 08:00 UTC)')

    scheduler.add_job(
        earnings_poll_trigger,
        trigger='cron',
        minute=0,
        id='earnings_poll_hourly',
        replace_existing=True,
    )
    log.info('Registered hourly earnings poll job')


if __name__ == '__main__':
    log.info('Starting Opening Bell scheduler...')
    _register_static_jobs()
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info('Scheduler stopped.')
