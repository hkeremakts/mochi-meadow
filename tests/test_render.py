"""Drawing: every condition renders, lighting follows the clock, frames are cheap."""
import os
import time
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from habitat.app import pick_zoom
from tests.support import fixed_clock
from habitat.render import Renderer
from habitat.world import World

pygame.init()


def frame(width, height, hour, weather, seconds=3.0, seed=4):
    pygame.init()
    screen = pygame.display.set_mode((width, height))
    zoom = pick_zoom(height)
    world = World(-(-width // zoom), -(-height // zoom), seed=seed, clock=fixed_clock(hour),
                  weather=weather, weather_locked=True)
    renderer = Renderer(screen, zoom)
    renderer.bind(world)
    for _ in range(int(seconds * 60)):
        world.update(1 / 60)
    renderer.draw(world)
    return screen, world, renderer


def brightness(surface):
    return float(pygame.surfarray.array3d(surface).mean())


class Rendering(unittest.TestCase):
    def test_every_time_of_day_and_weather_draws(self):
        for hour in (3.0, 6.2, 12.0, 19.3, 22.5):
            for weather in ("clear", "cloudy", "windy", "drizzle", "rain"):
                with self.subTest(hour=hour, weather=weather):
                    screen, _, _ = frame(640, 400, hour, weather, seconds=1.0)
                    pixels = pygame.surfarray.array3d(screen)
                    self.assertGreater(float(np.std(pixels)), 4.0, "frame is a flat colour")

    def test_night_is_darker_than_noon_but_not_black(self):
        noon = brightness(frame(640, 400, 12.0, "clear")[0])
        night = brightness(frame(640, 400, 23.0, "clear")[0])
        self.assertLess(night, noon * 0.6)
        self.assertGreater(night, 12.0)

    def test_rain_dims_the_meadow(self):
        clear = brightness(frame(640, 400, 12.0, "clear", seconds=1.0)[0])
        rain = brightness(frame(640, 400, 12.0, "rain", seconds=1.0)[0])
        self.assertLess(rain, clear)

    def test_a_1080p_frame_fits_comfortably_in_a_60fps_budget(self):
        screen, world, renderer = frame(1920, 1080, 12.0, "cloudy", seconds=2.0)
        start = time.perf_counter()
        for _ in range(60):
            world.update(1 / 60)
            renderer.draw(world)
        per_frame = (time.perf_counter() - start) / 60
        self.assertLess(per_frame, 0.008, f"{per_frame * 1000:.2f} ms per frame")


class Zoom(unittest.TestCase):
    def test_zoom_tracks_window_height(self):
        self.assertEqual(pick_zoom(640), 2)
        self.assertEqual(pick_zoom(800), 3)
        self.assertEqual(pick_zoom(1080), 4)
        self.assertEqual(pick_zoom(2160), 8)

    def test_zoom_never_drops_below_two(self):
        self.assertEqual(pick_zoom(300), 2)


if __name__ == "__main__":
    unittest.main()
