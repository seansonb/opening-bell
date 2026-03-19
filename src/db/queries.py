"""
Database query helpers for Opening Bell.
All functions catch DB errors, log them, and return safe empty values.
"""

from datetime import datetime

from db.database import get_session
from db.models import User, Watchlist, Thesis, ThesisVerdict, NewsArticle


def get_all_users() -> list[User]:
    try:
        with get_session() as session:
            users = session.query(User).all()
            session.expunge_all()
            return users
    except Exception as e:
        print(f"  [db] get_all_users error: {e}")
        return []


def get_user_by_email(email: str) -> User | None:
    try:
        with get_session() as session:
            user = session.query(User).filter_by(email=email).first()
            if user:
                session.expunge(user)
            return user
    except Exception as e:
        print(f"  [db] get_user_by_email error: {e}")
        return None


def get_watchlist(user_id: int) -> list[str]:
    try:
        with get_session() as session:
            rows = session.query(Watchlist).filter_by(user_id=user_id).all()
            return [r.symbol for r in rows]
    except Exception as e:
        print(f"  [db] get_watchlist error: {e}")
        return []


def get_thesis(user_id: int, symbol: str) -> Thesis | None:
    try:
        with get_session() as session:
            thesis = session.query(Thesis).filter_by(
                user_id=user_id, symbol=symbol.upper()
            ).first()
            if thesis:
                session.expunge(thesis)
            return thesis
    except Exception as e:
        print(f"  [db] get_thesis error: {e}")
        return None


def get_all_theses_for_user(user_id: int) -> list[Thesis]:
    try:
        with get_session() as session:
            theses = session.query(Thesis).filter_by(user_id=user_id).all()
            session.expunge_all()
            return theses
    except Exception as e:
        print(f"  [db] get_all_theses_for_user error: {e}")
        return []


def save_verdict(thesis_id: int, verdict: str, reasoning: str) -> ThesisVerdict | None:
    try:
        with get_session() as session:
            tv = ThesisVerdict(
                thesis_id=thesis_id,
                verdict=verdict,
                reasoning=reasoning,
            )
            session.add(tv)
            session.commit()
            session.refresh(tv)
            session.expunge(tv)
            return tv
    except Exception as e:
        print(f"  [db] save_verdict error: {e}")
        return None


def get_recent_articles(symbol: str, since: datetime) -> list[NewsArticle]:
    try:
        with get_session() as session:
            articles = (
                session.query(NewsArticle)
                .filter(
                    NewsArticle.symbol == symbol.upper(),
                    NewsArticle.published_at >= since,
                )
                .order_by(NewsArticle.published_at.desc())
                .all()
            )
            session.expunge_all()
            return articles
    except Exception as e:
        print(f"  [db] get_recent_articles error: {e}")
        return []


def save_articles(articles: list[dict], symbol: str) -> None:
    """Bulk insert articles, skipping duplicates by URL."""
    if not articles:
        return
    try:
        with get_session() as session:
            existing_urls = {
                row[0] for row in session.query(NewsArticle.url).filter(
                    NewsArticle.symbol == symbol.upper()
                ).all()
            }
            new_rows = []
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
                new_rows.append(NewsArticle(
                    symbol=symbol.upper(),
                    title=a.get('title', ''),
                    url=url,
                    publisher=a.get('publisher', ''),
                    summary=a.get('summary', ''),
                    published_at=published_at,
                ))
            if new_rows:
                session.add_all(new_rows)
                session.commit()
    except Exception as e:
        print(f"  [db] save_articles error: {e}")
