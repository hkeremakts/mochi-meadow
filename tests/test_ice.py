"""A hard winter freezes the pond, and Mochi tests the ice."""
import datetime
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat.personality import Personality
from habitat.seasons import Scenery
from habitat.world import World
from tests.support import fixed_clock

pygame.init()
pygame.display.set_mode((64, 64))
DT = 1 / 30
WINTER = datetime.date(2027, 1, 20)


def meadow(cold=None, date=WINTER):
    w = World(427, 266, seed=3, clock=fixed_clock(12.0, date=date), weather="clear", weather_locked=True,
              personality=Personality.neutral())
    w.entities = [w.cat]
    if cold is not None:
        w.env._temperature = lambda: cold
        w.env.temperature = cold
    return w


def water_colour(w):
    t = w.terrain
    rgb = pygame.surfarray.array3d(t.ground).swapaxes(0, 1)
    return rgb[t.water].mean(axis=0)


class Freezing(unittest.TestCase):
    def test_a_hard_frost_freezes_the_pond(self):
        w = meadow(cold=-6.0)
        w.env.ice = 0.0
        w.env.clock.speed = 600.0          # ten minutes a second
        for _ in range(int(10 / DT)):
            w.update(DT)
        self.assertTrue(w.env.frozen)

    def test_a_mild_winter_leaves_it_open(self):
        w = meadow(cold=3.0)
        w.env.ice = 0.0
        w.env.clock.speed = 600.0
        for _ in range(int(10 / DT)):
            w.update(DT)
        self.assertEqual(w.env.ice, 0.0)

    def test_a_thaw_melts_it(self):
        w = meadow(cold=6.0)
        w.env.ice = 1.0
        w.env.clock.speed = 600.0
        for _ in range(int(10 / DT)):
            w.update(DT)
        self.assertFalse(w.env.frozen)


class TheLook(unittest.TestCase):
    def test_ice_is_paler_than_water_and_baked_into_the_ground(self):
        w = meadow(cold=3.0)
        w.env.ice = 0.0
        w.scenery.apply(Scenery.key_for(w.env))
        open_water = water_colour(w)
        w.env.ice = 1.0
        self.assertTrue(w.scenery.apply(Scenery.key_for(w.env)))
        iced = water_colour(w)
        self.assertGreater(iced.mean(), open_water.mean() + 20)

    def test_nothing_ripples_on_ice(self):
        w = meadow(cold=-6.0)
        w.env.ice = 1.0
        w.water.ripples = []
        w.water.ripple(*w.terrain.pond.open_cells[0])
        self.assertEqual(w.water.ripples, [])


class Mochi(unittest.TestCase):
    def test_she_tests_the_ice_with_a_paw_and_licks_it(self):
        w = meadow(cold=-6.0)
        w.env.ice = 1.0
        cat = w.cat
        cat.posture = "stand"
        cat.idle_pose()
        cat.needs.thirst = 0.9
        cat._start("drink", cat.act_drink())
        labels, keys = [], set()
        for _ in range(int(90 / DT)):
            w.update(DT)
            labels.append(cat.label)
            keys.add((cat.anim.key or "").rsplit("_", 1)[0])
            if cat.activity_name != "drink":
                break
        self.assertIn("testing the ice", labels)
        self.assertIn("licking the ice", labels)
        self.assertNotIn("drinking from the pond", labels)
        self.assertLess(cat.needs.thirst, 0.9)
        self.assertTrue(keys & {"swipe_stand"} or "crouch" in keys)


if __name__ == "__main__":
    unittest.main()
