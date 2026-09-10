import pygame

from future_run.constants import LOGICAL_H, LOGICAL_W, WHITE


class TouchControls:
    """On-screen left / right / jump pad for phones and tablets."""

    LEFT = pygame.Rect(36, LOGICAL_H - 252, 200, 200)
    RIGHT = pygame.Rect(260, LOGICAL_H - 252, 200, 200)
    JUMP = pygame.Rect(LOGICAL_W - 236, LOGICAL_H - 292, 200, 240)

    def __init__(self):
        self.left = False
        self.right = False
        self.jump_held = False
        self._jump_edge = False
        self._held = {}

    def clear(self):
        self._held.clear()
        self.left = False
        self.right = False
        self.jump_held = False
        self._jump_edge = False

    def consume_jump(self):
        if self._jump_edge:
            self._jump_edge = False
            return True
        return False

    def _zone(self, pos):
        if self.LEFT.collidepoint(pos):
            return "left"
        if self.RIGHT.collidepoint(pos):
            return "right"
        if self.JUMP.collidepoint(pos):
            return "jump"
        return None

    def _sync(self):
        zones = set(self._held.values())
        self.left = "left" in zones
        self.right = "right" in zones
        jump = "jump" in zones
        if jump and not self.jump_held:
            self._jump_edge = True
        self.jump_held = jump

    def _bind(self, pointer_id, pos):
        zone = self._zone(pos)
        if zone:
            self._held[pointer_id] = zone
        elif pointer_id in self._held:
            del self._held[pointer_id]
        self._sync()
        return zone is not None

    def _unbind(self, pointer_id):
        if pointer_id in self._held:
            del self._held[pointer_id]
            self._sync()

    def handle_event(self, event, logical_from_window, logical_from_finger):
        if event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION):
            fid = getattr(event, "finger_id", getattr(event, "finger", 0))
            return self._bind(("f", fid), logical_from_finger(event))
        if event.type == pygame.FINGERUP:
            fid = getattr(event, "finger_id", getattr(event, "finger", 0))
            self._unbind(("f", fid))
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._bind("mouse", logical_from_window(event.pos))
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._unbind("mouse")
            return False
        if event.type == pygame.MOUSEMOTION and event.buttons[0]:
            return self._bind("mouse", logical_from_window(event.pos))
        return False

    def draw(self, surf, font):
        self._draw_pad(surf, self.LEFT, self.left, "<", font)
        self._draw_pad(surf, self.RIGHT, self.right, ">", font)
        self._draw_pad(surf, self.JUMP, self.jump_held, "JUMP", font)

    def _draw_pad(self, surf, rect, active, label, font):
        pad = pygame.Surface(rect.size, pygame.SRCALPHA)
        fill = (255, 255, 255, 92) if active else (12, 8, 28, 110)
        rim = (255, 255, 255, 200) if active else (255, 255, 255, 120)
        pygame.draw.ellipse(pad, fill, pad.get_rect())
        pygame.draw.ellipse(pad, rim, pad.get_rect(), 5)
        surf.blit(pad, rect.topleft)
        text = font.render(label, True, WHITE)
        surf.blit(
            text,
            (
                rect.centerx - text.get_width() // 2,
                rect.centery - text.get_height() // 2,
            ),
        )
