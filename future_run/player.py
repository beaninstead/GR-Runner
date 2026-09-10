import pygame

from future_run.constants import (
    FRICTION,
    GRAVITY,
    GROUND_TOP,
    INVINCIBLE_FRAMES,
    JUMP_VEL,
    MOVE_ACCEL,
    MOVE_MAX,
    PLAYER_H,
    PLAYER_W,
    SKILL_BOOST_FRAMES,
    SKILL_BOOST_MAX,
)


class Player:
    def __init__(self, frames, x, y):
        self.frames = frames
        self.rect = pygame.Rect(x, y, PLAYER_W, PLAYER_H)
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.on_ground = False
        self.facing = 1
        self.anim = 0
        self.timer = 0
        self.ducking = False
        self.invincible = 0
        self.last_safe = pygame.Vector2(x, y)
        self.stand_h = PLAYER_H
        self.duck_h = int(PLAYER_H * 0.62)
        self.skill_boost = 0

    def grant_skill_boost(self, frames=SKILL_BOOST_FRAMES):
        self.skill_boost = max(self.skill_boost, frames)

    @property
    def move_max(self):
        return SKILL_BOOST_MAX if self.skill_boost > 0 else MOVE_MAX

    def handle_input(self, keys, touch=None):
        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        if touch is not None:
            left = left or touch.left
            right = right or touch.right
        self.ducking = (keys[pygame.K_DOWN] or keys[pygame.K_s]) and self.on_ground
        self._set_duck(self.ducking)

        if self.ducking:
            self.vel_x *= 0.6
            return

        speed_cap = self.move_max
        if left ^ right:
            self.facing = -1 if left else 1
            self.vel_x += MOVE_ACCEL * self.facing
            self.vel_x = max(-speed_cap, min(speed_cap, self.vel_x))
        else:
            self.vel_x *= FRICTION
            if abs(self.vel_x) < 0.25:
                self.vel_x = 0

    def jump(self):
        if self.on_ground and not self.ducking:
            self.vel_y = JUMP_VEL
            self.on_ground = False

    def _set_duck(self, ducking):
        bottom = self.rect.bottom
        x = self.rect.x
        h = self.duck_h if ducking else self.stand_h
        self.rect.size = (PLAYER_W, h)
        self.rect.bottom = bottom
        self.rect.x = x

    def physics(self, ground_spans, platforms=None):
        self.vel_y += GRAVITY
        if self.vel_y > 28:
            self.vel_y = 28

        self.rect.x += int(self.vel_x)
        if self.rect.x < 40:
            self.rect.x = 40
            self.vel_x = 0

        self.on_ground = False
        self.rect.y += int(self.vel_y)
        slop = max(40, abs(self.vel_y) + 12)
        for x0, x1, top in ground_spans:
            if self.rect.right > x0 + 8 and self.rect.left < x1 - 8:
                if self.vel_y >= 0 and self.rect.bottom >= top and self.rect.bottom <= top + slop:
                    self.rect.bottom = top
                    self.vel_y = 0
                    self.on_ground = True
                    self.last_safe.update(self.rect.x, self.rect.y)

        for plat in platforms or []:
            if self.vel_y >= 0 and self.rect.colliderect(plat):
                if self.rect.bottom <= plat.top + slop and self.rect.bottom >= plat.top:
                    self.rect.bottom = plat.top
                    self.vel_y = 0
                    self.on_ground = True
                    self.last_safe.update(self.rect.x, self.rect.y)

        if self.invincible > 0:
            self.invincible -= 1
        if self.skill_boost > 0:
            self.skill_boost -= 1

        self.timer += 1
        if abs(self.vel_x) > 0.4 and self.on_ground:
            if self.timer % 6 == 0:
                self.anim = (self.anim + 1) % 4

    def snap_safe(self):
        self.rect.x = int(self.last_safe.x)
        self.rect.y = int(self.last_safe.y)
        self.vel_x = 0
        self.vel_y = 0
        self.on_ground = True
        self.invincible = max(self.invincible, INVINCIBLE_FRAMES)

    def fell_in_pit(self, ground_spans):
        if self.rect.top > GROUND_TOP + 80:
            return True
        over_ground = False
        for x0, x1, top in ground_spans:
            if self.rect.centerx >= x0 and self.rect.centerx <= x1:
                over_ground = True
                break
        return (not over_ground) and self.rect.top > GROUND_TOP - 20

    def image(self):
        if self.ducking and self.on_ground:
            frame = self.frames.get("break", self.frames["idle"])
        elif not self.on_ground:
            frame = self.frames["jump"] if self.vel_y < 0 else self.frames.get(
                "jump2", self.frames["jump"]
            )
        elif abs(self.vel_x) > 0.4:
            frame = self.frames[f"run{self.anim + 1}"]
        else:
            frame = self.frames["idle"]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        return frame
