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

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from db.models import Base, User, Watchlist, Thesis, NewsArticle

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/opening_bell.db')

if DATABASE_URL.startswith('sqlite'):
    # SQLite requires check_same_thread=False for multi-threaded use
    engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
else:
    # NullPool prevents connection leaks in short-lived/serverless jobs (e.g. Neon)
    engine = create_engine(DATABASE_URL, poolclass=NullPool)

SessionLocal = sessionmaker(bind=engine)

# Resolve project root (two levels up from src/db/)
_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')


def init_db() -> None:
    """Create all tables if they don't exist, then seed users from JSON if present."""
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
    users_path = os.path.join(_PROJECT_ROOT, 'data/users.json')

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


def import_theses_from_disk(theses_root: str | None = None) -> None:
    """
    One-time import utility: scan a directory tree for per-user thesis markdown files
    and upsert them into the DB.

    Expected layout:
        <theses_root>/<user_name_or_email>/<SYMBOL>.md

    Call this manually during initial migration or when bulk-importing thesis files.
    It is NOT called on normal startup.
    """
    root = theses_root or os.path.join(_PROJECT_ROOT, 'theses')

    with get_session() as session:
        users = session.query(User).all()
        user_by_name = {u.name.lower(): u for u in users}

        for subdir in glob.glob(os.path.join(root, '*')):
            if not os.path.isdir(subdir):
                continue

            dir_name = os.path.basename(subdir).lower()
            user = user_by_name.get(dir_name)
            if not user:
                print(f"  [db] No user found for theses dir: {dir_name}, skipping")
                continue

            user_symbols = {w.symbol for w in user.watchlist}

            for path in glob.glob(os.path.join(subdir, '*.md')):
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
                        print(f"  [db] Updated thesis: {symbol} for {user.name}")
                else:
                    session.add(Thesis(user_id=user.id, symbol=symbol, content=content))
                    print(f"  [db] Imported thesis: {symbol} for {user.name}")

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
