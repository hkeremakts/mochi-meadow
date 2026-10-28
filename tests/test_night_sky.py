"""The night sky in the pond: Venus as the evening and morning star, and
real lunar eclipses."""
import datetime
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat import sky
from habitat.events import ALL
from habitat.render import Renderer
from habitat.world import World
from tests.support import fixed_clock

pygame.init()


def utc(text):
    return datetime.datetime.fromisoformat(text).replace(tzinfo=datetime.timezone.utc)


class Venus(unittest.TestCase):
    """Against the published dates for 2026-27 (EarthSky, Star Walk)."""

    def test_greatest_evening_elongation_august_2026(self):
        self.assertAlmostEqual(sky.venus_elongation(utc("2026-08-15 06:00")), 45.9, delta=2.0)

    def test_between_us_and_the_sun_october_2026(self):
        self.assertLess(abs(sky.venus_elongation(utc("2026-10-24 04:00"))), 3.0)

    def test_greatest_morning_elongation_january_2027(self):
        self.assertAlmostEqual(sky.venus_elongation(utc("2027-01-03 12:00")), -47.0, delta=2.0)

    def test_the_evening_star_in_august_dusk_but_not_at_noon(self):
        s = sky.Sky(place=(41.0, 29.0), utc_offset=3)
        s.update(datetime.datetime(2026, 8, 15, 20, 45))
        self.assertTrue(s.venus_shows)
        s.update(datetime.datetime(2026, 8, 15, 13, 0))
        self.assertFalse(s.venus_shows)

    def test_hidden_in_the_sun_s_glare_at_conjunction(self):
        s = sky.Sky(place=(41.0, 29.0), utc_offset=3)
        for hour in (5, 6, 19, 20):
            s.update(datetime.datetime(2026, 10, 24, hour, 0))
            self.assertFalse(s.venus_shows, hour)

    def test_drawn_in_the_pond(self):
        screen = pygame.display.set_mode((427 * 2, 266 * 2))
        for seed in range(1, 30):           # a meadow where the tree doesn't hide Venus's spot in the pond
            w = World(427, 266, seed=seed, clock=fixed_clock(20.75, date=datetime.date(2026, 8, 15)),
                      weather="clear", weather_locked=True)
            x, y = w.water.sky_spot(w.env.sky.venus_az)
            if w.terrain.pond is not None and not w.terrain.behind_crown(x + 6, y):
                break
        self.assertTrue(w.env.sky.venus_shows)
        r = Renderer(screen, 2)
        r.bind(w)
        w.water.stars = []
        r.draw(w)
        with_venus = pygame.surfarray.array3d(screen).astype(int)
        w.env.sky.venus_alt = -10
        r.draw(w)
        without = pygame.surfarray.array3d(screen).astype(int)
        self.assertGreater((with_venus - without).max(), 60)


class Eclipses(unittest.TestCase):
    def test_total_at_greatest_eclipse(self):
        self.assertEqual(sky.eclipse_at(utc("2028-12-31 16:53")), (1.0, True))

    def test_partial_on_the_way_out_and_nothing_after(self):
        shadow, total = sky.eclipse_at(utc("2028-12-31 18:20"))
        self.assertFalse(total)
        self.assertGreater(shadow, 0.0)
        self.assertEqual(sky.eclipse_at(utc("2028-12-31 20:00")), (0.0, False))

    def test_an_ordinary_full_moon_is_not_an_eclipse(self):
        self.assertEqual(sky.eclipse_at(utc("2026-11-24 15:00"))[0], 0.0)

    def test_the_moon_dims_and_the_meadow_darkens(self):
        s = sky.Sky(place=(41.0, 29.0), utc_offset=3)
        s.update(datetime.datetime(2028, 12, 31, 19, 53))     # 16:53 UTC: totality, the moon up over Istanbul
        self.assertTrue(s.eclipse_total)
        self.assertGreater(s.moon_alt, 3)
        dark = s.moonlight
        s.eclipse = 0.0
        self.assertLess(dark, s.moonlight * 0.3)

    def test_noticed_on_the_night(self):
        w = World(427, 266, seed=4, clock=fixed_clock(19.9, date=datetime.date(2028, 12, 31)), weather="clear",
                  weather_locked=True)
        self.assertTrue(ALL["a lunar eclipse"].triggered(w))
        w2 = World(427, 266, seed=4, clock=fixed_clock(19.9, date=datetime.date(2028, 12, 30)), weather="clear",
                   weather_locked=True)
        self.assertFalse(ALL["a lunar eclipse"].triggered(w2))


class BehindTheTree(unittest.TestCase):
    def test_reflections_under_the_crown_are_hidden(self):
        w = World(427, 266, seed=4, clock=fixed_clock(22.0), weather="clear", weather_locked=True)
        t = w.terrain
        crown = t.canopies[0]
        self.assertTrue(t.behind_crown(crown.x, crown.y))
        self.assertFalse(t.behind_crown(crown.x + 200, crown.y + 200))
        crown.fade = 0.38                   # see-through over Mochi: the stars show again
        self.assertFalse(t.behind_crown(crown.x, crown.y))


if __name__ == "__main__":
    unittest.main()
