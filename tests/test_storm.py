"""Summer thunderstorms: silent lightning, and a cat who doesn't like it."""
import datetime
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat.events import ALL, Thunderstorm
from habitat.personality import Personality
from habitat.render import Renderer
from habitat.world import World
from tests.support import fixed_clock

pygame.init()
DT = 1 / 30
STORM = ALL["a thunderstorm"]


def meadow(weather="rain", date=datetime.date(2026, 7, 10), hour=15.0):
    w = World(427, 266, seed=5, clock=fixed_clock(hour, date=date), weather=weather, weather_locked=True,
              personality=Personality.neutral())
    w.entities = [w.cat]
    for _ in range(int(2 / DT)):
        w.update(DT)
    return w


def run(w, seconds, watch=None):
    seen = []
    for _ in range(int(seconds / DT)):
        w.update(DT)
        if watch:
            seen.append(watch(w))
    return seen


class WhenItComes(unittest.TestCase):
    def test_in_a_warm_downpour(self):
        self.assertTrue(STORM.ready(meadow()))

    def test_not_on_a_dry_day(self):
        self.assertFalse(STORM.ready(meadow("clear")))

    def test_not_in_winter_rain(self):
        w = meadow(date=datetime.date(2027, 1, 20))
        self.assertLess(w.env.temperature, 10)
        self.assertFalse(STORM.ready(w))


class Lightning(unittest.TestCase):
    def test_flashes_come_and_the_storm_ends_with_the_rain(self):
        w = meadow()
        storm = Thunderstorm(w)
        w.effects.append(storm)
        lit = run(w, 60, watch=lambda w: storm.brightness())
        self.assertGreater(max(lit), 0.9, "a flash")
        self.assertLess(sum(1 for k in lit if k > 0.02) / len(lit), 0.2, "flashes, not daylight")
        for _ in range(int(5 / DT)):              # the rain eases off
            w.env.weather.rain = 0.1
            w.update(DT)
        self.assertFalse(storm.alive)
        self.assertIsNone(w.storm)

    def test_a_flash_lights_the_whole_meadow(self):
        screen = pygame.display.set_mode((427 * 2, 266 * 2))
        w = meadow()
        r = Renderer(screen, 2)
        r.bind(w)
        storm = Thunderstorm(w)
        w.effects.append(storm)
        r.draw(w)
        dark = pygame.surfarray.array3d(screen).mean()
        storm.flash = 0.0
        r.draw(w)
        self.assertGreater(pygame.surfarray.array3d(screen).mean(), dark + 20)


class Mochi(unittest.TestCase):
    def test_ears_flat_while_it_lasts_even_under_cover(self):
        w = meadow()
        w.cat.sheltered = True
        w.cat._perceive = lambda: None
        w.effects.append(Thunderstorm(w))
        run(w, 2)
        self.assertEqual(w.cat.air, "wary")

    def test_a_flash_sends_her_for_cover(self):
        w = meadow()
        cat = w.cat
        cat.posture = "stand"
        cat.sheltered = False
        cat.activity = None
        cat.interruptible = True
        cat.idle_pose()
        cat._perceive = lambda: None          # only the lightning moves her
        cat._start("sit", cat.act_sit())
        storm = Thunderstorm(w)
        w.effects.append(storm)
        storm.strike()
        self.assertEqual(cat.activity_name, "shelter")


if __name__ == "__main__":
    unittest.main()
