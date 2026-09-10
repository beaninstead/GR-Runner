# /// script
# dependencies = [
#   "numpy",
# ]
# ///
import asyncio

import pygame

from future_run.constants import FPS, LOGICAL_H, LOGICAL_W, frame_scale
from future_run.game import FutureRun
from future_run.web import IS_WEB


def window_size():
    info = pygame.display.Info()
    max_w = max(400, info.current_w - 80)
    max_h = max(600, info.current_h - 80)
    scale = min(max_w / LOGICAL_W, max_h / LOGICAL_H)
    return max(360, int(LOGICAL_W * scale)), max(640, int(LOGICAL_H * scale))


async def main():
    if not IS_WEB:
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
        except Exception:
            pass
    pygame.init()
    pygame.display.set_caption("Future Run")
    flags = 0 if IS_WEB else pygame.RESIZABLE
    size = (LOGICAL_W, LOGICAL_H) if IS_WEB else window_size()
    window = pygame.display.set_mode(size, flags)
    clock = pygame.time.Clock()
    game = FutureRun(window)

    running = True
    while running:
        # tick() returns ms since last call; use it for dt so web FPS variance
        # does not slow/speed frame-tuned physics.
        dt_ms = clock.tick(FPS)
        dt = frame_scale(dt_ms / 1000.0)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                game.handle_event(event)
        game.update(dt)
        game.draw()
        pygame.display.flip()
        await asyncio.sleep(0)
    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
