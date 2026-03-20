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
            theses_dir = user_data.get('theses_dir')
            user = session.query(User).filter_by(email=email).first()
            if not user:
                user = User(name=user_data['name'], email=email, theses_dir=theses_dir)
                session.add(user)
                session.flush()
                print(f"  [db] Seeded user: {user.name} ({email})")
            elif user.theses_dir != theses_dir:
                user.theses_dir = theses_dir

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
    For each user, scan their theses_dir (or the global theses/ fallback) for .md files.
    Upsert a Thesis row for each file whose stem matches a symbol in the user's watchlist.
    """
    global_theses_dir = os.path.join(_PROJECT_ROOT, 'theses')

    with get_session() as session:
        users = session.query(User).all()

        for user in users:
            scan_dir = os.path.join(_PROJECT_ROOT, user.theses_dir) if user.theses_dir else global_theses_dir
            pattern = os.path.join(scan_dir, '*.md')

            user_symbols = {w.symbol for w in user.watchlist}

            for path in glob.glob(pattern):
                filename = os.path.basename(path)
                if filename.startswith('_'):
                    continue

                symbol = os.path.splitext(filename)[0].upper()
                if symbol not in user_symbols:
                    continue

                try:
                    with open(path, 'r') as f:
                        content = f.read()
                except Exception as e:
                    print(f"  [db] Could not read thesis file {path}: {e}")
                    continue

                existing = session.query(Thesis).filter_by(
                    user_id=user.id, symbol=symbol
                ).first()
                if existing:
                    if existing.content != content:
                        existing.content = content
                        print(f"  [db] Updated thesis: {symbol} for user_id={user.id}")
                else:
                    session.add(Thesis(user_id=user.id, symbol=symbol, content=content))
                    print(f"  [db] Seeded thesis: {symbol} for user_id={user.id}")

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
