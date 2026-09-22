const NICK_RE = /^[A-Za-z0-9][A-Za-z0-9 _]*$/;
const URLISH_RE = /(https?:\/\/|www\.|\.(com|net|org|io|gg|xyz)\b)/i;

const NICK_REJECT_MSG = "Please choose a different name";

// Exact match on compacted alphanumeric token (after leet normalize).
const ABUSE_COMPACT = new Set(
  [
    // English
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
    // Hinglish / romanized Hindi
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
  ].map((w) => w.toLowerCase())
);

// Longer substrings matched inside compacted nick (glued / spaced-out abuse).
const ABUSE_SUBSTR = [
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
];

// Devanagari abuse terms (checked on raw string).
const ABUSE_DEVANAGARI = [
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
];

const LEET_MAP = {
  "0": "o",
  "1": "i",
  "3": "e",
  "4": "a",
  "5": "s",
  "7": "t",
  "8": "b",
  "@": "a",
  $: "s",
  "!": "i",
};

function normalizeNickForAbuse(raw) {
  let s = String(raw || "").toLowerCase();
  s = s.replace(/[0134578@$!]/g, (ch) => LEET_MAP[ch] || ch);
  return s.replace(/[^a-z0-9]/g, "");
}

function nicknameIsAbusive(raw) {
  const text = String(raw || "");
  for (const term of ABUSE_DEVANAGARI) {
    if (text.includes(term)) return true;
  }
  const compact = normalizeNickForAbuse(text);
  if (!compact) return false;
  if (ABUSE_COMPACT.has(compact)) return true;
  for (const part of text.replace(/_/g, " ").split(/\s+/)) {
    const p = normalizeNickForAbuse(part);
    if (p && ABUSE_COMPACT.has(p)) return true;
  }
  for (const sub of ABUSE_SUBSTR) {
    if (sub.length >= 4 && compact.includes(sub)) return true;
  }
  return false;
}

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function normalizeNickname(raw) {
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim().replace(/\s+/g, " ");
  if (trimmed.length < 3 || trimmed.length > 16) return null;
  if (nicknameIsAbusive(trimmed)) return null;
  if (!NICK_RE.test(trimmed)) return null;
  if (URLISH_RE.test(trimmed)) return null;
  const compact = normalizeNickForAbuse(trimmed);
  if (!compact) return null;
  return trimmed;
}

export function nicknameNorm(nickname) {
  return nickname.trim().toLowerCase().replace(/\s+/g, " ");
}

export function isUuid(value) {
  return typeof value === "string" && UUID_RE.test(value);
}

export function asInt(value, min, max) {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n) || !Number.isInteger(n)) return null;
  if (n < min || n > max) return null;
  return n;
}

export function validateSubmitBody(body) {
  if (!body || typeof body !== "object") {
    return { error: "Invalid JSON body" };
  }
  if (typeof body.nickname === "string" && nicknameIsAbusive(body.nickname)) {
    return { error: NICK_REJECT_MSG };
  }
  const nickname = normalizeNickname(body.nickname);
  if (!nickname) {
    return {
      error:
        "Nickname must be 3–16 chars: letters, numbers, spaces, underscores; no URLs or empty",
    };
  }
  if (!isUuid(body.player_id)) {
    return { error: "player_id must be a UUID" };
  }
  const score = asInt(body.score, 0, 10_000_000);
  if (score === null) return { error: "score must be an integer 0…10000000" };
  const smart = asInt(body.smart, 0, 10_000);
  if (smart === null) return { error: "smart must be an integer 0…10000" };

  let coins = null;
  let lives = null;
  let client_ts = null;
  if (body.coins !== undefined && body.coins !== null) {
    coins = asInt(body.coins, 0, 100_000);
    if (coins === null) return { error: "coins out of range" };
  }
  if (body.lives !== undefined && body.lives !== null) {
    lives = asInt(body.lives, 0, 3);
    if (lives === null) return { error: "lives out of range" };
  }
  if (body.client_ts !== undefined && body.client_ts !== null) {
    client_ts = asInt(body.client_ts, 0, Number.MAX_SAFE_INTEGER);
    if (client_ts === null) return { error: "client_ts invalid" };
  }

  return {
    value: {
      nickname,
      nickname_norm: nicknameNorm(nickname),
      player_id: body.player_id.toLowerCase(),
      score,
      smart,
      coins,
      lives,
      client_ts,
    },
  };
}
