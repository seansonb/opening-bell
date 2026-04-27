SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email      TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name  TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS watchlist (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    symbol  TEXT NOT NULL,
    UNIQUE(user_id, symbol)
);

CREATE TABLE IF NOT EXISTS theses (
    thesis_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    symbol        TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'watchlist',
    sector_theses TEXT[] DEFAULT '{}',
    macro_theses  TEXT[] DEFAULT '{}',
    body          TEXT NOT NULL DEFAULT '',
    thesis_log    TEXT NOT NULL DEFAULT '',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, symbol)
);

CREATE TABLE IF NOT EXISTS thesis_verdicts (
    verdict_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thesis_id  UUID NOT NULL REFERENCES theses(thesis_id) ON DELETE CASCADE,
    verdict    TEXT NOT NULL,
    reasoning  TEXT,
    run_date   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS news_articles (
    article_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol       TEXT NOT NULL,
    title        TEXT NOT NULL,
    url          TEXT UNIQUE,
    publisher    TEXT,
    summary      TEXT,
    published_at TIMESTAMPTZ,
    fetched_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_news_symbol_published ON news_articles(symbol, published_at);
"""
