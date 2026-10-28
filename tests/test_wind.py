"""Gusts you can see: pale bands race over the grass on a windy day."""
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat.render import Renderer
from habitat.world import World
from tests.support import fixed_clock

pygame.init()
DT = 1 / 30


def meadow(weather, hour=12.0):
    w = World(427, 266, seed=4, clock=fixed_clock(hour), weather=weather, weather_locked=True)
    w.env.wind.strength = 0.0
    return w


def bands(w, seconds):
    seen = 0
    for _ in range(int(seconds / DT)):
        w.update(DT)
        seen = max(seen, len(w.env.sheen.streaks))
    return seen


class Sheen(unittest.TestCase):
    def test_a_windy_day_sends_bands_over_the_grass(self):
        self.assertGreater(bands(meadow("windy"), 30), 0)

    def test_none_in_a_breeze(self):
        self.assertEqual(bands(meadow("clear"), 30), 0)

    def test_none_by_night(self):
        self.assertEqual(bands(meadow("windy", hour=1.0), 30), 0)

    def test_they_travel_with_the_wind_and_fade(self):
        w = meadow("windy")
        sheen = w.env.sheen
        w.env.wind.direction = 1.0
        sheen.streaks = [[100.0, 100.0, 0, 90.0, 0.0, 2.0]]
        sheen.update(0.5, w.env.wind, 1.0, 0.0)
        self.assertGreater(sheen.streaks[0][0], 100.0)
        self.assertEqual(sheen.level(0.0, 2.0), 0)
        self.assertEqual(sheen.level(1.0, 2.0), sheen.LEVELS)

    def test_drawn_over_the_ground_and_only_brightening_it(self):
        screen = pygame.display.set_mode((427 * 2, 266 * 2))
        w = meadow("windy")
        r = Renderer(screen, 2)
        r.bind(w)
        w.env.sheen.streaks = []
        r.draw(w)
        before = pygame.surfarray.array3d(screen).astype(int)
        # at their brightest, standing still, here and there (some will be under a bush or the tree)
        w.env.sheen.streaks = [[x, y, 0, 0.0, 1.0, 2.0] for x in (20.0, 160.0, 300.0) for y in (30.0, 200.0)]
        r.draw(w)
        after = pygame.surfarray.array3d(screen).astype(int)
        diff = after - before
        self.assertGreater(diff.max(), 5, "a visible band")
        self.assertGreaterEqual(diff.min(), -1, "it never darkens anything")


if __name__ == "__main__":
    unittest.main()
