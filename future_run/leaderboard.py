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
_PRODUCTION_API = "https://future-run.vercel.app"
_LOCAL_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "0.0.0.0", "[::1]", "::1"}
)


def api_base() -> str:
    """Resolve API base URL (no trailing slash).

    Empty LEADERBOARD_API_URL → same-origin only on hosts that serve the
    Vercel `/api` functions. Local static previews, itch, Netlify, GitHub
    Pages, and LAN IPs have no API — those use the production Vercel host
    (CORS allows *). Treating HTML 200 SPA fallbacks as boards caused empty
    "No scores yet today" panels.
    """
    configured = (LEADERBOARD_API_URL or "").strip().rstrip("/")
    if configured:
        return configured
    if IS_WEB:
        try:
            from platform import window

            host = str(getattr(window.location, "hostname", "") or "").lower()
            if host in _LOCAL_HOSTS or host.endswith(".local"):
                return _PRODUCTION_API
            # Same-origin API only where serverless routes exist.
            if host == "future-run.vercel.app" or host.endswith(".vercel.app"):
                origin = str(window.location.origin or "")
                if origin and origin != "null":
                    return origin.rstrip("/")
            return _PRODUCTION_API
        except Exception:
            pass
    # Desktop / file:// — production Vercel host
    return _PRODUCTION_API


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
    saved = _ls_get(_STORAGE_NICK)
    if saved:
        return saved
    return getattr(get_saved_nickname, "_desktop", "") or ""


def save_nickname(nickname: str) -> None:
    get_saved_nickname._desktop = nickname  # type: ignore[attr-defined]
    _ls_set(_STORAGE_NICK, nickname)


if not hasattr(get_saved_nickname, "_desktop"):
    get_saved_nickname._desktop = ""  # type: ignore[attr-defined]


# Family-friendly reject message (never echo the blocked term).
_NICK_REJECT_MSG = "Please choose a different name"

# Compact tokens (after normalize) — English + Hinglish romanizations.
# Prefer whole-token / includes checks on compacted alphanumeric only.
_ABUSE_COMPACT = frozenset(
    {
        # English
        "ass",
        "asshole",
        "bastard",
        "bitch",
        "bollocks",
        "cock",
        "crap",
        "cunt",
        "damn",
        "dick",
        "fag",
        "faggot",
        "fuck",
        "fucker",
        "fucking",
        "motherfucker",
        "nigger",
        "nigga",
        "piss",
        "porn",
        "pussy",
        "shit",
        "slut",
        "twat",
        "whore",
        "sex",
        "sexy",
        "nude",
        "nudes",
        # Hinglish / romanized Hindi (common slang & abbreviations)
        "madarchod",
        "madrchod",
        "madarchodh",
        "behenchod",
        "bhenchod",
        "bahenchod",
        "bhenchodh",
        "betichod",
        "bhosdike",
        "bhosdi",
        "bhosada",
        "bhosda",
        "bhosdee",
        "bsdk",
        "bstdk",
        "chutiya",
        "chutya",
        "chutiyo",
        "chutiyapa",
        "chut",
        "choot",
        "chootiya",
        "gandu",
        "gaandu",
        "gand",
        "gaand",
        "lund",
        "loda",
        "lode",
        "lawda",
        "lawde",
        "harami",
        "haraami",
        "saala",
        "sala",
        "saali",
        "sali",
        "kamina",
        "kamine",
        "kutiya",
        "kutte",
        "kutia",
        "randi",
        "raandi",
        "rand",
        "hijda",
        "hijada",
        "napunsak",
        "mc",
        "bc",
        "mader",
        "bkl",
        "chodu",
        "chod",
        "chode",
        "jhaantu",
        "jhantu",
        "tatti",
        "tharkee",
        "tharki",
        "suar",
        "suarike",
    }
)

# Longer substrings that should match inside compacted nick even if glued.
_ABUSE_SUBSTR = (
    "madarchod",
    "behenchod",
    "bhenchod",
    "betichod",
    "bhosdi",
    "chutiya",
    "chootiya",
    "motherfuck",
    "fuck",
    "shit",
    "bitch",
    "asshole",
    "nigger",
    "nigga",
)

# Devanagari abuse / vulgar terms (checked on raw + lowercased NFC).
_ABUSE_DEVANAGARI = (
    "मदरचोद",
    "मादरचोद",
    "बहनचोद",
    "भेनचोद",
    "चूतिया",
    "चुतिया",
    "गांडू",
    "गांड",
    "भोसड़ी",
    "भोसडी",
    "हरामी",
    "हरामजादा",
    "कमीना",
    "रंडी",
    "लौड़ा",
    "लौडा",
    "लंड",
    "चूत",
    "साला",
    "साली",
    "कुत्ता",
    "कुतिया",
)


def _normalize_nick_for_abuse(raw: str) -> str:
    """Lowercase, leetspeak-ish map, strip non-alphanumerics for compact match."""
    s = str(raw or "").lower()
    trans = str.maketrans(
        {
            "0": "o",
            "1": "i",
            "3": "e",
            "4": "a",
            "5": "s",
            "7": "t",
            "8": "b",
            "@": "a",
            "$": "s",
            "!": "i",
        }
    )
    s = s.translate(trans)
    return "".join(ch for ch in s if ch.isalnum())


def _nickname_is_abusive(raw: str) -> bool:
    text = str(raw or "")
    # Devanagari / mixed-script checks on original text.
    for term in _ABUSE_DEVANAGARI:
        if term in text:
            return True
    compact = _normalize_nick_for_abuse(text)
    if not compact:
        return False
    if compact in _ABUSE_COMPACT:
        return True
    # Token-ish: split original on spaces/underscores then compact each.
    for part in text.replace("_", " ").split():
        p = _normalize_nick_for_abuse(part)
        if p in _ABUSE_COMPACT:
            return True
    for sub in _ABUSE_SUBSTR:
        if len(sub) >= 4 and sub in compact:
            return True
    return False


def validate_nickname_client(raw: str):
    """Mirror server rules for quick UI feedback. Returns (ok, message_or_nick)."""
    if raw is None:
        return False, "Enter a nickname"
    trimmed = " ".join(str(raw).strip().split())
    if len(trimmed) < 3 or len(trimmed) > 16:
        return False, "3–16 characters"
    if _nickname_is_abusive(trimmed):
        return False, _NICK_REJECT_MSG
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


def is_board_payload(data) -> bool:
    """True only for a real leaderboard JSON shape (has a list `top`)."""
    return isinstance(data, dict) and isinstance(data.get("top"), list)


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
    if not isinstance(data, dict):
        return False, {"error": "Bad response"}
    # SPA hosts often return HTML/index with HTTP 200 for unknown /api paths.
    # That must not be treated as an empty board.
    if not is_board_payload(data):
        err = error_message(data, "Could not reach leaderboard")
        return False, {"error": err}
    return True, data


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
    # Community quiz can push lives above START_LIVES (3). Live API historically
    # rejected >3 — clamp so submit still succeeds; ranking uses score/smart.
    lives_i = max(0, min(3, int(lives)))
    return {
        "player_id": get_player_id(),
        "nickname": nickname,
        "score": int(score),
        "smart": int(smart),
        "coins": max(0, min(100_000, int(coins))),
        "lives": lives_i,
        "client_ts": int(time.time() * 1000),
    }


def fallback_board(
    player_id: str | None = None,
    nickname: str = "",
    score: int = 0,
    smart: int = 0,
    coins: int = 0,
    lives: int = 0,
):
    """Offline / unreachable-API board so the UI is never blank.

    Seeds a few demo rows and, when possible, inserts the current player so
    a completed run still shows a ranked score locally.
    """
    day_key = time.strftime("%Y-%m-%d", time.gmtime())
    demo = [
        ("PixelPilot", 1250, 9),
        ("FutureFox", 1180, 8),
        ("CoinScout", 1020, 7),
        ("QuizWhiz", 940, 6),
        ("GradRunner", 880, 5),
        ("SmartLeap", 810, 4),
        ("CampusDash", 760, 3),
        ("SkillSpark", 700, 2),
    ]
    entries = []
    for i, (nick, sc, sm) in enumerate(demo, start=1):
        entries.append(
            {
                "rank": i,
                "player_id": f"demo-{i:02d}",
                "nickname": nick,
                "score": sc,
                "smart": sm,
                "coins": max(10, sc // 20),
                "lives": 2,
            }
        )

    you = None
    nick = (nickname or "").strip()
    # Include the player even at score 0 so a finished run never looks empty.
    if player_id and nick:
        you = {
            "rank": 0,
            "player_id": player_id,
            "nickname": nick[:16],
            "score": int(score),
            "smart": int(smart),
            "coins": int(coins),
            "lives": int(lives),
        }
        entries.append(you)
        entries.sort(key=lambda e: (-e["score"], -e["smart"], e["nickname"]))
        for i, e in enumerate(entries, start=1):
            e["rank"] = i
        you = next((e for e in entries if e.get("player_id") == player_id), you)

    return {
        "day_key": day_key,
        "timezone": "UTC",
        "sort": ["score_desc", "smart_desc"],
        "top": entries[:10],
        "you": you,
        "offline": True,
    }


def local_player_board(
    player_id: str | None,
    nickname: str,
    score: int,
    smart: int = 0,
    coins: int = 0,
    lives: int = 0,
):
    """Single-row board so the UI never shows a blank day after a submit."""
    day_key = time.strftime("%Y-%m-%d", time.gmtime())
    nick = (nickname or "").strip()[:16] or "You"
    pid = player_id or "local"
    you = {
        "rank": 1,
        "player_id": pid,
        "nickname": nick,
        "score": int(score),
        "smart": int(smart),
        "coins": int(coins),
        "lives": int(lives),
    }
    return {
        "day_key": day_key,
        "timezone": "UTC",
        "sort": ["score_desc", "smart_desc"],
        "top": [you],
        "you": you,
        "pending": True,
    }


def ensure_player_on_board(
    board: dict | None,
    player_id: str | None,
    nickname: str,
    score: int,
    smart: int = 0,
    coins: int = 0,
    lives: int = 0,
):
    """If the API board omits this player, splice them in (optimistic / failed POST)."""
    nick = (nickname or "").strip()
    if not board or not isinstance(board, dict) or not player_id or not nick:
        return board
    top = list(board.get("top") or [])
    you = board.get("you")
    if you and you.get("player_id") == player_id:
        return board
    if any(e.get("player_id") == player_id for e in top):
        return board

    entry = {
        "rank": 0,
        "player_id": player_id,
        "nickname": nick[:16],
        "score": int(score),
        "smart": int(smart),
        "coins": int(coins),
        "lives": int(lives),
    }
    merged = list(top) + [entry]
    merged.sort(key=lambda e: (-int(e.get("score") or 0), -int(e.get("smart") or 0), str(e.get("nickname") or "")))
    for i, e in enumerate(merged, start=1):
        e["rank"] = i
    you_row = next((e for e in merged if e.get("player_id") == player_id), entry)
    out = dict(board)
    out["top"] = merged[:10]
    out["you"] = you_row
    out["local_you"] = True
    return out


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