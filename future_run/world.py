import math

import pygame

from future_run.constants import (
    GRADDIE_SIZE,
    GROUND_ROW,
    GROUND_TOP,
    INK,
    LOGICAL_H,
    LOGICAL_W,
    RENDER_SCALE,
    S,
    TILE,
    WHITE,
)
from future_run.levels import LEVELS

GRADDIE_HINT = "Pick up Graddie to gain powers!"
BOOK_HAZARD_HINT = "Information Overload!!, Jump over to avoid"
FALSE_INFO_HINT = "False Info!"
NEWSPAPER_HAZARD_HINT = FALSE_INFO_HINT
MONEY_TRAP_HAZARD_HINT = "Money Trap! Bad ROI"
SKILL_BARRIER_HINT = "Skill Barrier!"
AGENT_HINT = "Agent appeared"
# Floating labels above hazards / pickups / NPCs (was 15–16).
OBJECT_HINT_FONT_SIZE = S(22)


def _tx(col):
    return col * TILE


def _ty(row):
    return row * TILE


def _wrap_text(font, text, width):
    words = text.split()
    lines, cur = [], ""
    for word in words:
        test = (cur + " " + word).strip()
        if font.size(test)[0] <= width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


class Coin:
    def __init__(self, col, row, anim):
        self.rect = pygame.Rect(_tx(col) + 8, _ty(row) + 8, TILE - 16, TILE - 16)
        self.anim = anim
        self.alive = True

    def update(self, dt=1.0):
        self.anim.update(dt)

    def draw(self, surf, cam):
        surf.blit(self.anim.image, (self.rect.x - 8 - cam.x, self.rect.y - 8 - cam.y))


class BookPile:
    _GLOW = (255, 56, 40)  # red hazard aura
    # Spin newspaper front→edge→front (smooth horizontal flip).
    _SPIN_CYCLE = (0, 1, 2, 3, 2, 1)

    def __init__(self, col, image=None, font=None, hint=BOOK_HAZARD_HINT, frames=None):
        self.frames = list(frames) if frames else None
        if self.frames:
            w = max(f.get_width() for f in self.frames)
            h = max(f.get_height() for f in self.frames)
            self.image = self.frames[0]
        else:
            self.image = image
            w, h = image.get_size()
        self.rect = pygame.Rect(_tx(col), GROUND_TOP - h, w, h)
        self.timer = 0.0
        self._glow_cache = {}
        self._hint_lines = []
        self._hint_outlines = []
        if font is not None:
            wrap_w = max(int(w * 2.6), 300)
            for line in _wrap_text(font, hint, wrap_w):
                self._hint_lines.append(font.render(line, True, INK))
                self._hint_outlines.append(font.render(line, True, WHITE))

    def update(self, dt=1.0):
        self.timer += dt

    def _current_image(self):
        if self.frames:
            idx = self._SPIN_CYCLE[(int(self.timer) // 8) % len(self._SPIN_CYCLE)]
            return self.frames[idx]
        return self.image

    def _glow_for(self, img):
        key = id(img)
        cached = self._glow_cache.get(key)
        if cached is not None:
            return cached
        mask = pygame.mask.from_surface(img)
        silhouette = mask.to_surface(
            setcolor=(*self._GLOW, 255), unsetcolor=(0, 0, 0, 0)
        ).convert_alpha()
        # Web: single cheap halo; desktop: feathered soft glow.
        if RENDER_SCALE < 1.0:
            pad = S(12)
            outer = pygame.Surface(
                (img.get_width() + pad * 2, img.get_height() + pad * 2),
                pygame.SRCALPHA,
            )
            big = pygame.transform.scale(
                silhouette,
                (int(img.get_width() * 1.15), int(img.get_height() * 1.15)),
            )
            bx = (outer.get_width() - big.get_width()) // 2
            by = (outer.get_height() - big.get_height()) // 2
            layer = big.copy()
            layer.fill((255, 255, 255, 70), special_flags=pygame.BLEND_RGBA_MULT)
            outer.blit(layer, (bx, by))
            self._glow_cache[key] = outer
            return outer
        pad = 20
        outer = pygame.Surface(
            (img.get_width() + pad * 2, img.get_height() + pad * 2), pygame.SRCALPHA
        )
        big = pygame.transform.smoothscale(
            silhouette,
            (int(img.get_width() * 1.22), int(img.get_height() * 1.22)),
        )
        bx = (outer.get_width() - big.get_width()) // 2
        by = (outer.get_height() - big.get_height()) // 2
        for dx, dy, a in (
            (0, 0, 70),
            (-5, 0, 48),
            (5, 0, 48),
            (0, -5, 48),
            (0, 5, 48),
            (-7, -4, 32),
            (7, -4, 32),
            (-7, 4, 32),
            (7, 4, 32),
        ):
            layer = big.copy()
            layer.fill((255, 255, 255, a), special_flags=pygame.BLEND_RGBA_MULT)
            outer.blit(layer, (bx + dx, by + dy))
        self._glow_cache[key] = outer
        return outer

    def draw(self, surf, cam, assets=None):
        img = self._current_image()
        x = self.rect.x - cam.x + (self.rect.w - img.get_width()) // 2
        y = self.rect.bottom - cam.y - img.get_height()
        glow = self._glow_for(img)
        if RENDER_SCALE < 1.0:
            # Skip per-frame pulse smoothscale on web.
            glow_draw = glow.copy()
            glow_draw.fill(
                (255, 255, 255, 160),
                special_flags=pygame.BLEND_RGBA_MULT,
            )
            surf.blit(
                glow_draw,
                (
                    x - (glow_draw.get_width() - img.get_width()) // 2,
                    y - (glow_draw.get_height() - img.get_height()) // 2,
                ),
            )
        else:
            # Sine pulse: alpha + slight scale so the hazard reads as urgent.
            wave = 0.5 + 0.5 * math.sin(self.timer * 0.12)
            pulse_a = 0.38 + 0.62 * wave
            pulse_s = 1.0 + 0.06 * wave
            pulsed = glow.copy()
            pulsed.fill(
                (255, 255, 255, int(255 * pulse_a)),
                special_flags=pygame.BLEND_RGBA_MULT,
            )
            if abs(pulse_s - 1.0) > 0.001:
                nw = max(1, int(pulsed.get_width() * pulse_s))
                nh = max(1, int(pulsed.get_height() * pulse_s))
                pulsed = pygame.transform.smoothscale(pulsed, (nw, nh))
            surf.blit(
                pulsed,
                (
                    x - (pulsed.get_width() - img.get_width()) // 2,
                    y - (pulsed.get_height() - img.get_height()) // 2,
                ),
            )
        surf.blit(img, (x, y))
        if self._hint_lines:
            gap = 4
            block_h = sum(s.get_height() for s in self._hint_lines) + gap * (
                len(self._hint_lines) - 1
            )
            ty = y - block_h - 18
            cx = self.rect.centerx - cam.x
            for ink, white in zip(self._hint_lines, self._hint_outlines):
                hx = cx - ink.get_width() // 2
                for ox, oy in (
                    (-2, 0),
                    (2, 0),
                    (0, -2),
                    (0, 2),
                    (-2, -2),
                    (2, 2),
                    (-2, 2),
                    (2, -2),
                ):
                    surf.blit(white, (hx + ox, ty + oy))
                surf.blit(ink, (hx, ty))
                ty += ink.get_height() + gap


class FlyingPhone:
    def __init__(self, x, y, left, right, speed, frames):
        w, h = frames[0].get_size()
        self.rect = pygame.Rect(x, y, w, h)
        self.left = left
        self.right = right
        self.speed = speed
        self.dir = 1
        self.frames = frames
        self.timer = 0.0

    def update(self, dt=1.0):
        self.rect.x += int(self.speed * self.dir * dt)
        if self.rect.x < self.left or self.rect.x > self.right:
            self.dir *= -1
        self.timer += dt

    def draw(self, surf, cam):
        img = self.frames[(int(self.timer) // 8) % len(self.frames)]
        if self.dir < 0:
            img = pygame.transform.flip(img, True, False)
        surf.blit(img, (self.rect.x - cam.x, self.rect.y - cam.y))


class FallingHazard:
    """Floating fee / confusion blobs that bob vertically."""

    def __init__(self, x, y, speed, image):
        w, h = image.get_size()
        self.base_y = y
        self.rect = pygame.Rect(x, y, w, h)
        self.speed = speed
        self.image = image
        self.timer = 0.0
        self.dir = 1

    def update(self, dt=1.0):
        self.timer += dt
        self.rect.y += int(self.speed * self.dir * dt)
        if self.rect.y < self.base_y - 2 * TILE or self.rect.y > self.base_y + 2 * TILE:
            self.dir *= -1

    def draw(self, surf, cam):
        surf.blit(self.image, (self.rect.x - cam.x, self.rect.y - cam.y))


class Platform:
    def __init__(self, col, row, width):
        self.rect = pygame.Rect(_tx(col), _ty(row), width * TILE, TILE)
        self.cols = width
        self.col = col
        self.row = row

    def draw(self, surf, cam, assets):
        brick = assets.tile("brick")
        for i in range(self.cols):
            surf.blit(
                brick,
                (_tx(self.col + i) - cam.x, _ty(self.row) - cam.y),
            )


class FomoBoard:
    def __init__(self, col, image):
        w, h = image.get_size()
        self.rect = pygame.Rect(_tx(col), GROUND_TOP - h, w, h)
        self.image = image
        # Thin one-way platform on the frame top (same feel as brick platforms).
        self.platform_rect = pygame.Rect(self.rect.x, self.rect.y, w, max(8, TILE // 3))

    def draw(self, surf, cam):
        surf.blit(self.image, (self.rect.x - cam.x, self.rect.y - cam.y))


# Decor kinds that act as jumpable one-way platforms.
# Value = fraction of sprite height from the top to the landing surface
# (0 = image top; bench seat sits below the backrest).
_JUMPABLE_DECOR = {
    "board": 0.0,
    "bench": 0.58,
}


class GraddiePickup:
    # idle → jump → land; holds in frames @ ~60fps (~0.7s cycle).
    _HOP = (
        (0, 18),  # short idle
        (1, 14),  # jump peak
        (2, 10),  # soft land
    )
    _LIFT = S(48)  # bounce height in px
    _GLOW = (186, 140, 255)  # soft purple aura

    def __init__(self, x, y, frames, dialogue_box=None, font=None):
        self.rect = pygame.Rect(x, y, GRADDIE_SIZE, GRADDIE_SIZE)
        self.frames = frames
        self.alive = True
        self.timer = 0.0
        self.step = 0
        self._glow_cache = {}
        self._hint_lines = []
        self._hint_outlines = []
        if font is not None:
            for line in _wrap_text(font, GRADDIE_HINT, int(GRADDIE_SIZE * 2.4)):
                self._hint_lines.append(font.render(line, True, INK))
                self._hint_outlines.append(font.render(line, True, WHITE))

    def update(self, dt=1.0):
        self.timer += dt
        _, hold = self._HOP[self.step]
        if self.timer >= hold:
            self.timer = 0.0
            self.step = (self.step + 1) % len(self._HOP)

    def _hop_lift(self):
        """Ease vertical offset so hops aren't only frame-snaps."""
        frame_i, hold = self._HOP[self.step]
        t = self.timer / max(1, hold)
        if frame_i == 0:
            return int(3 * math.sin(t * math.pi * 2))
        if frame_i == 1:
            return int(self._LIFT * math.sin(math.pi * t))
        if frame_i == 2:
            ease = (1.0 - t) * (1.0 - t)
            return int(self._LIFT * 0.12 * ease)
        return 0

    def _glow_for(self, img):
        key = id(img)
        cached = self._glow_cache.get(key)
        if cached is not None:
            return cached
        # Soft halo: tinted silhouette scaled up + feathered stamps.
        mask = pygame.mask.from_surface(img)
        silhouette = mask.to_surface(
            setcolor=(*self._GLOW, 255), unsetcolor=(0, 0, 0, 0)
        ).convert_alpha()
        if RENDER_SCALE < 1.0:
            pad = S(10)
            outer = pygame.Surface(
                (img.get_width() + pad * 2, img.get_height() + pad * 2),
                pygame.SRCALPHA,
            )
            big = pygame.transform.scale(
                silhouette,
                (int(img.get_width() * 1.12), int(img.get_height() * 1.12)),
            )
            bx = (outer.get_width() - big.get_width()) // 2
            by = (outer.get_height() - big.get_height()) // 2
            layer = big.copy()
            layer.fill((255, 255, 255, 55), special_flags=pygame.BLEND_RGBA_MULT)
            outer.blit(layer, (bx, by))
            self._glow_cache[key] = outer
            return outer
        pad = 18
        outer = pygame.Surface(
            (img.get_width() + pad * 2, img.get_height() + pad * 2), pygame.SRCALPHA
        )
        big = pygame.transform.smoothscale(
            silhouette,
            (int(img.get_width() * 1.18), int(img.get_height() * 1.18)),
        )
        bx = (outer.get_width() - big.get_width()) // 2
        by = (outer.get_height() - big.get_height()) // 2
        for dx, dy, a in (
            (0, 0, 55),
            (-4, 0, 40),
            (4, 0, 40),
            (0, -4, 40),
            (0, 4, 40),
            (-6, -3, 28),
            (6, -3, 28),
            (-6, 3, 28),
            (6, 3, 28),
        ):
            layer = big.copy()
            layer.fill((255, 255, 255, a), special_flags=pygame.BLEND_RGBA_MULT)
            outer.blit(layer, (bx + dx, by + dy))
        self._glow_cache[key] = outer
        return outer

    def draw(self, surf, cam):
        frame_i, _ = self._HOP[self.step]
        img = self.frames[min(frame_i, len(self.frames) - 1)]
        lift = self._hop_lift()
        x = self.rect.x - cam.x
        y = self.rect.y - cam.y - lift
        glow = self._glow_for(img)
        surf.blit(
            glow,
            (x - (glow.get_width() - img.get_width()) // 2,
             y - (glow.get_height() - img.get_height()) // 2),
        )
        surf.blit(img, (x, y))
        if self._hint_lines:
            gap = 4
            block_h = sum(s.get_height() for s in self._hint_lines) + gap * (
                len(self._hint_lines) - 1
            )
            ty = y - block_h - 12
            cx = self.rect.centerx - cam.x
            for ink, white in zip(self._hint_lines, self._hint_outlines):
                hx = cx - ink.get_width() // 2
                for ox, oy in (
                    (-2, 0),
                    (2, 0),
                    (0, -2),
                    (0, 2),
                    (-2, -2),
                    (2, 2),
                    (-2, 2),
                    (2, -2),
                ):
                    surf.blit(white, (hx + ox, ty + oy))
                surf.blit(ink, (hx, ty))
                ty += ink.get_height() + gap


class AgentNpc:
    """Study-abroad agent beside the bicycle (World 2) — writing / glance idle."""

    # agent.png: 0 look-back, 1 profile write, 2 front write, 3 glance aside.
    _IDLE_CYCLE = (2, 2, 3, 2, 1, 2, 2, 3)
    _FRAME_HOLD = 16  # ticks per pose @ ~60fps

    def __init__(self, col, frames, font=None):
        # Accept a frame list or a single surface (legacy).
        if isinstance(frames, (list, tuple)):
            self.frames = list(frames)
        else:
            self.frames = [frames]
        self.timer = 0.0
        self.step = 0
        self.image = self.frames[self._IDLE_CYCLE[0] % len(self.frames)]
        w = max(f.get_width() for f in self.frames)
        h = max(f.get_height() for f in self.frames)
        # Sit just left of the bike column so the sprite stands beside it.
        self.rect = pygame.Rect(_tx(col) - w // 2, GROUND_TOP - h, w, h)
        self._hint = None
        self._hint_outline = None
        if font is not None:
            self._hint = font.render(AGENT_HINT, True, INK)
            self._hint_outline = font.render(AGENT_HINT, True, WHITE)

    def update(self, dt=1.0):
        self.timer += dt
        if len(self.frames) <= 1:
            return
        while self.timer >= self._FRAME_HOLD:
            self.timer -= self._FRAME_HOLD
            self.step = (self.step + 1) % len(self._IDLE_CYCLE)
        idx = self._IDLE_CYCLE[self.step] % len(self.frames)
        self.image = self.frames[idx]

    def draw(self, surf, cam):
        # Subtle idle bob so a held pose still feels alive.
        bob = int(round(math.sin(self.timer * 0.11) * 2))
        x = self.rect.x - cam.x
        y = self.rect.y - cam.y + bob
        surf.blit(self.image, (x, y))
        if self._hint is None:
            return
        hx = self.rect.centerx - cam.x - self._hint.get_width() // 2
        hy = y - self._hint.get_height() - 12
        for ox, oy in (
            (-2, 0),
            (2, 0),
            (0, -2),
            (0, 2),
            (-2, -2),
            (2, 2),
            (-2, 2),
            (2, -2),
        ):
            surf.blit(self._hint_outline, (hx + ox, hy + oy))
        surf.blit(self._hint, (hx, hy))


class Trigger:
    def __init__(self, col, kind, payload=None, width=4):
        self.kind = kind
        self.payload = payload
        self.used = False
        self.col = col
        self.width = width
        self.rect = pygame.Rect(_tx(col), GROUND_TOP - 6 * TILE, width * TILE, 6 * TILE)
        self.box = None

    def draw(self, surf, cam, assets, goal_label=None):
        x = self.rect.x - cam.x
        top = GROUND_TOP - cam.y
        if self.kind == "quiz":
            # FOMO is marked by the billboard; the agent quiz uses a standing NPC.
            if self.payload in ("fomo", "agent"):
                return
            self.box.update()
            for i in range(min(3, self.width)):
                surf.blit(self.box.image, (x + (i + 1) * TILE, top - 4 * TILE))
        elif self.kind == "goal":
            gate = assets.gate
            gx = x + (self.rect.w - gate.get_width()) // 2
            gy = top - gate.get_height()
            surf.blit(gate, (gx, gy))
            label = goal_label or "Finish"
            font = assets.font_sm
            ink = font.render(label, True, WHITE)
            outline = font.render(label, True, INK)
            tx = gx + (gate.get_width() - ink.get_width()) // 2
            ty = gy - ink.get_height() - 6
            for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
                surf.blit(outline, (tx + ox, ty + oy))
            surf.blit(ink, (tx, ty))


SKY_TINTS = {
    "day": None,
    "dusk": (255, 140, 80, 40),
    "city": (80, 100, 180, 35),
    "future": (160, 80, 220, 45),
}


class World:
    def __init__(self, assets, level_index=0):
        self.assets = assets
        self.level_index = level_index
        self.cfg = LEVELS[level_index]
        self.cols = self.cfg["cols"]
        self.rows = LOGICAL_H // TILE
        self.pits = list(self.cfg.get("pits") or [])
        self.world_right = self.cols * TILE
        self.ground = self._build_ground()
        self.clouds = list(self.cfg.get("clouds") or [])
        self.decor = list(self.cfg.get("decor") or [])
        self.sky_tint = SKY_TINTS.get(self.cfg.get("sky", "day"))
        # Non-tileable skyline: keep a per-world strip wide enough that parallax
        # never needs to wrap inside the viewport (slight H-stretch only if short).
        self.backdrop = self.assets.backdrops.get(self.cfg.get("backdrop"))
        if self.backdrop is not None:
            bw = self.backdrop.get_width()
            bh = self.backdrop.get_height()
            max_cam = max(0, self.world_right - LOGICAL_W)
            need_w = LOGICAL_W + int(max_cam * 0.35)
            if bw < need_w:
                self.backdrop = pygame.transform.scale(self.backdrop, (need_w, bh))

        gy = GROUND_ROW
        self.coins = []
        for col, above in self.cfg.get("coins") or []:
            self.coins.append(Coin(col, gy - above, assets.coin_anim()))

        self.books = []
        book_font = assets.font(OBJECT_HINT_FONT_SIZE)
        for item in self.cfg.get("books") or []:
            col, kind = item[0], item[1] if len(item) > 1 else "tall"
            if kind in ("newspaper", "false_info"):
                self.books.append(
                    BookPile(
                        col,
                        frames=assets.false_info,
                        font=book_font,
                        hint=FALSE_INFO_HINT,
                    )
                )
            elif kind == "money_trap":
                self.books.append(
                    BookPile(
                        col,
                        assets.money_trap,
                        font=book_font,
                        hint=MONEY_TRAP_HAZARD_HINT,
                    )
                )
            elif kind == "skill_barrier":
                self.books.append(
                    BookPile(
                        col,
                        assets.skill_barrier,
                        font=book_font,
                        hint=SKILL_BARRIER_HINT,
                    )
                )
            else:
                img = assets.books if kind == "tall" else assets.books_short
                self.books.append(BookPile(col, img, font=book_font))

        self.phones = []
        for xcol, above, left, right, speed in self.cfg.get("phones") or []:
            self.phones.append(
                FlyingPhone(
                    _tx(xcol),
                    _ty(gy - above),
                    _tx(left),
                    _tx(right),
                    S(speed),
                    assets.phones,
                )
            )

        self.platforms = [
            Platform(col, row, width)
            for col, row, width in (self.cfg.get("platforms") or [])
        ]

        self.falling = []
        default_sprite = getattr(
            assets, self.cfg.get("falling_sprite", "blob_blue"), assets.blob_blue
        )
        for entry in self.cfg.get("falling") or []:
            col, above, speed = entry[0], entry[1], entry[2]
            sprite = default_sprite
            if len(entry) >= 4 and entry[3]:
                sprite = getattr(assets, entry[3], default_sprite)
            self.falling.append(
                FallingHazard(
                    _tx(col),
                    _ty(gy - above),
                    S(speed),
                    sprite,
                )
            )

        self.fomo_boards = []
        for item in self.cfg.get("fomo_boards") or []:
            col = item[0] if isinstance(item, (list, tuple)) else item
            self.fomo_boards.append(FomoBoard(col, assets.fomo_board))

        self.prop_platforms = self._build_prop_platforms()

        self.graddies = []
        for kind, col in self.cfg.get("pickups") or []:
            if kind == "graddie":
                self.graddies.append(
                    GraddiePickup(
                        _tx(col),
                        GROUND_TOP - GRADDIE_SIZE,
                        assets.graddie,
                        font=assets.font(OBJECT_HINT_FONT_SIZE),
                    )
                )

        self.npcs = []
        for kind, col in self.cfg.get("npcs") or []:
            if kind == "agent":
                self.npcs.append(
                    AgentNpc(
                        col, assets.agent, font=assets.font(OBJECT_HINT_FONT_SIZE)
                    )
                )

        self.triggers = []
        for col, kind, payload, width in self.cfg.get("triggers") or []:
            trig = Trigger(col, kind, payload, width=width)
            if kind == "quiz":
                trig.box = assets.box_anim()
            self.triggers.append(trig)

    def _build_ground(self):
        spans = []
        cursor = 0
        pits = sorted(self.pits)
        for pit0, pit1 in pits:
            if cursor < pit0:
                spans.append((_tx(cursor), _tx(pit0), GROUND_TOP))
            cursor = pit1
        if cursor < self.cols:
            spans.append((_tx(cursor), self.world_right, GROUND_TOP))
        if not spans:
            spans = [(0, self.world_right, GROUND_TOP)]
        return spans

    def update(self, dt=1.0):
        for coin in self.coins:
            if coin.alive:
                coin.update(dt)
        for book in self.books:
            book.update(dt)
        for phone in self.phones:
            phone.update(dt)
        for haz in self.falling:
            haz.update(dt)
        for g in self.graddies:
            if g.alive:
                g.update(dt)
        for npc in self.npcs:
            npc.update(dt)

    def _build_prop_platforms(self):
        """One-way tops for boards, benches, FOMO frames, and book piles."""
        rects = []
        plat_h = max(8, TILE // 3)
        for kind, col in self.decor:
            frac = _JUMPABLE_DECOR.get(kind)
            if frac is None:
                continue
            img = getattr(self.assets, kind, None)
            if img is None:
                continue
            w, h = img.get_size()
            x = _tx(col)
            top = GROUND_TOP - h + int(h * frac)
            rects.append(pygame.Rect(x, top, w, plat_h))
        for board in self.fomo_boards:
            rects.append(board.platform_rect)
        # Book tops via physics (same as bench) so grounding does not depend on
        # post-pass colliderect, which fails when feet sit exactly on the rim.
        for book in self.books:
            rects.append(
                pygame.Rect(book.rect.x, book.rect.y, book.rect.w, plat_h)
            )
        return rects

    def solid_rects(self):
        """Platform tops the player can stand on (in addition to ground spans)."""
        return [p.rect for p in self.platforms] + list(self.prop_platforms)

    def _visible_range(self, cam):
        x0 = max(0, cam.x // TILE - 1)
        x1 = min(self.cols, (cam.x + LOGICAL_W) // TILE + 2)
        y0 = max(0, cam.y // TILE - 1)
        y1 = min(self.rows, (cam.y + LOGICAL_H) // TILE + 2)
        return int(x0), int(x1), int(y0), int(y1)

    def _in_pit(self, tx):
        for pit0, pit1 in self.pits:
            if pit0 <= tx < pit1:
                return True
        return False

    def draw_background(self, surf, cam):
        x0, x1, y0, y1 = self._visible_range(cam)
        sky = self.assets.tile("sky")
        ground = self.assets.tile("ground")

        if self.backdrop is not None:
            # Parallax panorama above the ground. Source art is not seamless, so
            # scroll a single strip (clamp) — never tile/wrap mid-screen.
            bw = self.backdrop.get_width()
            y = -cam.y
            max_shift = max(0, bw - LOGICAL_W)
            shift = min(max(0, int(cam.x * 0.35)), max_shift)
            surf.blit(self.backdrop, (-shift, y))
            for ty in range(max(y0, GROUND_ROW), y1):
                for tx in range(x0, x1):
                    dest = (tx * TILE - cam.x, ty * TILE - cam.y)
                    if self._in_pit(tx):
                        # Backdrop only covers y < GROUND_TOP; blit sky so pit
                        # columns stay empty (no leftover ground / black fill).
                        surf.blit(sky, dest)
                    else:
                        surf.blit(ground, dest)
        else:
            for ty in range(y0, y1):
                for tx in range(x0, x1):
                    dest = (tx * TILE - cam.x, ty * TILE - cam.y)
                    if ty >= GROUND_ROW:
                        if self._in_pit(tx):
                            surf.blit(sky, dest)
                        else:
                            surf.blit(ground, dest)
                    else:
                        surf.blit(sky, dest)
            if self.sky_tint:
                tint = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
                tint.fill(self.sky_tint)
                surf.blit(tint, (0, 0))
            self._draw_clouds(surf, cam)

        self._draw_decor(surf, cam)

    def _draw_clouds(self, surf, cam):
        for i, (cx, cy) in enumerate(self.clouds):
            img = self.assets.cloud1 if i % 2 == 0 else self.assets.cloud2
            surf.blit(img, (_tx(cx) - cam.x, _ty(cy) - cam.y))

    def _draw_decor(self, surf, cam):
        for kind, col in self.decor:
            img = getattr(self.assets, kind)
            x = _tx(col) - cam.x
            y = GROUND_TOP - img.get_height() - cam.y
            surf.blit(img, (x, y))

    def draw_entities(self, surf, cam, font=None):
        for plat in self.platforms:
            plat.draw(surf, cam, self.assets)
        for board in self.fomo_boards:
            board.draw(surf, cam)
        for coin in self.coins:
            if coin.alive:
                coin.draw(surf, cam)
        for book in self.books:
            book.draw(surf, cam)
        for phone in self.phones:
            phone.draw(surf, cam)
        for haz in self.falling:
            haz.draw(surf, cam)
        for g in self.graddies:
            if g.alive:
                g.draw(surf, cam)
        for npc in self.npcs:
            npc.draw(surf, cam)
        next_i = self.level_index + 1
        if next_i < len(LEVELS):
            goal_label = "Go to World {}".format(next_i + 1)
        else:
            goal_label = "Finish"
        for trig in self.triggers:
            if not trig.used or trig.kind == "goal":
                trig.draw(surf, cam, self.assets, goal_label=goal_label)


def draw_mario_backdrop(surf, assets):
    cols = LOGICAL_W // TILE + 2
    rows = LOGICAL_H // TILE + 1
    sky = assets.tile("sky")
    ground = assets.tile("ground")
    for ty in range(rows):
        for tx in range(cols):
            dest = (tx * TILE, ty * TILE)
            surf.blit(ground if ty >= GROUND_ROW else sky, dest)
    for i, (cx, cy) in enumerate(((2, 6), (8, 4), (13, 7))):
        img = assets.cloud1 if i % 2 == 0 else assets.cloud2
        surf.blit(img, (cx * TILE, cy * TILE))
    y = GROUND_TOP
    for kind, bx in (("bush", 1), ("board", 5), ("bike", 8)):
        img = getattr(assets, kind)
        surf.blit(img, (bx * TILE, y - img.get_height()))
