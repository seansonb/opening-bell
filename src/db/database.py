"""
Database engine, session management, and lifecycle helpers for Opening Bell.

To swap SQLite for Supabase (or any Postgres instance), set DATABASE_URL in .env:
    DATABASE_URL=postgresql://user:pass@host:5432/dbname
No other code changes are needed.
"""

import glob
import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, User, Watchlist, Thesis, NewsArticle

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/opening_bell.db')

# SQLite requires check_same_thread=False; Postgres does not accept it
_connect_args = {'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine)

# Resolve project root (two levels up from src/db/)
_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')


def init_db() -> None:
    """Create all tables if they don't exist, then seed users and theses."""
    Base.metadata.create_all(engine)
    seed_users()


@contextmanager
def get_session():
    """Yield a SQLAlchemy session, always closing in the finally block."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def seed_users() -> None:
    """
    Seed users, watchlists, and theses from JSON + thesis files.
    Idempotent — safe to call on every startup.
    """
    test_mode = os.getenv('TEST_MODE', 'false').lower() == 'true'
    users_file = 'data/users_test.json' if test_mode else 'data/users.json'
    users_path = os.path.join(_PROJECT_ROOT, users_file)

    try:
        with open(users_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"  [db] Users file not found: {users_path}")
        return

    with get_session() as session:
        for user_data in data.get('users', []):
            email = user_data.get('email')
            if not email:
                continue

            # Upsert user
            user = session.query(User).filter_by(email=email).first()
            if not user:
                user = User(name=user_data['name'], email=email)
                session.add(user)
                session.flush()
                print(f"  [db] Seeded user: {user.name} ({email})")

            # Upsert watchlist symbols
            existing_symbols = {w.symbol for w in user.watchlist}
            for symbol in user_data.get('symbols', []):
                if symbol not in existing_symbols:
                    session.add(Watchlist(user_id=user.id, symbol=symbol))

        session.commit()

    # Seed theses — scan theses/ dir and associate with watchlist users
    _seed_theses()


def _seed_theses() -> None:
    """
    Scan theses/*.md and seed Thesis rows for users who have the symbol
    in their watchlist. Always reads from the main theses/ directory.
    """
    theses_dir = os.path.join(_PROJECT_ROOT, 'theses')
    pattern = os.path.join(theses_dir, '*.md')

    with get_session() as session:
        for path in glob.glob(pattern):
            filename = os.path.basename(path)
            if filename.startswith('_'):
                continue

            symbol = os.path.splitext(filename)[0].upper()

            try:
                with open(path, 'r') as f:
                    content = f.read()
            except Exception as e:
                print(f"  [db] Could not read thesis file {path}: {e}")
                continue

            # Find users with this symbol in their watchlist
            watchlist_rows = (
                session.query(Watchlist)
                .filter_by(symbol=symbol)
                .all()
            )

            for wl in watchlist_rows:
                exists = session.query(Thesis).filter_by(
                    user_id=wl.user_id, symbol=symbol
                ).first()
                if not exists:
                    session.add(Thesis(
                        user_id=wl.user_id,
                        symbol=symbol,
                        content=content,
                    ))
                    print(f"  [db] Seeded thesis: {symbol} for user_id={wl.user_id}")

        session.commit()


def purge_old_articles() -> None:
    """Delete NewsArticle rows where published_at is older than 7 days."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    with get_session() as session:
        deleted = (
            session.query(NewsArticle)
            .filter(NewsArticle.published_at < cutoff)
            .delete()
        )
        session.commit()
        if deleted:
            print(f"  [db] Purged {deleted} articles older than 7 days")
