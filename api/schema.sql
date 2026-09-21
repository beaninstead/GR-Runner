-- Future Run daily leaderboard (Neon Postgres via Vercel Marketplace)
-- Day buckets: UTC calendar date (YYYY-MM-DD). Applied automatically on first API hit.

CREATE TABLE IF NOT EXISTS daily_scores (
  id BIGSERIAL PRIMARY KEY,
  day_key CHAR(10) NOT NULL,
  player_id UUID NOT NULL,
  nickname VARCHAR(16) NOT NULL,
  nickname_norm VARCHAR(16) NOT NULL,
  score INT NOT NULL CHECK (score >= 0 AND score <= 10000000),
  smart INT NOT NULL CHECK (smart >= 0 AND smart <= 10000),
  coins INT,
  lives INT,
  client_ts BIGINT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (day_key, nickname_norm),
  UNIQUE (day_key, player_id)
);

CREATE INDEX IF NOT EXISTS idx_daily_scores_rank
  ON daily_scores (day_key, score DESC, smart DESC);

CREATE TABLE IF NOT EXISTS score_rate_limits (
  player_id UUID NOT NULL,
  day_key CHAR(10) NOT NULL,
  hits INT NOT NULL DEFAULT 0,
  window_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (player_id, day_key)
);
