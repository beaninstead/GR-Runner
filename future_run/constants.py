from future_run.web import IS_WEB

# Full design resolution is 1080×1920. On web/mobile, render at half so
# pygbag fills ~¼ the pixels and avoids a per-frame 1080p smoothscale.
DESIGN_W = 1080
DESIGN_H = 1920
RENDER_SCALE = 0.5 if IS_WEB else 1.0


def S(n):
    """Map a 1080p-design value to the active render scale."""
    if RENDER_SCALE == 1.0:
        return n
    if isinstance(n, float):
        return n * RENDER_SCALE
    return int(round(n * RENDER_SCALE))


LOGICAL_W = S(DESIGN_W)
LOGICAL_H = S(DESIGN_H)
FPS = 60
# Portrait aspect (width / height) for web canvas CSS letterboxing.
ASPECT = DESIGN_W / DESIGN_H


def frame_scale(dt_seconds):
    """Convert real dt to 'frames at 60fps' so per-frame motion stays consistent.

    Web/pygbag often runs well below 60 FPS; without this, frame-based velocity
    makes the player crawl. Clamp so a hitch does not teleport the player.
    """
    if dt_seconds is None or dt_seconds <= 0:
        return 1.0
    return max(0.25, min(float(dt_seconds) * FPS, 3.0))

PURPLE = (109, 40, 217)
PURPLE_DARK = (46, 16, 101)
PURPLE_SOFT = (167, 139, 250)
GOLD = (250, 204, 21)
WHITE = (255, 255, 255)
INK = (30, 27, 46)
SKY_TOP = (135, 186, 245)
SKY_BOT = (232, 244, 255)
GRASS = (86, 166, 75)
DIRT = (196, 140, 82)
BRICK = (232, 197, 149)
PHONE = (40, 40, 48)
BOOK_RED = (185, 28, 28)
BOOK_BLUE = (29, 78, 216)
BOOK_GREEN = (21, 128, 61)
OUTLINE = (28, 22, 36)

TILE = S(96)
GROUND_ROW = 16
GROUND_TOP = GROUND_ROW * TILE
# World pickup / sprite box (was TILE; doubled for clearer presence).
GRADDIE_SIZE = 2 * TILE  # 192 design → scaled
PLAYER_W, PLAYER_H = S(160), S(160)
GRAVITY = S(1.35)
JUMP_VEL = S(-28.0)
MOVE_ACCEL = S(1.05)
MOVE_MAX = S(9.2)
FRICTION = 0.80
# Terminal fall speed and foot-snap slop (design px).
FALL_MAX = S(28)
FOOT_SLOP_MIN = S(40)
FOOT_SLOP_PAD = S(12)
FOOT_INSET = S(8)
WORLD_EDGE = S(40)
PIT_BELOW = S(80)
PIT_NEAR = S(20)
# Idle velocity cutoff (design px/frame).
VEL_STOP = S(0.25)
VEL_RUN = S(0.4)

START_LIVES = 3
COIN_VALUE = 10
INVINCIBLE_FRAMES = 70
# World 4 reward after third pit — lasts the rest of the level at 60 FPS.
WORLD4_INVINCIBLE_FRAMES = 60 * 60 * 20  # ~20 minutes
SKILL_BOOST_FRAMES = 60 * 8  # ~8 seconds of super-speed
SKILL_BOOST_MAX = S(14.5)
WORLD_INTRO_FRAMES = 90
# Quiz answer feedback bubble — ~5s of real time under frame_scale(dt).
QUIZ_FEEDBACK_FRAMES = 60 * 5
CTA_URL = "https://www.gradright.com"
# Daily leaderboard API. Empty = same-origin `/api/leaderboard` on web
# (Vercel). Override for local static preview against production, e.g.
# "https://future-run.vercel.app". Days are UTC calendar buckets.
LEADERBOARD_API_URL = ""
