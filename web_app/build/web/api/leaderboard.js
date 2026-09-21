/**
 * Daily live leaderboard API (UTC day buckets).
 *
 * GET  /api/leaderboard?player_id=<uuid>[&day=YYYY-MM-DD]
 *   → { day_key, timezone: "UTC", top: [...], you: {...}|null }
 *
 * POST /api/leaderboard
 *   body: { player_id, nickname, score, smart, coins?, lives?, client_ts? }
 *   → upserts best score for (day_key, player_id); nickname unique per day
 *   → same shape as GET
 *
 * Anti-abuse (light v1): validate types/ranges, nickname rules, rate limit
 * submissions per player/day, upsert only if score/smart improves.
 * Full anti-cheat requires real login later — clients can still lie about scores.
 */

import { ensureSchema, getSql, utcDayKey } from "./_lib/db.js";
import { isUuid, validateSubmitBody } from "./_lib/validate.js";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Cache-Control": "no-store",
};

const MAX_SUBMITS_PER_DAY = 30;

function json(status, payload) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json", ...CORS },
  });
}

export function OPTIONS() {
  return new Response(null, { status: 204, headers: CORS });
}

function rowToEntry(row, rank) {
  return {
    rank,
    player_id: row.player_id,
    nickname: row.nickname,
    score: row.score,
    smart: row.smart,
    coins: row.coins,
    lives: row.lives,
  };
}

async function buildBoard(sql, dayKey, playerId) {
  const topRows = await sql`
    SELECT player_id, nickname, score, smart, coins, lives
    FROM daily_scores
    WHERE day_key = ${dayKey}
    ORDER BY score DESC, smart DESC, updated_at ASC
    LIMIT 10
  `;
  const top = topRows.map((r, i) => rowToEntry(r, i + 1));

  let you = null;
  if (playerId) {
    const mine = await sql`
      SELECT player_id, nickname, score, smart, coins, lives
      FROM daily_scores
      WHERE day_key = ${dayKey} AND player_id = ${playerId}
      LIMIT 1
    `;
    if (mine.length) {
      const row = mine[0];
      const ahead = await sql`
        SELECT COUNT(*)::int AS n
        FROM daily_scores
        WHERE day_key = ${dayKey}
          AND (
            score > ${row.score}
            OR (score = ${row.score} AND smart > ${row.smart})
            OR (
              score = ${row.score}
              AND smart = ${row.smart}
              AND player_id <> ${playerId}
              AND updated_at < (
                SELECT updated_at FROM daily_scores
                WHERE day_key = ${dayKey} AND player_id = ${playerId}
              )
            )
          )
      `;
      you = rowToEntry(row, (ahead[0]?.n ?? 0) + 1);
    }
  }

  return {
    day_key: dayKey,
    timezone: "UTC",
    sort: ["score_desc", "smart_desc"],
    top,
    you,
  };
}

async function checkRateLimit(sql, playerId, dayKey) {
  const existing = await sql`
    SELECT hits, window_start FROM score_rate_limits
    WHERE player_id = ${playerId} AND day_key = ${dayKey}
    LIMIT 1
  `;
  if (!existing.length) {
    await sql`
      INSERT INTO score_rate_limits (player_id, day_key, hits, window_start)
      VALUES (${playerId}, ${dayKey}, 1, NOW())
    `;
    return { ok: true };
  }
  const hits = existing[0].hits;
  if (hits >= MAX_SUBMITS_PER_DAY) {
    return { ok: false, error: "Rate limit: too many submits today" };
  }
  await sql`
    UPDATE score_rate_limits
    SET hits = hits + 1
    WHERE player_id = ${playerId} AND day_key = ${dayKey}
  `;
  return { ok: true };
}

export async function GET(request) {
  try {
    await ensureSchema();
    const sql = getSql();
    const url = new URL(request.url);
    const dayParam = url.searchParams.get("day");
    const dayKey =
      dayParam && /^\d{4}-\d{2}-\d{2}$/.test(dayParam)
        ? dayParam
        : utcDayKey();
    const playerId = url.searchParams.get("player_id");
    if (playerId && !isUuid(playerId)) {
      return json(400, { error: "player_id must be a UUID" });
    }
    const board = await buildBoard(
      sql,
      dayKey,
      playerId ? playerId.toLowerCase() : null
    );
    return json(200, board);
  } catch (err) {
    console.error("leaderboard GET", err);
    return json(500, { error: "Server error" });
  }
}

export async function POST(request) {
  try {
    await ensureSchema();
    const sql = getSql();
    let body;
    try {
      body = await request.json();
    } catch {
      return json(400, { error: "Invalid JSON" });
    }
    const parsed = validateSubmitBody(body);
    if (parsed.error) return json(400, { error: parsed.error });
    const v = parsed.value;
    const dayKey = utcDayKey();

    const rl = await checkRateLimit(sql, v.player_id, dayKey);
    if (!rl.ok) return json(429, { error: rl.error });

    // Nickname claimed by a different player today?
    const nickTaken = await sql`
      SELECT player_id FROM daily_scores
      WHERE day_key = ${dayKey} AND nickname_norm = ${v.nickname_norm}
      LIMIT 1
    `;
    if (nickTaken.length && nickTaken[0].player_id !== v.player_id) {
      return json(409, { error: "Nickname already taken today" });
    }

    const existing = await sql`
      SELECT score, smart FROM daily_scores
      WHERE day_key = ${dayKey} AND player_id = ${v.player_id}
      LIMIT 1
    `;

    if (!existing.length) {
      await sql`
        INSERT INTO daily_scores (
          day_key, player_id, nickname, nickname_norm,
          score, smart, coins, lives, client_ts
        ) VALUES (
          ${dayKey}, ${v.player_id}, ${v.nickname}, ${v.nickname_norm},
          ${v.score}, ${v.smart}, ${v.coins}, ${v.lives}, ${v.client_ts}
        )
      `;
    } else {
      const prev = existing[0];
      const better =
        v.score > prev.score ||
        (v.score === prev.score && v.smart > prev.smart);
      if (better) {
        await sql`
          UPDATE daily_scores SET
            nickname = ${v.nickname},
            nickname_norm = ${v.nickname_norm},
            score = ${v.score},
            smart = ${v.smart},
            coins = ${v.coins},
            lives = ${v.lives},
            client_ts = ${v.client_ts},
            updated_at = NOW()
          WHERE day_key = ${dayKey} AND player_id = ${v.player_id}
        `;
      } else {
        // Still allow nickname refresh on non-improving submit
        await sql`
          UPDATE daily_scores SET
            nickname = ${v.nickname},
            nickname_norm = ${v.nickname_norm},
            updated_at = updated_at
          WHERE day_key = ${dayKey} AND player_id = ${v.player_id}
        `;
      }
    }

    const board = await buildBoard(sql, dayKey, v.player_id);
    return json(200, { ...board, saved: true });
  } catch (err) {
    console.error("leaderboard POST", err);
    // Unique violation race
    if (String(err?.message || err).includes("unique") || err?.code === "23505") {
      return json(409, { error: "Nickname already taken today" });
    }
    return json(500, { error: "Server error" });
  }
}
