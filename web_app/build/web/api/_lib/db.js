import { neon } from "@neondatabase/serverless";

let _sql = null;
let _schemaReady = false;

/** Lazy Neon client — safe when DATABASE_URL is missing at build time. */
export function getSql() {
  if (_sql) return _sql;
  const url = process.env.DATABASE_URL || process.env.POSTGRES_URL;
  if (!url) {
    throw new Error("DATABASE_URL is not configured");
  }
  _sql = neon(url);
  return _sql;
}

export async function ensureSchema() {
  if (_schemaReady) return;
  const sql = getSql();
  await sql`
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
    )
  `;
  await sql`
    CREATE INDEX IF NOT EXISTS idx_daily_scores_rank
    ON daily_scores (day_key, score DESC, smart DESC)
  `;
  await sql`
    CREATE TABLE IF NOT EXISTS score_rate_limits (
      player_id UUID NOT NULL,
      day_key CHAR(10) NOT NULL,
      hits INT NOT NULL DEFAULT 0,
      window_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (player_id, day_key)
    )
  `;
  _schemaReady = true;
}

/** UTC calendar day key: YYYY-MM-DD */
export function utcDayKey(date = new Date()) {
  return date.toISOString().slice(0, 10);
}
