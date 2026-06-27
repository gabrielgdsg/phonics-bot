-- ═══════════════════════════════════════════════════════════════
-- Phonics Bot — Complete Database Schema
-- Run this once on any PostgreSQL instance (Railway or local)
-- Safe to re-run — all statements use IF NOT EXISTS
-- ═══════════════════════════════════════════════════════════════

-- ── Users: config + progress ──────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    chat_id         BIGINT      PRIMARY KEY,
    lang            VARCHAR(2)  NOT NULL DEFAULT 'en',
    daily_tip       BOOLEAN     NOT NULL DEFAULT TRUE,
    daily_activity  BOOLEAN     NOT NULL DEFAULT TRUE,
    activity_lang   VARCHAR(2)  NOT NULL DEFAULT 'en',
    en_lesson       INTEGER     NOT NULL DEFAULT 1,
    pt_lesson       INTEGER     NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Phonics lessons ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lessons (
    id          SERIAL      PRIMARY KEY,
    lang        VARCHAR(2)  NOT NULL,
    num         INTEGER     NOT NULL,
    title       TEXT        NOT NULL,
    words       TEXT[]      NOT NULL,
    sentences   TEXT[]      NOT NULL DEFAULT '{}',
    tips        TEXT        NOT NULL,
    enrichment  TEXT,
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (lang, num)
);

-- ── Children's songs ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS songs (
    id              SERIAL      PRIMARY KEY,
    lang            VARCHAR(2)  NOT NULL,           -- 'pt' or 'en'
    title           TEXT        NOT NULL,
    lyrics          TEXT        NOT NULL,           -- plain lyrics (no chords)
    chords          TEXT,                           -- lyrics with chord names above syllables
    vocabulary_tips TEXT,                           -- Claude-generated word/expression notes
    youtube_url     TEXT,
    age_min         INTEGER     NOT NULL DEFAULT 0, -- minimum age in months
    age_max         INTEGER     NOT NULL DEFAULT 72,-- maximum age in months
    category        VARCHAR(50),                    -- 'classic', 'phonics', 'movement', 'lullaby'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Daily tips pool ───────────────────────────────────────────
-- Pre-generated pool of tips served in rotation
-- tip_date cycles through the pool — no API call needed at send time
CREATE TABLE IF NOT EXISTS daily_tips (
    id          SERIAL      PRIMARY KEY,
    lang        VARCHAR(2)  NOT NULL DEFAULT 'en',
    tip_number  INTEGER     NOT NULL,               -- 1 to N (e.g. 1–365)
    word        TEXT        NOT NULL,               -- the word or expression
    definition  TEXT        NOT NULL,               -- what it means
    example_1   TEXT        NOT NULL,               -- toddler example sentence
    example_2   TEXT        NOT NULL,               -- adult use example sentence
    toddler_tip TEXT        NOT NULL,               -- song/game/routine tip
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (lang, tip_number)
);

-- ── Weekly activity plans ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS weekly_plans (
    id          SERIAL      PRIMARY KEY,
    week_iso    VARCHAR(8)  NOT NULL UNIQUE,        -- e.g. '2025-W03'
    plan_pt     TEXT,
    plan_en     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_lessons_lang_num   ON lessons     (lang, num);
CREATE INDEX IF NOT EXISTS idx_songs_lang         ON songs       (lang);
CREATE INDEX IF NOT EXISTS idx_songs_category     ON songs       (category);
CREATE INDEX IF NOT EXISTS idx_daily_tips_lang_num ON daily_tips (lang, tip_number);
CREATE INDEX IF NOT EXISTS idx_weekly_plans_week  ON weekly_plans (week_iso);
