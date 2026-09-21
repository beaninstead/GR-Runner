"""Client helpers for the daily leaderboard API (anonymous nicknames).

Days are UTC calendar buckets (YYYY-MM-DD). Player identity is a UUID kept in
localStorage (web) or a session fallback (desktop). Scores are only submitted
from the campaign win screen — not after each world.
"""

from __future__ import annotations

import json
import time
import uuid

from future_run.constants import LEADERBOARD_API_URL
from future_run.web import IS_WEB

_STORAGE_ID = "future_run_player_id"
_STORAGE_NICK = "future_run_nickname"


def api_base() -> str:
    """Resolve API base URL (no trailing slash). Empty LEADERBOARD_API_URL → same-origin."""
    configured = (LEADERBOARD_API_URL or "").strip().rstrip("/")
    if configured:
        return configured
    if IS_WEB:
        try:
            from platform import window

            origin = str(window.location.origin)
            if origin and origin != "null":
                return origin
        except Exception:
            pass
    # Desktop / file:// fallback — production Vercel host
    return "https://future-run.vercel.app"


def leaderboard_url() -> str:
    return api_base() + "/api/leaderboard"


def _ls_get(key: str):
    if not IS_WEB:
        return None
    try:
        from platform import window

        val = window.localStorage.getItem(key)
        if val is None or val == "null":
            return None
        return str(val)
    except Exception:
        return None


def _ls_set(key: str, value: str) -> None:
    if not IS_WEB:
        return
    try:
        from platform import window

        window.localStorage.setItem(key, value)
    except Exception:
        pass


def get_or_create_player_id() -> str:
    existing = _ls_get(_STORAGE_ID)
    if existing:
        return existing
    pid = str(uuid.uuid4())
    _ls_set(_STORAGE_ID, pid)
    if not IS_WEB:
        # Keep in-process for desktop session
        get_or_create_player_id._desktop = pid  # type: ignore[attr-defined]
    return pid


if not hasattr(get_or_create_player_id, "_desktop"):
    get_or_create_player_id._desktop = None  # type: ignore[attr-defined]


def get_player_id() -> str:
    if IS_WEB:
        return get_or_create_player_id()
    cached = get_or_create_player_id._desktop  # type: ignore[attr-defined]
    if cached:
        return cached
    return get_or_create_player_id()


def get_saved_nickname() -> str:
    return _ls_get(_STORAGE_NICK) or ""


def save_nickname(nickname: str) -> None:
    _ls_set(_STORAGE_NICK, nickname)


def validate_nickname_client(raw: str):
    """Mirror server rules for quick UI feedback. Returns (ok, message_or_nick)."""
    if raw is None:
        return False, "Enter a nickname"
    trimmed = " ".join(str(raw).strip().split())
    if len(trimmed) < 3 or len(trimmed) > 16:
        return False, "3–16 characters"
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _")
    if not trimmed or trimmed[0] in " _":
        return False, "Start with a letter or number"
    if any(c not in allowed for c in trimmed):
        return False, "Letters, numbers, spaces, _"
    lower = trimmed.lower()
    if "http://" in lower or "https://" in lower or "www." in lower:
        return False, "No URLs"
    return True, trimmed


def _looks_like_python_exception(msg: str) -> bool:
    low = msg.lower()
    return (
        "object of type" in low
        or "cannot be convert" in low
        or "traceback" in low
        or low.startswith("typeerror")
        or low.startswith("attributeerror")
        or low.startswith("keyerror")
    )


def error_message(data, fallback: str = "Submit failed") -> str:
    """Always return a short plain-string status for the win UI (never a dict)."""
    if data is None:
        return fallback
    if isinstance(data, str):
        msg = data.strip()
    elif isinstance(data, dict):
        err = data.get("error", data.get("message", fallback))
        if isinstance(err, dict):
            err = err.get("message") or err.get("error") or fallback
        msg = str(err).strip() if err is not None else fallback
    else:
        msg = str(data).strip()
    if not msg:
        return fallback
    if _looks_like_python_exception(msg):
        return "Could not reach leaderboard"
    return msg[:48]


def _parse_response(status: int, text: str):
    try:
        data = json.loads(text) if text else {}
    except Exception:
        data = {"error": text or "Bad response"}
    if status >= 400:
        if isinstance(data, dict):
            # Normalize nested/non-string error fields to a plain string.
            return False, {"error": error_message(data)}
        return False, {"error": str(data)}
    return True, data if isinstance(data, dict) else {"error": "Bad response"}


def fetch_leaderboard_sync(player_id: str | None = None):
    """Blocking GET — fine for desktop; on web prefer async helpers."""
    import urllib.error
    import urllib.request

    url = leaderboard_url()
    if player_id:
        url += "?player_id=" + player_id
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return _parse_response(resp.status, resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return _parse_response(e.code, body)
    except Exception as e:
        return False, {"error": error_message(str(e), "Could not reach leaderboard")}


def submit_score_sync(payload: dict):
    import urllib.error
    import urllib.request

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        leaderboard_url(),
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return _parse_response(resp.status, resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return _parse_response(e.code, body)
    except Exception as e:
        return False, {"error": error_message(str(e), "Could not reach leaderboard")}


def build_submit_payload(nickname: str, score: int, smart: int, coins: int, lives: int):
    return {
        "player_id": get_player_id(),
        "nickname": nickname,
        "score": int(score),
        "smart": int(smart),
        "coins": int(coins),
        "lives": int(lives),
        "client_ts": int(time.time() * 1000),
    }


async def fetch_leaderboard_async(player_id: str | None = None):
    """Web async GET via window.fetch (pygbag)."""
    if not IS_WEB:
        return fetch_leaderboard_sync(player_id)
    url = leaderboard_url()
    if player_id:
        url += "?player_id=" + player_id
    return await _js_fetch(url, "GET", None)


async def submit_score_async(payload: dict):
    if not IS_WEB:
        return submit_score_sync(payload)
    return await _js_fetch(leaderboard_url(), "POST", payload)


async def _js_fetch(url: str, method: str, body):
    from platform import window

    # pygbag's JS bridge cannot pass nested Python dicts as RequestInit —
    # that raises TypeError("object of type 'dict' cannot be converted…").
    # Serialize to a real JS object via JSON.parse.
    headers = {"Accept": "application/json"}
    opts = {"method": method, "headers": headers}
    if body is not None:
        headers["Content-Type"] = "application/json"
        opts["body"] = json.dumps(body)
    try:
        js_opts = window.JSON.parse(json.dumps(opts))
        resp = await window.fetch(url, js_opts)
        text = await resp.text()
        status = int(resp.status)
        return _parse_response(status, str(text))
    except Exception as e:
        return False, {"error": error_message(str(e), "Could not reach leaderboard")}