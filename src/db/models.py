"""
SQLAlchemy ORM models for Opening Bell.
"""

from datetime import datetime
from sqlalchemy import (
    Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    theses_dir: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    watchlist: Mapped[list['Watchlist']] = relationship(
        'Watchlist', back_populates='user', cascade='all, delete-orphan'
    )
    theses: Mapped[list['Thesis']] = relationship(
        'Thesis', back_populates='user', cascade='all, delete-orphan'
    )


class Watchlist(Base):
    __tablename__ = 'watchlist'
    __table_args__ = (UniqueConstraint('user_id', 'symbol'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False)

    user: Mapped['User'] = relationship('User', back_populates='watchlist')


class Thesis(Base):
    __tablename__ = 'theses'
    __table_args__ = (UniqueConstraint('user_id', 'symbol'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped['User'] = relationship('User', back_populates='theses')
    verdicts: Mapped[list['ThesisVerdict']] = relationship(
        'ThesisVerdict', back_populates='thesis', cascade='all, delete-orphan'
    )


class ThesisVerdict(Base):
    __tablename__ = 'thesis_verdicts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thesis_id: Mapped[int] = mapped_column(Integer, ForeignKey('theses.id', ondelete='CASCADE'), nullable=False)
    verdict: Mapped[str] = mapped_column(String)
    reasoning: Mapped[str] = mapped_column(Text)
    run_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    thesis: Mapped['Thesis'] = relationship('Thesis', back_populates='verdicts')


class NewsArticle(Base):
    __tablename__ = 'news_articles'
    __table_args__ = (
        Index('ix_news_symbol_published', 'symbol', 'published_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, unique=True)
    publisher: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
