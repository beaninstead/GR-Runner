import math

import pygame

from future_run.constants import (
    GOLD,
    GROUND_TOP,
    INK,
    LOGICAL_H,
    LOGICAL_W,
    PURPLE,
    PURPLE_DARK,
    PURPLE_SOFT,
    RENDER_SCALE,
    S,
    TILE,
    WHITE,
)
from future_run.world import World

# Bright gold used for Ask-Graddie hint glow (reads on cream + dark quiz overlay).
_HINT_GLOW = (255, 220, 60)


def blit_center(surf, image, y):
    surf.blit(image, ((LOGICAL_W - image.get_width()) // 2, y))


def draw_text_center(surf, font, text, y, color=WHITE):
    img = font.render(str(text), True, color)
    blit_center(surf, img, y)
    return img


def _status_line(status, limit=40):
    """Coerce win-screen status to a plain string safe for font.render."""
    if status is None or status is False or status == "":
        return ""
    if isinstance(status, dict):
        status = status.get("error") or status.get("message") or "Error"
    text = str(status).strip()
    if not text:
        return ""
    low = text.lower()
    if (
        "object of type" in low
        or "cannot be convert" in low
        or "traceback" in low
        or low.startswith("typeerror")
    ):
        return "Could not reach leaderboard"
    return text[:limit]


def wrap_text(font, text, width):
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


# Cream header fraction of quiz_panel.png (measured from asset).
_QUIZ_HEADER_RATIO = 0.314
_QUIZ_PANEL_ASPECT = 691 / 1024  # native h/w
_QUIZ_PANEL_HEIGHT_SCALE = 1.2  # +20% taller dialogue box
# Quiz typography — sized to fill cream header + option buttons
_QUIZ_TITLE_SIZE = S(36)
_QUIZ_PROMPT_SIZE = S(28)
_QUIZ_OPTION_SIZE = S(26)
_QUIZ_HINT_SIZE = S(18)
# Extra gap between wrapped lines (prompt, options, feedback).
_QUIZ_LINE_GAP = S(8)
# Ask-Graddie banner: text lives in the white panel right of the character.
ASK_GRADDIE_TEXT_LEFT = 0.29
ASK_GRADDIE_TEXT_RIGHT = 0.05
_ASK_GRADDIE_MAX_W = S(380)


def quiz_layout(assets, quiz, has_helper=False):
    """Compute quiz panel + option button rects (vertically centered)."""
    panel_w = S(980)
    panel_h = int(panel_w * _QUIZ_PANEL_ASPECT * _QUIZ_PANEL_HEIGHT_SCALE)
    panel_x = (LOGICAL_W - panel_w) // 2
    panel_y = (LOGICAL_H - panel_h) // 2
    header_h = int(panel_h * _QUIZ_HEADER_RATIO)

    title_font = assets.font(_QUIZ_TITLE_SIZE)
    prompt_font = assets.font(_QUIZ_PROMPT_SIZE)
    option_font = assets.font(_QUIZ_OPTION_SIZE)
    hint_font = assets.font(_QUIZ_HINT_SIZE)
    pad_x = S(56)
    text_w = panel_w - pad_x * 2

    title_h = title_font.size(quiz["title"])[1]
    prompt_lines = wrap_text(prompt_font, quiz["prompt"], text_w)
    prompt_h = sum(prompt_font.size(line)[1] for line in prompt_lines)
    if len(prompt_lines) > 1:
        prompt_h += _QUIZ_LINE_GAP * (len(prompt_lines) - 1)
    header_content_h = title_h + S(12) + prompt_h
    # Vertically center title+prompt inside cream header.
    header_text_top = panel_y + max(S(16), (header_h - header_content_h) // 2)

    opt_w = S(860)
    opt_x = (LOGICAL_W - opt_w) // 2
    n = len(quiz["choices"])
    ask = getattr(assets, "ask_graddie", None) if has_helper else None

    if ask is not None:
        aw, ah = ask.get_size()
        aspect = aw / float(max(1, ah))
        helper_w = min(_ASK_GRADDIE_MAX_W, opt_w)
        helper_h = max(S(86), int(round(helper_w / aspect)))
        helper_gap = S(17)
        opt_h = S(100)
        gap = S(12)
    elif has_helper:
        helper_w = opt_w
        helper_h = S(96)
        helper_gap = S(22)
        opt_h = S(112)
        gap = S(16)
    else:
        helper_w = 0
        helper_h = 0
        helper_gap = 0
        opt_h = S(120)
        gap = S(22)

    body_top = panel_y + header_h + S(28)
    body_bottom = panel_y + panel_h - S(34)
    body_h = body_bottom - body_top
    options_block = n * opt_h + max(0, n - 1) * gap + (
        helper_gap + helper_h if has_helper else 0
    )
    # Keep the ask-graddie banner on-panel by shrinking height if needed.
    if ask is not None and options_block > body_h:
        avail = body_h - (n * opt_h + max(0, n - 1) * gap + helper_gap)
        if avail >= S(86):
            helper_h = avail
            helper_w = min(opt_w, int(round(helper_h * aspect)))
            helper_h = max(S(86), int(round(helper_w / aspect)))
            options_block = n * opt_h + max(0, n - 1) * gap + helper_gap + helper_h

    y = body_top
    spare = body_h - options_block
    if spare > 0:
        y = body_top + min(S(20), spare // 6)

    choice_rects = []
    for _ in quiz["choices"]:
        choice_rects.append(pygame.Rect(opt_x, y, opt_w, opt_h))
        y += opt_h + gap
    helper_rect = None
    if has_helper:
        helper_x = (LOGICAL_W - helper_w) // 2
        helper_rect = pygame.Rect(helper_x, y + helper_gap - gap, helper_w, helper_h)

    return {
        "panel": pygame.Rect(panel_x, panel_y, panel_w, panel_h),
        "header_h": header_h,
        "header_text_top": header_text_top,
        "text_w": text_w,
        "pad_x": pad_x,
        "title_font": title_font,
        "prompt_font": prompt_font,
        "option_font": option_font,
        "hint_font": hint_font,
        "prompt_lines": prompt_lines,
        "choice_rects": choice_rects,
        "helper_rect": helper_rect,
    }


def quiz_feedback_message_rect(assets, panel, feedback):
    """Hitbox for the post-answer feedback bubble (matches Screens.quiz draw).

    Returns (rect, lines, line_h, line_gap) or (None, [], 0, 0).
    """
    if not feedback:
        return None, [], 0, 0
    option_font = assets.font(_QUIZ_OPTION_SIZE)
    pad_x, pad_y = S(36), S(20)
    text_w = option_font.size(feedback)[0]
    max_inner = min(S(520), LOGICAL_W - S(80) - 2 * pad_x)
    inner_w = min(text_w, max_inner)
    lines = wrap_text(option_font, feedback, inner_w)
    line_h = option_font.get_height()
    line_gap = _QUIZ_LINE_GAP if len(lines) > 1 else 0
    total_h = line_h * len(lines) + line_gap * (len(lines) - 1)
    max_line_w = max(option_font.size(line)[0] for line in lines)
    msg_w = max_line_w + 2 * pad_x
    msg_h = total_h + 2 * pad_y
    msg_x = (LOGICAL_W - msg_w) // 2
    msg_y = panel.bottom + S(24)
    msg_y = min(msg_y, LOGICAL_H - msg_h - S(40))
    return pygame.Rect(msg_x, msg_y, msg_w, msg_h), lines, line_h, line_gap


class Button:
    def __init__(
        self,
        rect,
        text,
        color=PURPLE,
        image=None,
        overlay_text=False,
        text_color=WHITE,
        image_correct=None,
        image_wrong=None,
        image_hint=None,
        text_inset_left=0.0,
        text_inset_right=0.0,
    ):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.color = color
        self.highlight = False
        self.image = image
        self.image_correct = image_correct
        self.image_wrong = image_wrong
        self.image_hint = image_hint
        self.overlay_text = overlay_text
        self.text_color = text_color
        self.text_inset_left = float(text_inset_left)
        self.text_inset_right = float(text_inset_right)
        self.result = None  # None | "correct" | "wrong"

    def _hint_active(self):
        """Graddie/Right-Fit hint chrome (before answer feedback)."""
        return bool(self.highlight and self.result is None and self.image_hint is not None)

    def _active_image(self):
        if self.result == "correct" and self.image_correct is not None:
            return self.image_correct
        if self.result == "wrong" and self.image_wrong is not None:
            return self.image_wrong
        if self._hint_active():
            return self.image_hint
        if self.highlight and self.image_correct is not None:
            return self.image_correct
        return self.image

    def _label_color(self):
        if self.result == "correct" or self.result == "wrong":
            return WHITE
        if self._hint_active():
            return INK  # cream gold panel
        if self.highlight:
            return WHITE
        return self.text_color

    def _label_area(self):
        """Rect where overlay label is centered (full button or inset panel)."""
        pad_l = int(self.rect.w * self.text_inset_left)
        pad_r = int(self.rect.w * self.text_inset_right)
        if pad_l or pad_r:
            return pygame.Rect(
                self.rect.x + pad_l,
                self.rect.y,
                max(1, self.rect.w - pad_l - pad_r),
                self.rect.h,
            )
        return self.rect

    def _draw_hint_glow(self, surf, img):
        """Pulsing yellow aura around the hinted option (alpha + light scale)."""
        mask = pygame.mask.from_surface(img)
        silhouette = mask.to_surface(
            setcolor=(*_HINT_GLOW, 255), unsetcolor=(0, 0, 0, 0)
        ).convert_alpha()
        wave = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.0065)
        pulse_a = 0.40 + 0.55 * wave
        pulse_s = 1.0 + 0.055 * wave
        pad = S(16)
        glow = pygame.Surface(
            (img.get_width() + pad * 2, img.get_height() + pad * 2),
            pygame.SRCALPHA,
        )
        scale = 1.18 if RENDER_SCALE < 1.0 else 1.24
        big = pygame.transform.scale(
            silhouette,
            (
                max(1, int(img.get_width() * scale)),
                max(1, int(img.get_height() * scale)),
            ),
        )
        bx = (glow.get_width() - big.get_width()) // 2
        by = (glow.get_height() - big.get_height()) // 2
        if RENDER_SCALE < 1.0:
            # Alpha pulse only — skip per-frame smoothscale on web.
            layer = big.copy()
            layer.fill(
                (255, 255, 255, int(70 + 100 * wave)),
                special_flags=pygame.BLEND_RGBA_MULT,
            )
            glow.blit(layer, (bx, by))
        else:
            for dx, dy, a in (
                (0, 0, 88),
                (-4, 0, 55),
                (4, 0, 55),
                (0, -4, 55),
                (0, 4, 55),
                (-7, -3, 32),
                (7, -3, 32),
                (-7, 3, 32),
                (7, 3, 32),
            ):
                layer = big.copy()
                layer.fill((255, 255, 255, a), special_flags=pygame.BLEND_RGBA_MULT)
                glow.blit(layer, (bx + dx, by + dy))
            glow.fill(
                (255, 255, 255, int(255 * pulse_a)),
                special_flags=pygame.BLEND_RGBA_MULT,
            )
            if abs(pulse_s - 1.0) > 0.001:
                nw = max(1, int(glow.get_width() * pulse_s))
                nh = max(1, int(glow.get_height() * pulse_s))
                glow = pygame.transform.smoothscale(glow, (nw, nh))
        surf.blit(
            glow,
            (
                self.rect.x - (glow.get_width() - img.get_width()) // 2,
                self.rect.y - (glow.get_height() - img.get_height()) // 2,
            ),
        )

    def draw(self, surf, font):
        img = self._active_image()
        if img is not None:
            if img.get_width() != self.rect.w or img.get_height() != self.rect.h:
                img = pygame.transform.scale(img, (self.rect.w, self.rect.h))
            if self._hint_active():
                self._draw_hint_glow(surf, img)
            surf.blit(img, self.rect.topleft)
            if not self.overlay_text:
                return
        else:
            color = (16, 185, 129) if self.highlight or self.result == "correct" else self.color
            if self.result == "wrong":
                color = (220, 60, 60)
            radius = S(24)
            pygame.draw.rect(surf, color, self.rect, border_radius=radius)
            pygame.draw.rect(
                surf,
                WHITE,
                self.rect,
                S(4) if (self.highlight or self.result) else S(2),
                border_radius=radius,
            )
        area = self._label_area()
        wrap_pad = S(16) if (self.text_inset_left or self.text_inset_right) else S(48)
        lines = wrap_text(font, self.text, max(1, area.w - wrap_pad))
        line_gap = _QUIZ_LINE_GAP if len(lines) > 1 else 0
        total_h = sum(font.size(line)[1] for line in lines) + line_gap * (
            len(lines) - 1
        )
        y = area.centery - total_h // 2
        color = self._label_color()
        for line in lines:
            label = font.render(line, True, color)
            surf.blit(label, (area.centerx - label.get_width() // 2, y))
            y += label.get_height() + line_gap

    def hit(self, pos):
        return self.rect.collidepoint(pos)


class HUD:
    def draw(
        self,
        surf,
        assets,
        lives,
        coins,
        score,
        has_graddie,
        graddie_used,
        world_code="1",
        right_fit=False,
        money_boost=False,
        skill_boost=False,
    ):
        bar_h = S(168)
        bar = pygame.Surface((LOGICAL_W, bar_h), pygame.SRCALPHA)
        bar.fill((10, 20, 40, 120))
        surf.blit(bar, (0, 0))

        icon_h = assets.hud_heart.get_height()
        icon_y = (bar_h - icon_h) // 2
        value_size = S(24)
        label_size = S(18)
        text_y = icon_y + (icon_h - value_size) // 2

        surf.blit(assets.hud_heart, (S(24), icon_y))
        assets.draw_pixels(surf, "x{}".format(lives), S(116), text_y, value_size)

        surf.blit(assets.hud_coin, (S(240), icon_y))
        assets.draw_pixels(surf, "x{:02d}".format(coins), S(332), text_y, value_size)

        assets.draw_pixels(surf, "SCORE", S(500), S(32), label_size)
        assets.draw_pixels(surf, "{:06d}".format(max(0, score)), S(500), S(86), value_size)

        assets.draw_pixels(surf, "WORLD", S(780), S(32), label_size)
        assets.draw_pixels(surf, world_code, S(812), S(86), value_size)

        icon_x = S(940)
        if has_graddie:
            icon = assets.graddie[3] if not graddie_used else assets.graddie[0]
            scaled = pygame.transform.scale(icon, (icon_h, icon_h))
            gy = (bar_h - icon_h) // 2
            surf.blit(scaled, (icon_x, gy))
            icon_x += icon_h + S(8)
        if right_fit:
            assets.draw_pixels(surf, "RF", icon_x, text_y, S(16), GOLD)
            icon_x += S(52)
        if money_boost:
            assets.draw_pixels(surf, "$2", icon_x, text_y, S(16), GOLD)
            icon_x += S(52)
        if skill_boost:
            assets.draw_pixels(surf, "INV", icon_x, text_y, S(16), GOLD)


class Screens:
    def __init__(self, assets):
        self.assets = assets
        # Reuse World 1-1 drawing so the home screen matches play visuals.
        self.menu_world = World(assets, 0)
        self._menu_cam = pygame.Vector2(0, 0)
        self.start_btn = Button(
            (S(280), LOGICAL_H // 2 - S(85), S(520), S(170)),
            "START",
            image=assets.btn_start,
        )
        # Game-over image buttons; rects are laid out each frame in game_over().
        self.retry_btn = Button(
            (S(280), S(900), S(520), S(170)), "RETRY", image=assets.btn_retry
        )
        self.home_btn = Button(
            (S(280), S(1100), S(520), S(170)), "HOME", image=assets.btn_home
        )
        # Image-only CTA (pack_btn_cta.png); rect sized each frame in win().
        self.cta_btn = Button(
            (S(260), S(1500), S(560), S(110)),
            "",
            image=assets.btn_cta,
            overlay_text=False,
        )
        # Text buttons for daily leaderboard (win flow).
        self.submit_btn = Button(
            (S(200), S(1400), S(680), S(100)), "SUBMIT SCORE", color=PURPLE
        )
        self.confirm_nick_btn = Button(
            (S(200), S(1200), S(680), S(100)), "POST SCORE", color=PURPLE
        )
        self.board_back_btn = Button(
            (S(200), S(1600), S(320), S(90)), "BACK", color=PURPLE_DARK
        )
        self.skip_board_btn = Button(
            (S(560), S(1600), S(320), S(90)), "SKIP", color=PURPLE_DARK
        )
        self.nick_field_rect = pygame.Rect(0, 0, 0, 0)

    def menu(self, surf):
        self.menu_world.draw_background(surf, self._menu_cam)
        # Idle pose at World 1 spawn, bottom-aligned like Player draw in play.
        idle = self.assets.player["idle"]
        px = 3 * TILE
        py = GROUND_TOP - idle.get_height()
        surf.blit(idle, (px, py))
        title_y = S(70)
        blit_center(surf, self.assets.title, title_y)
        y = title_y + self.assets.title.get_height() + S(18)
        self.assets.draw_pixels_center(surf, "YOUR FUTURE. YOUR CHOICES.", y, S(20))
        y += S(72)
        self.assets.draw_pixels_center(surf, "WORLD 1-4", y, S(22))
        # Vertically centered; hitbox matches drawn rect.
        self.start_btn.rect.y = LOGICAL_H // 2 - self.start_btn.rect.h // 2
        self.start_btn.draw(surf, self.assets.font_lg)

    def world_intro(self, surf, code, name, subtitle):
        overlay = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        overlay.fill((10, 8, 28, 180))
        surf.blit(overlay, (0, 0))

        code_font = self.assets.font(S(58))
        name_font = self.assets.font(S(36))
        subtitle_font = self.assets.font(S(28))
        hint_font = self.assets.font(S(18))
        title_y = S(560)
        draw_text_center(surf, code_font, f"WORLD {code}", title_y, GOLD)
        name_y = title_y + code_font.get_height() + S(80)
        draw_text_center(surf, name_font, name, name_y, WHITE)
        subtitle_y = name_y + name_font.get_height() + S(72)
        draw_text_center(surf, subtitle_font, subtitle, subtitle_y, PURPLE_SOFT)
        hint_y = subtitle_y + subtitle_font.get_height() + S(72)
        draw_text_center(surf, hint_font, "Tap or press SPACE", hint_y, WHITE)

    def world_clear(self, surf, name, score, continue_btn):
        overlay = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        overlay.fill((10, 8, 28, 200))
        surf.blit(overlay, (0, 0))

        title_font = self.assets.font(S(58))
        name_font = self.assets.font(S(36))
        score_font = self.assets.font(S(28))
        title_y = S(560)
        draw_text_center(surf, title_font, "WORLD CLEARED", title_y, GOLD)
        name_y = title_y + title_font.get_height() + S(80)
        draw_text_center(surf, name_font, name, name_y, WHITE)
        score_y = name_y + name_font.get_height() + S(72)
        draw_text_center(surf, score_font, f"Score  {score}", score_y, PURPLE_SOFT)

        # Image CONTINUE button — aspect-correct like game-over buttons.
        cont_img = continue_btn.image or self.assets.btn_continue
        btn_w = S(520)
        btn_h = max(1, int(round(btn_w * cont_img.get_height() / cont_img.get_width())))
        btn_x = (LOGICAL_W - btn_w) // 2
        btn_y = score_y + score_font.get_height() + S(72)
        continue_btn.rect.update(btn_x, btn_y, btn_w, btn_h)
        continue_btn.draw(surf, self.assets.font_lg)

    def game_over(self, surf, score):
        overlay = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        overlay.fill((10, 8, 20, 210))
        surf.blit(overlay, (0, 0))

        # Title + score + stacked image buttons only (no panel / quote clutter).
        title_font = self.assets.font(S(96))
        score_font = self.assets.font(S(36))
        title_y = S(560)
        draw_text_center(surf, title_font, "GAME OVER", title_y, (230, 48, 48))
        score_y = title_y + title_font.get_height() + S(48)
        draw_text_center(surf, score_font, f"Score  {score}", score_y, GOLD)

        btn_w = S(520)
        retry_img = self.assets.btn_retry
        home_img = self.assets.btn_home
        retry_h = max(1, int(round(btn_w * retry_img.get_height() / retry_img.get_width())))
        home_h = max(1, int(round(btn_w * home_img.get_height() / home_img.get_width())))
        btn_x = (LOGICAL_W - btn_w) // 2
        gap = S(36)
        retry_y = score_y + score_font.get_height() + S(72)
        self.retry_btn.rect.update(btn_x, retry_y, btn_w, retry_h)
        self.home_btn.rect.update(btn_x, retry_y + retry_h + gap, btn_w, home_h)
        self.retry_btn.draw(surf, self.assets.font_lg)
        self.home_btn.draw(surf, self.assets.font_lg)

    def _win_bg(self, surf):
        surf.blit(self.assets.end_screen_bg, (0, 0))

    def _layout_cta(self, panel_bottom):
        cta_img = self.assets.btn_cta
        btn_w = S(560)
        btn_h = max(1, int(round(btn_w * cta_img.get_height() / cta_img.get_width())))
        btn_x = (LOGICAL_W - btn_w) // 2
        btn_y = min(panel_bottom + S(40), LOGICAL_H - btn_h - S(24))
        self.cta_btn.rect.update(btn_x, btn_y, btn_w, btn_h)
        return btn_y

    def win(self, surf, score, coins, smart, lives, mode="stats", nick="", status="", board=None):
        """Campaign win screen with optional nickname entry / daily leaderboard.

        mode: stats | nickname | board
        Days are UTC (shown on the board panel).
        """
        self._win_bg(surf)
        scale_fn = (
            pygame.transform.scale
            if RENDER_SCALE < 1.0
            else pygame.transform.smoothscale
        )
        btn_font = self.assets.font(S(26))

        if mode == "board":
            self._draw_leaderboard(surf, scale_fn, board, status)
            return

        if mode == "nickname":
            self._draw_nickname(surf, scale_fn, nick, status, btn_font)
            return

        # --- stats (default) ---
        stats_font = self.assets.font(S(32))
        score_value_font = self.assets.font(S(88))
        line_gap = S(50)
        score_stack_gap = S(14)
        pad_x, pad_y = S(56), S(44)

        score_label = "Your Score:"
        score_value = str(score)
        other_lines = [
            f"Grad Coins: {coins}",
            f"Smart Decision: {smart}",
            f"Lives Remaining: {lives} / 3",
        ]
        max_tw = max(
            stats_font.size(score_label)[0],
            score_value_font.size(score_value)[0],
            *(stats_font.size(line)[0] for line in other_lines),
        )
        score_block_h = (
            stats_font.get_height()
            + score_stack_gap
            + score_value_font.get_height()
        )
        block_h = score_block_h + line_gap + len(other_lines) * line_gap
        pw = max_tw + pad_x * 2
        ph = block_h + pad_y * 2
        panel = scale_fn(self.assets.win_stats_panel, (pw, ph))
        panel_x = (LOGICAL_W - pw) // 2
        # Raise panel so submit + CTA fit below.
        panel_y = max(S(80), (LOGICAL_H - ph) // 2 - S(160))
        surf.blit(panel, (panel_x, panel_y))

        y = panel_y + pad_y
        draw_text_center(surf, stats_font, score_label, y, INK)
        y += stats_font.get_height() + score_stack_gap
        draw_text_center(surf, score_value_font, score_value, y, INK)
        y += score_value_font.get_height() + line_gap
        for line in other_lines:
            draw_text_center(surf, stats_font, line, y, INK)
            y += line_gap

        submit_w, submit_h = S(680), S(100)
        submit_x = (LOGICAL_W - submit_w) // 2
        submit_y = panel_y + ph + S(48)
        self.submit_btn.rect.update(submit_x, submit_y, submit_w, submit_h)
        self.submit_btn.draw(surf, btn_font)

        self._layout_cta(self.submit_btn.rect.bottom + S(36))
        self.cta_btn.draw(surf, self.assets.font_lg)

    def _draw_nickname(self, surf, scale_fn, nick, status, btn_font):
        title_font = self.assets.font(S(36))
        body_font = self.assets.font(S(24))
        pad_x, pad_y = S(48), S(40)
        lines = [
            "Anonymous nickname",
            "3-16 letters / numbers",
            "Daily board (UTC)",
        ]
        field_h = S(88)
        inner_w = S(820)
        pw = inner_w + pad_x * 2
        ph = pad_y * 2 + title_font.get_height() + S(24) + body_font.get_height() * 3 + S(28) + field_h + S(24) + S(100)
        panel = scale_fn(self.assets.win_stats_panel, (pw, ph))
        panel_x = (LOGICAL_W - pw) // 2
        panel_y = max(S(120), (LOGICAL_H - ph) // 2 - S(80))
        surf.blit(panel, (panel_x, panel_y))

        y = panel_y + pad_y
        draw_text_center(surf, title_font, "JOIN TODAY'S BOARD", y, INK)
        y += title_font.get_height() + S(24)
        for line in lines:
            draw_text_center(surf, body_font, line, y, INK)
            y += body_font.get_height() + S(8)

        field = pygame.Rect(panel_x + pad_x, y + S(12), inner_w, field_h)
        pygame.draw.rect(surf, WHITE, field, border_radius=S(16))
        pygame.draw.rect(surf, PURPLE, field, S(4), border_radius=S(16))
        shown = str(nick or "") + "|"
        nick_img = body_font.render(shown[:22], True, INK)
        surf.blit(
            nick_img,
            (field.x + S(24), field.centery - nick_img.get_height() // 2),
        )
        self.nick_field_rect = field
        y = field.bottom + S(28)

        status_text = _status_line(status, 40)
        if status_text:
            err_font = self.assets.font(S(20))
            draw_text_center(surf, err_font, status_text, y, (180, 40, 40))
            y += err_font.get_height() + S(16)

        bw, bh = S(680), S(100)
        self.confirm_nick_btn.rect.update((LOGICAL_W - bw) // 2, y, bw, bh)
        self.confirm_nick_btn.draw(surf, btn_font)

        self._layout_cta(self.confirm_nick_btn.rect.bottom + S(48))
        self.cta_btn.draw(surf, self.assets.font_lg)

    def _draw_leaderboard(self, surf, scale_fn, board, status):
        title_font = self.assets.font(S(34))
        row_font = self.assets.font(S(20))
        small = self.assets.font(S(16))
        pad_x, pad_y = S(36), S(36)
        day = (board or {}).get("day_key", "UTC")
        top = list((board or {}).get("top") or [])
        you = (board or {}).get("you")
        rows = top[:10]
        # Ensure "you" appears even outside top 10
        you_in_top = False
        if you:
            for r in rows:
                if r.get("player_id") and r.get("player_id") == you.get("player_id"):
                    you_in_top = True
                    r["_is_you"] = True
                    break
            if not you_in_top:
                you = dict(you)
                you["_is_you"] = True
                you["_separator"] = True

        pw = S(960)
        row_h = S(44)
        header_h = title_font.get_height() + small.get_height() + S(36)
        extra = row_h + S(16) if (you and not you_in_top) else 0
        ph = pad_y * 2 + header_h + row_h * max(1, len(rows)) + extra + S(20)
        ph = min(ph, LOGICAL_H - S(280))
        panel = scale_fn(self.assets.win_stats_panel, (pw, ph))
        panel_x = (LOGICAL_W - pw) // 2
        panel_y = S(72)
        surf.blit(panel, (panel_x, panel_y))

        y = panel_y + pad_y
        draw_text_center(surf, title_font, "DAILY TOP 10", y, INK)
        y += title_font.get_height() + S(8)
        draw_text_center(surf, small, f"UTC day  {day}", y, PURPLE_DARK)
        y += small.get_height() + S(20)

        def draw_row(entry, yy, highlight=False):
            rank = entry.get("rank", "?")
            nick = str(entry.get("nickname", "?"))[:14]
            sc = entry.get("score", 0)
            sm = entry.get("smart", 0)
            label = f"{rank:>2}  {nick:<14}  {sc:>5}  S{sm}"
            color = PURPLE if highlight else INK
            img = row_font.render(label, True, color)
            surf.blit(img, (panel_x + pad_x, yy))
            return yy + row_h

        for entry in rows:
            y = draw_row(entry, y, highlight=bool(entry.get("_is_you")))

        if you and not you_in_top:
            y += S(8)
            draw_text_center(surf, small, "— you —", y, PURPLE_DARK)
            y += small.get_height() + S(4)
            draw_row(you, y, highlight=True)

        status_text = _status_line(status, 48)
        if status_text:
            draw_text_center(
                surf,
                small,
                status_text,
                panel_y + ph - pad_y - small.get_height(),
                (180, 40, 40),
            )

        # Bottom actions
        bw, bh = S(320), S(90)
        gap = S(40)
        total = bw * 2 + gap
        bx = (LOGICAL_W - total) // 2
        by = panel_y + ph + S(28)
        self.board_back_btn.rect.update(bx, by, bw, bh)
        self.skip_board_btn.rect.update(bx + bw + gap, by, bw, bh)
        self.board_back_btn.text = "STATS"
        self.skip_board_btn.text = "CTA"
        self.board_back_btn.draw(surf, self.assets.font(S(22)))
        self.skip_board_btn.draw(surf, self.assets.font(S(22)))

        self._layout_cta(self.board_back_btn.rect.bottom + S(24))
        self.cta_btn.draw(surf, self.assets.font_lg)

    def quiz(self, surf, quiz, buttons, graddie_btn, feedback, used_graddie):
        overlay = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        overlay.fill((10, 6, 30, 200))
        surf.blit(overlay, (0, 0))

        layout = quiz_layout(self.assets, quiz, has_helper=graddie_btn is not None)
        panel = layout["panel"]
        scale_fn = (
            pygame.transform.scale
            if RENDER_SCALE < 1.0
            else pygame.transform.smoothscale
        )
        panel_img = scale_fn(self.assets.quiz_panel, (panel.w, panel.h))
        surf.blit(panel_img, panel.topleft)

        # Title + question both live in the cream header (dark ink).
        y = layout["header_text_top"]
        title_img = layout["title_font"].render(quiz["title"], True, INK)
        surf.blit(title_img, ((LOGICAL_W - title_img.get_width()) // 2, y))
        y += title_img.get_height() + S(12)
        for line in layout["prompt_lines"]:
            img = layout["prompt_font"].render(line, True, INK)
            surf.blit(img, ((LOGICAL_W - img.get_width()) // 2, y))
            y += img.get_height() + _QUIZ_LINE_GAP

        option_font = layout["option_font"]
        hint_font = layout["hint_font"]
        for btn in buttons:
            btn.draw(surf, option_font)

        if graddie_btn is not None:
            graddie_btn.draw(surf, option_font)
            hint = "Highlights the right option — one use"
            if used_graddie:
                hint = "Graddie highlighted the best option"
            img = hint_font.render(hint, True, WHITE)
            hint_y = graddie_btn.rect.bottom + S(14)
            surf.blit(img, (LOGICAL_W // 2 - img.get_width() // 2, hint_y))
        elif used_graddie:
            hint = "Graddie highlighted the best option"
            img = hint_font.render(hint, True, WHITE)
            surf.blit(
                img,
                (
                    LOGICAL_W // 2 - img.get_width() // 2,
                    panel.bottom - S(48),
                ),
            )

        if feedback:
            msg_rect, lines, line_h, line_gap = quiz_feedback_message_rect(
                self.assets, panel, feedback
            )
            total_h = line_h * len(lines) + line_gap * (len(lines) - 1)
            msg = pygame.transform.scale(
                self.assets.quiz_message, (msg_rect.w, msg_rect.h)
            )
            surf.blit(msg, msg_rect.topleft)
            fy = msg_rect.y + (msg_rect.h - total_h) // 2
            for line in lines:
                img = option_font.render(line, True, INK)
                surf.blit(img, (msg_rect.x + (msg_rect.w - img.get_width()) // 2, fy))
                fy += line_h + line_gap
