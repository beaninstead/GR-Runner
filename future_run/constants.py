LOGICAL_W = 1080
LOGICAL_H = 1920
FPS = 60
# Portrait aspect (width / height) for web canvas CSS letterboxing.
ASPECT = LOGICAL_W / LOGICAL_H


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

TILE = 96
GROUND_ROW = 16
GROUND_TOP = GROUND_ROW * TILE
# World pickup / sprite box (was TILE; doubled for clearer presence).
GRADDIE_SIZE = 2 * TILE  # 192
PLAYER_W, PLAYER_H = 160, 160
GRAVITY = 1.35
JUMP_VEL = -28.0
MOVE_ACCEL = 1.05
MOVE_MAX = 9.2
FRICTION = 0.80

START_LIVES = 3
COIN_VALUE = 10
INVINCIBLE_FRAMES = 70
# World 4 reward after third pit — lasts the rest of the level at 60 FPS.
WORLD4_INVINCIBLE_FRAMES = 60 * 60 * 20  # ~20 minutes
SKILL_BOOST_FRAMES = 60 * 8  # ~8 seconds of super-speed
SKILL_BOOST_MAX = 14.5
WORLD_INTRO_FRAMES = 90
CTA_URL = "https://www.gradright.com"
