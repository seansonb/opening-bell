"""
EarningsReportJob — triggered at 4:00 PM ET on a company's earnings date.
Fetches EDGAR press release, runs LLM extraction, renders the email template,
and sends to all users watching the symbol.
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jobs.base_job import BaseScheduledJob
from db.queries import update_scheduled_earnings_status

log = logging.getLogger(__name__)


def _send_html_email(html: str, subject: str, recipient: str) -> None:
    sender = os.getenv('SENDER_EMAIL')
    password = os.getenv('SENDER_PASSWORD')
    if not sender or not password:
        raise ValueError("SENDER_EMAIL and SENDER_PASSWORD must be set")

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender, password)
        server.send_message(msg)


def trigger(symbol: str, record_id: str) -> None:
    """Top-level callable stored by APScheduler. record_id = scheduled_earnings.id."""
    EarningsReportJob(job_id=record_id, symbol=symbol).execute()


class EarningsReportJob(BaseScheduledJob):

    def __init__(self, job_id: str, symbol: str):
        super().__init__(job_id)
        self.symbol = symbol
        self.record_id = job_id  # job_id IS the scheduled_earnings UUID

    def _before_run(self):
        update_scheduled_earnings_status(self.record_id, 'running')

    def _after_run(self, result: str):
        update_scheduled_earnings_status(self.record_id, 'completed', result_summary=result)

    def _on_failure(self, error: Exception):
        update_scheduled_earnings_status(self.record_id, 'failed', result_summary=str(error))
        log.error(f"[earnings_report] {self.symbol} failed: {error}")

    def run(self) -> str:
        from datetime import datetime, timezone, timedelta
        from data.edgar_provider import EDGARProvider
        from db.queries import get_recent_articles, get_users_watching_symbol
        from jobs.earnings_extractor import fetch_yfinance_snapshot, run_llm_extraction
        from jobs.earnings_renderer import render_earnings_report

        log.info(f"[earnings_report] {self.symbol}: starting")
        now = datetime.now(timezone.utc)

        # Fetch data
        edgar_data = EDGARProvider().get_earnings_press_release(self.symbol)
        yf_snapshot = fetch_yfinance_snapshot(self.symbol)
        news = get_recent_articles(self.symbol, since=now - timedelta(hours=48))

        # LLM extraction — only when a press release is available
        # thesis_verdict/commentary are per-user; section is omitted until per-user rendering added
        llm_fields = None
        if edgar_data.press_release_text:
            llm_fields = run_llm_extraction(edgar_data, yf_snapshot, thesis=None, news=news)
        else:
            log.info(f"[earnings_report] {self.symbol}: no press release — skipping LLM")

        # Render once — same HTML for all watchers (thesis section omitted when thesis=None)
        html = render_earnings_report(self.symbol, now, edgar_data, yf_snapshot, llm_fields, news)
        log.info(f"[earnings_report] {self.symbol}: rendered {len(html):,} chars")

        # Send to all watchers
        users = get_users_watching_symbol(self.symbol)
        if not users:
            log.info(f"[earnings_report] {self.symbol}: no watchers, skipping send")

        month = now.strftime('%B')
        subject = f"{self.symbol} Earnings — {month} {now.day}, {now.year}"
        sent = 0
        for user in users:
            try:
                _send_html_email(html, subject, user.email)
                log.info(f"[earnings_report] {self.symbol}: sent to {user.email}")
                sent += 1
            except Exception as e:
                log.error(f"[earnings_report] {self.symbol}: send failed for {user.email} — {e}")

        has_pr = edgar_data.press_release_text is not None
        summary = (
            f"{self.symbol}: press_release={has_pr}, "
            f"llm={bool(llm_fields)}, "
            f"sent={sent}/{len(users)}"
        )
        log.info(f"[earnings_report] {summary}")
        return summary
