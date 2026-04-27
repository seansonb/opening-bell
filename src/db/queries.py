import uuid
from dataclasses import dataclass
from datetime import datetime

from db.database import get_db


@dataclass
class User:
    user_id: str
    email: str
    first_name: str
    last_name: str

    @property
    def id(self) -> str:
        return self.user_id

    @property
    def name(self) -> str:
        return self.first_name


@dataclass
class Thesis:
    thesis_id: str
    user_id: str
    symbol: str
    status: str
    sector_theses: list[str]
    macro_theses: list[str]
    body: str
    thesis_log: str

    @property
    def id(self) -> str:
        return self.thesis_id


def get_all_users() -> list[User]:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id, email, first_name, last_name FROM users ORDER BY created_at"
                )
                rows = cur.fetchall()
        return [User(user_id=str(r[0]), email=r[1], first_name=r[2], last_name=r[3]) for r in rows]
    except Exception as e:
        print(f"  [db] get_all_users error: {e}")
        return []


def get_user_by_email(email: str) -> User | None:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id, email, first_name, last_name FROM users WHERE email = %s",
                    (email,)
                )
                row = cur.fetchone()
        if row:
            return User(user_id=str(row[0]), email=row[1], first_name=row[2], last_name=row[3])
        return None
    except Exception as e:
        print(f"  [db] get_user_by_email error: {e}")
        return None


def get_watchlist(user_id: str) -> list[str]:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT symbol FROM watchlist WHERE user_id = %s ORDER BY symbol",
                    (uuid.UUID(user_id),)
                )
                rows = cur.fetchall()
        return [r[0] for r in rows]
    except Exception as e:
        print(f"  [db] get_watchlist error: {e}")
        return []


def get_thesis(user_id: str, symbol: str) -> Thesis | None:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT thesis_id, user_id, symbol, status, sector_theses, macro_theses, body, thesis_log
                       FROM theses WHERE user_id = %s AND symbol = %s""",
                    (uuid.UUID(user_id), symbol.upper())
                )
                row = cur.fetchone()
        if row:
            return Thesis(
                thesis_id=str(row[0]),
                user_id=str(row[1]),
                symbol=row[2],
                status=row[3],
                sector_theses=list(row[4]) if row[4] else [],
                macro_theses=list(row[5]) if row[5] else [],
                body=row[6] or '',
                thesis_log=row[7] or '',
            )
        return None
    except Exception as e:
        print(f"  [db] get_thesis error: {e}")
        return None


def get_all_theses_for_user(user_id: str) -> list[Thesis]:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT thesis_id, user_id, symbol, status, sector_theses, macro_theses, body, thesis_log
                       FROM theses WHERE user_id = %s ORDER BY symbol""",
                    (uuid.UUID(user_id),)
                )
                rows = cur.fetchall()
        return [
            Thesis(
                thesis_id=str(r[0]), user_id=str(r[1]), symbol=r[2],
                status=r[3],
                sector_theses=list(r[4]) if r[4] else [],
                macro_theses=list(r[5]) if r[5] else [],
                body=r[6] or '', thesis_log=r[7] or '',
            )
            for r in rows
        ]
    except Exception as e:
        print(f"  [db] get_all_theses_for_user error: {e}")
        return []


def append_to_thesis_log(thesis_id: str, entry: str) -> None:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE theses
                       SET thesis_log = thesis_log || %s, updated_at = NOW()
                       WHERE thesis_id = %s""",
                    (entry, uuid.UUID(thesis_id))
                )
    except Exception as e:
        print(f"  [db] append_to_thesis_log error: {e}")


def save_verdict(thesis_id: str, verdict: str, reasoning: str) -> str | None:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO thesis_verdicts (thesis_id, verdict, reasoning)
                       VALUES (%s, %s, %s) RETURNING verdict_id""",
                    (uuid.UUID(thesis_id), verdict, reasoning)
                )
                row = cur.fetchone()
        return str(row[0]) if row else None
    except Exception as e:
        print(f"  [db] save_verdict error: {e}")
        return None


def get_recent_articles(symbol: str, since: datetime) -> list[dict]:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT title, url, publisher, summary, published_at
                       FROM news_articles
                       WHERE symbol = %s AND published_at >= %s
                       ORDER BY published_at DESC""",
                    (symbol.upper(), since)
                )
                rows = cur.fetchall()
        return [
            {
                'title': r[0],
                'url': r[1],
                'publisher': r[2],
                'summary': r[3] or '',
                'published_at': r[4],
            }
            for r in rows
        ]
    except Exception as e:
        print(f"  [db] get_recent_articles error: {e}")
        return []


def save_articles(articles: list[dict], symbol: str) -> None:
    if not articles:
        return
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                candidate_urls = [a.get('link', '') for a in articles if a.get('link')]
                if candidate_urls:
                    cur.execute(
                        "SELECT url FROM news_articles WHERE url = ANY(%s)",
                        (candidate_urls,)
                    )
                    existing_urls = {r[0] for r in cur.fetchall()}
                else:
                    existing_urls = set()

                for a in articles:
                    url = a.get('link', '')
                    if not url or url in existing_urls:
                        continue
                    published_at = None
                    raw_date = a.get('published', '')
                    if raw_date:
                        try:
                            published_at = datetime.strptime(raw_date, '%Y-%m-%d %H:%M')
                        except ValueError:
                            pass
                    cur.execute(
                        """INSERT INTO news_articles (symbol, title, url, publisher, summary, published_at)
                           VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT (url) DO NOTHING""",
                        (symbol.upper(), a.get('title', ''), url,
                         a.get('publisher', ''), a.get('summary', ''), published_at)
                    )
    except Exception as e:
        print(f"  [db] save_articles error: {e}")
