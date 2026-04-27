import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from db.models import SCHEMA

load_dotenv()

# Register UUID adapter so uuid.UUID objects are properly serialized and
# UUID columns are returned as uuid.UUID objects.
psycopg2.extras.register_uuid()

DATABASE_URL = os.environ['DATABASE_URL']


@contextmanager
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)


def purge_old_articles() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    deleted = 0
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM news_articles WHERE published_at < %s",
                (cutoff,)
            )
            deleted = cur.rowcount
    if deleted:
        print(f"  [db] Purged {deleted} articles older than 7 days")
