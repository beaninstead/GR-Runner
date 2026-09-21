import asyncio
import math

import pygame

from future_run import leaderboard as lb
from future_run.constants import (
    COIN_VALUE,
    CTA_URL,
    GOLD,
    GROUND_TOP,
    INK,
    INVINCIBLE_FRAMES,
    LOGICAL_H,
    LOGICAL_W,
    PLAYER_H,
    QUIZ_FEEDBACK_FRAMES,
    RENDER_SCALE,
    S,
    START_LIVES,
    TILE,
    WHITE,
    WORLD4_INVINCIBLE_FRAMES,
    WORLD_INTRO_FRAMES,
)
from future_run.levels import LEVELS, QUIZZES
from future_run.player import Player
from future_run.touch import TouchControls
from future_run.ui import (
    ASK_GRADDIE_TEXT_LEFT,
    ASK_GRADDIE_TEXT_RIGHT,
    Button,
    HUD,
    Screens,
    quiz_feedback_message_rect,
    quiz_layout,
)
from future_run.web import (
    IS_WEB,
    consume_nickname_html_enter,
    consume_nickname_html_escape,
    debug_hotkeys_allowed,
    focus_nickname_html_input,
    hide_nickname_html_input,
    open_url,
    poll_nickname_html_input,
    show_nickname_html_input,
)
from future_run.world import World


class Camera:
    def __init__(self):
        self.x = 0
        self.y = 0

    def follow(self, player, world_right):
        self.x = player.rect.centerx - int(LOGICAL_W * 0.32)
        self.y = player.rect.bottom - int(LOGICAL_H * 0.78)
        self.x = max(0, min(self.x, world_right - LOGICAL_W))
        self.y = max(0, min(self.y, max(0, GROUND_TOP + 3 * TILE - LOGICAL_H)))


class FutureRun:
    def __init__(self, window):
        self.window = window
        self.logical = pygame.Surface((LOGICAL_W, LOGICAL_H))
        from future_run.assets import Assets

        self.assets = Assets()
        self.hud = HUD()
        self.screens = Screens(self.assets)
        self.camera = Camera()
        self.touch = TouchControls()
        self.state = "menu"
        self.feedback_timer = 0
        self.pending_fail = False
        self.pending_fail_life = -1
        self._eat_pointer = False
        self.level_index = 0
        self.intro_timer = 0
        self.reset_campaign()
        # Win-screen leaderboard (anonymous nicknames, UTC daily).
        self.win_mode = "stats"  # stats | nickname | board
        self.win_nickname = lb.get_saved_nickname()
        self.win_status = ""
        self.win_board = None
        self._lb_busy = False
        self._text_input_active = False

    def reset_campaign(self):
        self.level_index = 0
        self.lives = START_LIVES
        self.coin_count = 0
        self.decision_points = 0
        self.smart = 0
        self.deaths = 0
        self.has_graddie = False
        self.graddie_used = False
        self.has_right_fit = False
        self.right_fit_used = False
        self.money_boost = False
        self.start_level(0)

    def reset_world(self):
        """Retry current world after running out of lives, keeping 2/3 of score."""
        retained = (self.score * 2) // 3
        self.lives = START_LIVES
        # Lose 1/3 of accumulated score (retain ~2/3); campaign Start still zeros via reset_campaign.
        self.coin_count = (self.coin_count * 2) // 3
        self.decision_points = (self.decision_points * 2) // 3
        self.deaths = (self.deaths * 2) // 3
        # Flooring each component can drift a few points; nudge decisions to hit floor(score*2/3).
        self.decision_points += retained - self.score
        self.smart = 0
        self.has_graddie = False
        self.graddie_used = False
        self.has_right_fit = False
        self.right_fit_used = False
        self.money_boost = False
        self.start_level(self.level_index)

    def _player_frames_for_level(self, index):
        """Per-world player sheets: W2/W3 passport suit, W4 trophy suit."""
        code = LEVELS[index]["code"]
        if index == 1 or code == "2-1":
            return self.assets.player_world2
        if index == 2 or code == "3-1":
            return self.assets.player_world3
        if index == 3 or code == "4-1":
            return self.assets.player_world4
        return self.assets.player

    def start_level(self, index):
        self.level_index = index
        self.world = World(self.assets, index)
        frames = self._player_frames_for_level(index)
        self.player = Player(frames, 3 * TILE, GROUND_TOP - PLAYER_H)
        self.active_quiz = None
        self.quiz_buttons = []
        self.graddie_btn = None
        self.feedback = ""
        self.pending_fail = False
        self.invincible_granted = False
        self.camera.follow(self.player, self.world.world_right)
        self.intro_timer = WORLD_INTRO_FRAMES
        self.touch.clear()
        if self.state not in ("menu", "gameover", "win"):
            self.state = "intro"

    @property
    def score(self):
        return self.coin_count * COIN_VALUE + self.decision_points - self.deaths

    @property
    def level_cfg(self):
        return LEVELS[self.level_index]

    def lose_life(self, snap=True, amount=1):
        if amount == 0:
            return
        if (self.player.invincible > 0 or self.player.skill_boost > 0) and snap:
            return
        self.lives -= amount
        self.deaths += amount
        if snap:
            self.player.snap_safe()
        else:
            self.player.invincible = max(self.player.invincible, INVINCIBLE_FRAMES)
        if self.lives <= 0:
            self.lives = 0
            self.touch.clear()
            self.state = "gameover"

    def open_quiz(self, which):
        # Finger/mouse up may be swallowed by the quiz UI, so drop held pads now.
        self.touch.clear()
        quiz = QUIZZES[which]
        self.active_quiz = quiz
        self.feedback = ""
        self.pending_fail = False
        self.state = "quiz"
        self.quiz_buttons = []
        can_help = (self.has_graddie and not self.graddie_used) or (
            self.has_right_fit and not self.right_fit_used
        )
        layout = quiz_layout(self.assets, quiz, has_helper=can_help)
        letters = "ABC"
        for i, text in enumerate(quiz["choices"]):
            self.quiz_buttons.append(
                Button(
                    layout["choice_rects"][i],
                    f"{letters[i]}.  {text}",
                    image=self.assets.quiz_option,
                    image_correct=self.assets.quiz_option_correct,
                    image_wrong=self.assets.quiz_option_wrong,
                    image_hint=self.assets.quiz_option_hint,
                    overlay_text=True,
                    text_color=INK,
                )
            )
        self.graddie_btn = None
        if can_help and layout["helper_rect"] is not None:
            label = (
                "Ask Graddie"
                if (self.has_graddie and not self.graddie_used)
                else "Use Right-Fit"
            )
            self.graddie_btn = Button(
                layout["helper_rect"],
                label,
                image=self.assets.ask_graddie,
                overlay_text=True,
                text_color=INK,
                text_inset_left=ASK_GRADDIE_TEXT_LEFT,
                text_inset_right=ASK_GRADDIE_TEXT_RIGHT,
            )

    def use_helper(self):
        if not self.active_quiz:
            return
        used = False
        if self.has_graddie and not self.graddie_used:
            self.graddie_used = True
            used = True
        elif self.has_right_fit and not self.right_fit_used:
            self.right_fit_used = True
            used = True
        if not used:
            return
        correct = self.active_quiz["correct"]
        self.quiz_buttons[correct].highlight = True
        self.graddie_btn = None

    def answer(self, index):
        if self.feedback or not self.active_quiz:
            return
        quiz = self.active_quiz
        correct = quiz["correct"]
        if index == correct:
            points = quiz["points"]
            if self.money_boost:
                points *= 2
                self.money_boost = False
                self.feedback = f"Nice. +{points}  (Money Boost!)"
            else:
                self.feedback = f"Nice. +{points}  Future Points"
            self.decision_points += points
            self.smart += 1
            self.pending_fail = False
            self.pending_fail_life = 0
            self.quiz_buttons[index].result = "correct"
            self._grant_reward(quiz.get("reward"), points)
        else:
            self.feedback = quiz["fail"]
            self.pending_fail = True
            self.pending_fail_life = int(quiz.get("life_on_fail", -1) or 0)
            self.quiz_buttons[index].result = "wrong"
            self.quiz_buttons[correct].result = "correct"
        self.feedback_timer = QUIZ_FEEDBACK_FRAMES

    def _grant_reward(self, reward, points):
        if not reward:
            return
        if reward == "right_fit":
            self.has_right_fit = True
            self.right_fit_used = False
            self.feedback = f"Nice. +{points}  Right-Fit unlocked!"
        elif reward == "money_boost":
            self.money_boost = True
            self.feedback = f"Nice. +{points}  Money Boost ready!"
        elif reward == "community":
            self.lives += 1
            self.feedback = f"Nice. +{points}  +1 Life!"
        elif reward == "skill_boost":
            self.player.grant_skill_boost()
            self.feedback = f"Nice. +{points}  Invincible!"
        elif reward == "future_ready":
            self.feedback = f"Nice. +{points}  Future Ready!"

    def finish_quiz(self):
        if self.pending_fail:
            self.lose_life(snap=False, amount=abs(self.pending_fail_life) if self.pending_fail_life else 0)
        self.active_quiz = None
        self.feedback = ""
        if self.state != "gameover":
            self.state = "play"
        # Safety net: ensure no stale hold survives quiz → play.
        self.touch.clear()

    def advance_world(self):
        self.touch.clear()
        next_i = self.level_index + 1
        if next_i >= len(LEVELS):
            self.win_mode = "stats"
            self.win_status = ""
            self.win_board = None
            self._lb_busy = False
            self.win_nickname = lb.get_saved_nickname()
            self._stop_text_input()
            self.state = "win"
            return
        self.state = "world_clear"
        self.clear_continue = Button(
            (S(280), S(1200), S(520), S(140)),
            "",
            image=self.assets.btn_continue,
            overlay_text=False,
        )
        self._pending_next = next_i

    def _debug_jump_to_win(self):
        """F9 (local only): open win/leaderboard flow with sample campaign stats."""
        self.touch.clear()
        # Plausible end-of-campaign numbers so SUBMIT SCORE → nickname → board works.
        self.coin_count = 48
        self.decision_points = 720
        self.deaths = 1
        self.smart = 8
        self.lives = 2
        self.win_mode = "stats"
        self.win_status = ""
        self.win_board = None
        self._lb_busy = False
        self.win_nickname = lb.get_saved_nickname()
        self._stop_text_input()
        self.state = "win"

    def continue_next_world(self):
        self.start_level(self._pending_next)
        self.state = "intro"

    def _start_text_input(self):
        if self._text_input_active:
            return
        self._text_input_active = True
        if IS_WEB:
            # Mobile Safari/Chrome need a focused DOM <input> for soft keyboard.
            show_nickname_html_input(self.win_nickname or "")
        try:
            pygame.key.start_text_input()
        except Exception:
            pass

    def _stop_text_input(self):
        if not self._text_input_active:
            return
        self._text_input_active = False
        if IS_WEB:
            hide_nickname_html_input()
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass

    def _sync_web_nickname_input(self):
        """Pull HTML input value / Enter / Escape into win nickname state."""
        if not (IS_WEB and self._text_input_active and self.win_mode == "nickname"):
            return
        val = poll_nickname_html_input()
        if val is not None and val != self.win_nickname:
            self.win_nickname = val
            self.win_status = ""
        if consume_nickname_html_enter():
            self._submit_to_leaderboard()
            return
        if consume_nickname_html_escape():
            self.win_mode = "stats"
            self._stop_text_input()

    def _open_nickname(self):
        self.win_mode = "nickname"
        self.win_status = ""
        if not self.win_nickname:
            self.win_nickname = lb.get_saved_nickname()
        self._start_text_input()

    def _submit_to_leaderboard(self):
        if self._lb_busy:
            return
        ok, msg = lb.validate_nickname_client(self.win_nickname)
        if not ok:
            self.win_status = msg
            return
        self.win_nickname = msg
        lb.save_nickname(self.win_nickname)
        self.win_status = "Posting…"
        self._lb_busy = True
        payload = lb.build_submit_payload(
            self.win_nickname,
            self.score,
            self.smart,
            self.coin_count,
            self.lives,
        )

        async def _run():
            try:
                success, data = await lb.submit_score_async(payload)
                if success:
                    self.win_board = data
                    self.win_status = ""
                    self.win_mode = "board"
                    self._stop_text_input()
                else:
                    self.win_status = lb.error_message(data)
            except Exception as e:
                self.win_status = lb.error_message(str(e), "Could not reach leaderboard")
            finally:
                self._lb_busy = False

        try:
            loop = asyncio.get_event_loop()
            loop.create_task(_run())
        except Exception:
            # Fallback sync (desktop)
            success, data = lb.submit_score_sync(payload)
            self._lb_busy = False
            if success:
                self.win_board = data
                self.win_status = ""
                self.win_mode = "board"
                self._stop_text_input()
            else:
                self.win_status = lb.error_message(data)

    def _handle_win_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            pos = self._logical_pos(event.pos)
            if self.screens.cta_btn.hit(pos):
                open_url(CTA_URL)
                return
            if self.win_mode == "stats" and self.screens.submit_btn.hit(pos):
                self._open_nickname()
                return
            if self.win_mode == "nickname":
                if self.screens.confirm_nick_btn.hit(pos):
                    self._submit_to_leaderboard()
                    return
                # Re-focus HTML input so the soft keyboard can reopen after blur.
                if IS_WEB:
                    focus_nickname_html_input()
                return
            if self.win_mode == "board":
                if self.screens.board_back_btn.hit(pos):
                    self.win_mode = "stats"
                    return
                if self.screens.skip_board_btn.hit(pos):
                    open_url(CTA_URL)
                    return
            return

        if self.win_mode == "nickname":
            # On web the HTML <input> is the source of truth (avoids double chars
            # from TEXTINPUT + value poll). Desktop still uses pygame IME events.
            if IS_WEB and self._text_input_active:
                if event.type == pygame.KEYDOWN and event.key in (
                    pygame.K_RETURN,
                    pygame.K_KP_ENTER,
                ):
                    self._submit_to_leaderboard()
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.win_mode = "stats"
                    self._stop_text_input()
                return
            if event.type == pygame.TEXTINPUT:
                ch = event.text
                if ch and len(self.win_nickname) < 16:
                    self.win_nickname += str(ch)
                    self.win_status = ""
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE:
                    self.win_nickname = self.win_nickname[:-1]
                    self.win_status = ""
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._submit_to_leaderboard()
                elif event.key == pygame.K_ESCAPE:
                    self.win_mode = "stats"
                    self._stop_text_input()
                return

        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.win_mode == "stats":
                self._open_nickname()
            elif self.win_mode == "board":
                open_url(CTA_URL)

    def _maybe_grant_world4_invincible(self):
        """After World 4's third pit, grant long-lasting invincibility once."""
        if self.invincible_granted:
            return
        if not (self.level_index == 3 or self.level_cfg.get("id") == 4):
            return
        pits = self.world.pits or []
        if len(pits) < 3:
            return
        end_col = pits[2][1]
        if self.player.rect.centerx <= end_col * TILE:
            return
        self.invincible_granted = True
        self.player.invincible = max(self.player.invincible, WORLD4_INVINCIBLE_FRAMES)
        # Gold glow / INVINCIBLE label uses the skill_boost FX path.
        self.player.grant_skill_boost(WORLD4_INVINCIBLE_FRAMES)

    def update_play(self, dt=1.0):
        keys = pygame.key.get_pressed()
        self.player.handle_input(keys, self.touch, dt=dt)
        if self.touch.consume_jump():
            self.player.jump()
        self.player.physics(self.world.ground, self.world.solid_rects(), dt=dt)
        self.world.update(dt)
        self.camera.follow(self.player, self.world.world_right)
        self._maybe_grant_world4_invincible()

        if self.player.fell_in_pit(self.world.ground):
            self.lose_life(snap=True)

        if self.player.invincible <= 0 and self.player.skill_boost <= 0:
            for book in self.world.books:
                if self.player.rect.colliderect(book.rect):
                    if (
                        self.player.rect.bottom - book.rect.top < TILE // 2 + 24
                        and self.player.vel_y >= 0
                    ):
                        self.player.rect.bottom = book.rect.top
                        self.player.vel_y = 0
                        self.player.on_ground = True
                        self.player.last_safe.update(self.player.rect.x, self.player.rect.y)
                    else:
                        self.lose_life(snap=True)
                    break
            for phone in self.world.phones:
                if self.player.rect.colliderect(phone.rect):
                    self.lose_life(snap=True)
                    break
            for haz in self.world.falling:
                if self.player.rect.colliderect(haz.rect):
                    self.lose_life(snap=True)
                    break

        for coin in self.world.coins:
            if coin.alive and self.player.rect.colliderect(coin.rect):
                coin.alive = False
                self.coin_count += 1

        for g in self.world.graddies:
            if g.alive and self.player.rect.colliderect(g.rect):
                g.alive = False
                self.has_graddie = True
                self.graddie_used = False

        for trig in self.world.triggers:
            if trig.used:
                continue
            if self.player.rect.colliderect(trig.rect):
                trig.used = True
                if trig.kind == "quiz":
                    self.open_quiz(trig.payload)
                elif trig.kind == "goal":
                    self.advance_world()

    def draw_play(self):
        self.world.draw_background(self.logical, self.camera)
        self.world.draw_entities(self.logical, self.camera, self.assets.font_sm)
        img = self.player.image()
        # Skip blink while skill_boost gold glow is active (e.g. World 4 grant).
        show = (
            self.player.skill_boost > 0
            or self.player.invincible <= 0
            or (int(self.player.invincible) // 4) % 2 == 0
        )
        if show:
            draw_y = self.player.rect.bottom - img.get_height()
            px = self.player.rect.x - self.camera.x
            py = draw_y - self.camera.y
            if self.player.skill_boost > 0:
                self._draw_skill_boost_fx(img, px, py)
            self.logical.blit(img, (px, py))
        self.hud.draw(
            self.logical,
            self.assets,
            self.lives,
            self.coin_count,
            self.score,
            self.has_graddie,
            self.graddie_used,
            world_code=str(self.level_cfg["id"]),
            right_fit=self.has_right_fit and not self.right_fit_used,
            money_boost=self.money_boost,
            skill_boost=self.player.skill_boost > 0,
        )

    def _draw_skill_boost_fx(self, img, x, y):
        """Sprite-shaped pulsing gold aura + floating INVINCIBLE label."""
        mask = pygame.mask.from_surface(img)
        silhouette = mask.to_surface(
            setcolor=(*GOLD, 255), unsetcolor=(0, 0, 0, 0)
        ).convert_alpha()
        if RENDER_SCALE < 1.0:
            # Cheap static tint — no per-frame smoothscale on web.
            pad = S(12)
            glow = pygame.Surface(
                (img.get_width() + pad * 2, img.get_height() + pad * 2),
                pygame.SRCALPHA,
            )
            big = pygame.transform.scale(
                silhouette,
                (int(img.get_width() * 1.16), int(img.get_height() * 1.16)),
            )
            bx = (glow.get_width() - big.get_width()) // 2
            by = (glow.get_height() - big.get_height()) // 2
            layer = big.copy()
            layer.fill((255, 255, 255, 90), special_flags=pygame.BLEND_RGBA_MULT)
            glow.blit(layer, (bx, by))
            self.logical.blit(
                glow,
                (
                    x - (glow.get_width() - img.get_width()) // 2,
                    y - (glow.get_height() - img.get_height()) // 2,
                ),
            )
        else:
            wave = 0.5 + 0.5 * math.sin(self.player.timer * 0.18)
            pulse_a = 0.45 + 0.55 * wave
            pulse_s = 1.0 + 0.07 * wave
            pad = 22
            glow = pygame.Surface(
                (img.get_width() + pad * 2, img.get_height() + pad * 2),
                pygame.SRCALPHA,
            )
            big = pygame.transform.smoothscale(
                silhouette,
                (int(img.get_width() * 1.24), int(img.get_height() * 1.24)),
            )
            bx = (glow.get_width() - big.get_width()) // 2
            by = (glow.get_height() - big.get_height()) // 2
            for dx, dy, a in (
                (0, 0, 80),
                (-5, 0, 55),
                (5, 0, 55),
                (0, -5, 55),
                (0, 5, 55),
                (-8, -4, 35),
                (8, -4, 35),
                (-8, 4, 35),
                (8, 4, 35),
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
            self.logical.blit(
                glow,
                (
                    x - (glow.get_width() - img.get_width()) // 2,
                    y - (glow.get_height() - img.get_height()) // 2,
                ),
            )

        wave = 0.5 + 0.5 * math.sin(self.player.timer * 0.18)
        font = self.assets.font(S(18))
        label = "INVINCIBLE"
        text = font.render(label, True, GOLD)
        outline = font.render(label, True, WHITE)
        text_a = int(160 + 95 * wave)
        tx = x + img.get_width() // 2 - text.get_width() // 2
        ty = y - text.get_height() - S(18) - int(S(4) * wave)

        glow_layer = pygame.Surface(
            (text.get_width() + S(24), text.get_height() + S(24)), pygame.SRCALPHA
        )
        for dx, dy in (
            (-3, 0),
            (3, 0),
            (0, -3),
            (0, 3),
            (-2, -2),
            (2, -2),
            (-2, 2),
            (2, 2),
        ):
            glow_layer.blit(outline, (S(12) + dx, S(12) + dy))
        tinted = glow_layer.copy()
        tinted.fill((*GOLD, text_a), special_flags=pygame.BLEND_RGBA_MULT)
        self.logical.blit(tinted, (tx - S(12), ty - S(12)))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.logical.blit(outline, (tx + dx, ty + dy))
        main = text.copy()
        main.set_alpha(min(255, text_a + 40))
        self.logical.blit(main, (tx, ty))

    def handle_event(self, event):
        if self._eat_pointer:
            if event.type in (pygame.MOUSEBUTTONUP, pygame.FINGERUP):
                self._eat_pointer = False
                self.touch.clear()
            elif event.type in (
                pygame.MOUSEBUTTONDOWN,
                pygame.FINGERDOWN,
                pygame.MOUSEMOTION,
                pygame.FINGERMOTION,
            ):
                return
        if self.state == "play":
            self.touch.handle_event(event, self._logical_pos, self._finger_logical)

        # F9: local-only jump to campaign win / leaderboard (desktop or localhost web).
        if (
            event.type == pygame.KEYDOWN
            and event.key == pygame.K_F9
            and debug_hotkeys_allowed()
        ):
            self._debug_jump_to_win()
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.state == "play":
                self.touch.clear()
                self.state = "pause"
            elif self.state == "pause":
                self.touch.clear()
                self.state = "play"
            return

        if self.state == "menu":
            if event.type == pygame.MOUSEBUTTONDOWN and self.screens.start_btn.hit(
                self._logical_pos(event.pos)
            ):
                self.touch.clear()
                self.reset_campaign()
                self.state = "intro"
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.touch.clear()
                self.reset_campaign()
                self.state = "intro"
        elif self.state == "intro":
            if event.type == pygame.KEYDOWN and event.key in (
                pygame.K_RETURN,
                pygame.K_SPACE,
            ):
                self.intro_timer = 0
                self.touch.clear()
                self.state = "play"
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.intro_timer = 0
                self.touch.clear()
                self.state = "play"
        elif self.state == "world_clear":
            if event.type == pygame.MOUSEBUTTONDOWN and self.clear_continue.hit(
                self._logical_pos(event.pos)
            ):
                self.continue_next_world()
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.continue_next_world()
        elif self.state == "gameover":
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = self._logical_pos(event.pos)
                if self.screens.retry_btn.hit(pos):
                    self.reset_world()
                    self.state = "intro"
                elif self.screens.home_btn.hit(pos):
                    self.reset_campaign()
                    self.state = "menu"
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_r):
                self.reset_world()
                self.state = "intro"
        elif self.state == "win":
            self._handle_win_event(event)
        elif self.state == "quiz":
            if self.feedback:
                # Early dismiss: tap/click outside quiz panel + feedback bubble.
                pos = None
                if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
                    pos = self._logical_pos(event.pos)
                elif event.type == pygame.FINGERDOWN:
                    pos = self._finger_logical(event)
                if pos is not None and self.active_quiz:
                    layout = quiz_layout(
                        self.assets,
                        self.active_quiz,
                        has_helper=self.graddie_btn is not None,
                    )
                    panel = layout["panel"]
                    msg, _, _, _ = quiz_feedback_message_rect(
                        self.assets, panel, self.feedback
                    )
                    if not panel.collidepoint(pos) and (
                        msg is None or not msg.collidepoint(pos)
                    ):
                        self.finish_quiz()
                        # Swallow matching up / duplicate pointer so play pads
                        # don't fire from the same outside tap.
                        self._eat_pointer = True
                return
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_1, pygame.K_a):
                    self.answer(0)
                elif event.key in (pygame.K_2, pygame.K_b):
                    self.answer(1)
                elif event.key in (pygame.K_3, pygame.K_c):
                    self.answer(2)
                elif event.key == pygame.K_g:
                    self.use_helper()
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = self._logical_pos(event.pos)
                if self.graddie_btn and self.graddie_btn.hit(pos):
                    self.use_helper()
                    return
                for i, btn in enumerate(self.quiz_buttons):
                    if btn.hit(pos):
                        self.answer(i)
                        break
        elif self.state == "play":
            if event.type == pygame.KEYDOWN and event.key in (
                pygame.K_SPACE,
                pygame.K_UP,
                pygame.K_w,
            ):
                self.player.jump()

    def _logical_pos(self, pos):
        ww, wh = self.window.get_size()
        scale = min(ww / LOGICAL_W, wh / LOGICAL_H)
        ox = (ww - LOGICAL_W * scale) / 2
        oy = (wh - LOGICAL_H * scale) / 2
        return int((pos[0] - ox) / scale), int((pos[1] - oy) / scale)

    def _finger_logical(self, event):
        ww, wh = self.window.get_size()
        x, y = float(event.x), float(event.y)
        if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
            pos = (x * ww, y * wh)
        else:
            pos = (x, y)
        return self._logical_pos(pos)

    def update(self, dt=1.0):
        if self.state == "win":
            self._sync_web_nickname_input()
        if self.state == "intro":
            self.intro_timer -= dt
            if self.intro_timer <= 0:
                self.touch.clear()
                self.state = "play"
        elif self.state == "play":
            self.update_play(dt)
        elif self.state == "quiz" and self.feedback:
            self.feedback_timer -= dt
            if self.feedback_timer <= 0:
                self.finish_quiz()

    def draw(self):
        if self.state == "menu":
            self.screens.menu(self.logical)
        else:
            self.draw_play()
            if self.state == "intro":
                self.screens.world_intro(
                    self.logical,
                    str(self.level_cfg["id"]),
                    self.level_cfg["name"],
                    self.level_cfg["subtitle"],
                )
            elif self.state == "world_clear":
                self.screens.world_clear(
                    self.logical,
                    self.level_cfg["name"],
                    self.score,
                    self.clear_continue,
                )
            elif self.state == "quiz":
                helper_used = self.graddie_used or self.right_fit_used
                self.screens.quiz(
                    self.logical,
                    self.active_quiz,
                    self.quiz_buttons,
                    self.graddie_btn,
                    self.feedback,
                    helper_used,
                )
            elif self.state == "gameover":
                self.screens.game_over(self.logical, self.score)
            elif self.state == "win":
                self.screens.win(
                    self.logical,
                    self.score,
                    self.coin_count,
                    self.smart,
                    self.lives,
                    mode=self.win_mode,
                    nick=self.win_nickname,
                    status=self.win_status,
                    board=self.win_board,
                )
            elif self.state == "pause":
                shade = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
                shade.fill((0, 0, 0, 140))
                self.logical.blit(shade, (0, 0))
                img = self.assets.font_lg.render("Paused", True, (255, 255, 255))
                self.logical.blit(
                    img, ((LOGICAL_W - img.get_width()) // 2, S(900))
                )

        if self.state == "play":
            self.touch.draw(self.logical, self.assets.font_sm)

        ww, wh = self.window.get_size()
        scale = min(ww / LOGICAL_W, wh / LOGICAL_H)
        dw, dh = int(LOGICAL_W * scale), int(LOGICAL_H * scale)
        ox = (ww - dw) // 2
        oy = (wh - dh) // 2
        self.window.fill((10, 8, 20))
        # Avoid a wasteful 1:1 smoothscale copy every frame (common on web).
        if dw == LOGICAL_W and dh == LOGICAL_H:
            self.window.blit(self.logical, (ox, oy))
        elif IS_WEB or RENDER_SCALE < 1.0:
            scaled = pygame.transform.scale(self.logical, (dw, dh))
            self.window.blit(scaled, (ox, oy))
        else:
            scaled = pygame.transform.smoothscale(self.logical, (dw, dh))
            self.window.blit(scaled, (ox, oy))
