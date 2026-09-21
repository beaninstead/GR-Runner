# Daily leaderboard (Future Run)

Anonymous nicknames + UTC daily board, backed by **Neon Postgres** from the Vercel Marketplace (`neon-crimson-lantern` on project `future-run`).

## Day bucket

Scores are grouped by **UTC calendar day** (`YYYY-MM-DD` from `Date.toISOString()`). Documented in API responses as `timezone: "UTC"`.

## Endpoints

Same-origin on Vercel (Root Directory remains `web_app/build/web`):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/leaderboard?player_id=<uuid>` | Top 10 for today + optional `you` row/rank |
| `POST` | `/api/leaderboard` | Submit/upsert campaign-end score |
| `OPTIONS` | `/api/leaderboard` | CORS preflight |

### POST body

```json
{
  "player_id": "uuid",
  "nickname": "Ada Runner",
  "score": 1234,
  "smart": 7,
  "coins": 12,
  "lives": 2,
  "client_ts": 1710000000000
}
```

Server stamps `day_key`. Upserts per `(day_key, player_id)` only when the new score is higher (or equal score with higher `smart`). Nicknames are unique per day.

### Light anti-abuse (v1)

- Nickname rules: 3–16 chars, alphanumeric + spaces/underscores, no URLs, basic profanity block
- Integer range checks
- Max ~30 POSTs per `player_id` per UTC day
- **Clients can still forge scores** until real login/anti-cheat

## Env vars (from Marketplace Neon)

Pulled via `vercel env pull` into `web_app/build/web/.env.local` (gitignored):

- `DATABASE_URL` (required by API)
- Also provisioned: `DATABASE_URL_UNPOOLED`, `POSTGRES_*`, `NEON_PROJECT_ID`, …

## Local test

```bash
cd web_app/build/web
npm install
vercel env pull .env.local --yes
npx vercel dev --listen 3000
# Game static + /api/leaderboard on http://127.0.0.1:3000
```

Or point the game at production while serving static only:

```python
# future_run/constants.py
LEADERBOARD_API_URL = "https://future-run.vercel.app"
```

## Game UI flow

1. Beat World 4 → win stats + **SUBMIT SCORE** + GradRight CTA  
2. Enter anonymous nickname → **POST SCORE**  
3. Daily top 10 + **you** (even if outside top 10)  
4. CTA still available

Player UUID + last nickname live in `localStorage` (`future_run_player_id`, `future_run_nickname`).

## Real login later

Install Clerk (or Auth0) from Vercel Marketplace (`vercel integration add clerk`), map `userId` → `player_id`, drop anonymous UUID, and bind scores to authenticated sessions. Neon Auth was also enabled on the store if you prefer Neon-native auth.
