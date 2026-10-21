"""The tree's shadow follows the sun, and Mochi follows the shadow."""
import datetime
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import habitat.entities.cat as cat_module
from habitat.shade import cast
from habitat.world import World
from tests.support import fixed_clock

pygame.init()
pygame.display.set_mode((64, 64))
DT = 1 / 30
SUMMER = datetime.date(2026, 7, 10)


def meadow(hour=10.0, weather="clear", seed=3, date=SUMMER):
    w = World(427, 266, seed=seed, clock=fixed_clock(hour, date=date), weather=weather, weather_locked=True)
    w.env.clouds.clouds = []
    w.update(DT)
    return w


class Casting(unittest.TestCase):
    def test_shadows_fall_away_from_the_sun(self):
        east = cast(20, 90, 40)
        self.assertLess(east[0], -50, "morning sun in the east: shadow to the west")
        self.assertGreater(cast(20, 270, 40)[0], 50)
        self.assertLess(cast(60, 180, 40)[1], 0, "noon sun in the south: shadow to the north (up)")

    def test_a_low_sun_casts_a_longer_shadow(self):
        self.assertGreater(abs(cast(10, 90, 40)[0]), abs(cast(50, 90, 40)[0]) * 3)


class TreeShadow(unittest.TestCase):
    def test_it_swings_round_through_the_day(self):
        xs = [meadow(hour).shade.ellipse[0] for hour in (8.0, 11.0, 14.0, 17.0)]
        self.assertEqual(xs, sorted(xs))
        tree = meadow().terrain.tree
        self.assertLess(xs[0], tree.x - 40)
        self.assertGreater(xs[-1], tree.x + 40)

    def test_no_shadow_without_direct_sun(self):
        self.assertLess(meadow(weather="rain").shade.strength, 0.05)
        self.assertIsNone(meadow(hour=1.0, date=datetime.date(2026, 7, 14)).shade.ellipse,
                          "a new moon casts nothing")

    def test_a_full_moon_casts_a_faint_one(self):
        w = meadow(hour=1.0, date=datetime.date(2026, 7, 30))
        self.assertIsNotNone(w.shade.ellipse)
        self.assertLess(w.shade.strength, meadow(hour=10.0).shade.strength)

    def test_a_cloud_over_the_sun_fades_it(self):
        w = meadow()
        before = w.shade.strength
        cx, cy = w.shade.ellipse[:2]
        shape = w.env.clouds.shapes[0]
        cloud = [cx - shape.get_width() / 2, cy - shape.get_height() / 2, shape, 0.0]
        w.env.clouds.clouds = [cloud]
        w.env.clouds.update = lambda *a: None
        for _ in range(int(5 / DT)):
            w.update(DT)
        self.assertLess(w.shade.strength, before * 0.4)

    def test_it_darkens_the_grass_but_never_the_tree_itself(self):
        w = meadow(hour=12.5)
        light = pygame.Surface((w.width, w.height))
        light.fill((255, 255, 255))
        w.shade.draw(light)
        tree = w.terrain.tree
        canopy = tree.canopy
        self.assertEqual(light.get_at((int(canopy.x), int(canopy.y)))[:3], (255, 255, 255))
        w2 = meadow(hour=8.0)
        light2 = pygame.Surface((w2.width, w2.height))
        light2.fill((255, 255, 255))
        w2.shade.draw(light2)
        x, y = (int(v) for v in w2.shade.ellipse[:2])
        self.assertLess(sum(light2.get_at((x, y))[:3]), 255 * 3 - 60)


class Mochi(unittest.TestCase):
    def setUp(self):
        self.saved = dict(cat_module.SHADE)

    def tearDown(self):
        cat_module.SHADE.clear()
        cat_module.SHADE.update(self.saved)

    def nap(self, w, seconds=90):
        c = w.cat
        c.needs.energy = 0.05
        c.activity = None
        c.interruptible = True
        for _ in range(int(seconds / DT)):
            w.update(DT)
            if c.label == "napping":
                return True
        return False

    def test_on_a_hot_day_she_naps_in_the_shade(self):
        cat_module.SHADE.update(hot_above=-50.0, seek_chance=1.0)
        shaded = 0
        for seed in (3, 4, 5):
            w = meadow(hour=15.0, seed=seed)
            if self.nap(w):
                shaded += w.shade.covers(w.cat.x, w.cat.y)
        self.assertGreaterEqual(shaded, 2)

    def test_on_a_cold_day_she_naps_in_the_sun(self):
        cat_module.SHADE.update(hot_above=99.0, cold_below=99.0, seek_chance=1.0)
        sunny = 0
        for seed in (3, 4, 5):
            w = meadow(hour=15.0, seed=seed)
            if self.nap(w):
                sunny += not w.shade.covers(w.cat.x, w.cat.y) and not w.terrain.under_roof(w.cat.x, w.cat.y)
        self.assertGreaterEqual(sunny, 2)

    def test_when_the_shade_moves_off_her_she_follows_it(self):
        cat_module.SHADE.update(hot_above=-50.0, seek_chance=0.0, restless_after=5)
        w = meadow(hour=15.0)
        self.assertTrue(self.nap(w))
        if w.shade.covers(w.cat.x, w.cat.y):
            self.skipTest("she happened to choose the shade anyway")
        labels = set()
        for _ in range(int(60 / DT)):
            w.update(DT)
            labels.add(w.cat.label)
            if w.cat.label == "napping" and w.shade.covers(w.cat.x, w.cat.y):
                break
        self.assertIn("following the shade", labels)
        self.assertTrue(w.shade.covers(w.cat.x, w.cat.y))


if __name__ == "__main__":
    unittest.main()
