"""The ginger cat's kitten: once he and Mochi are old friends."""
import datetime
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat import cat_anims
from habitat.entities.cat import cat_library
from habitat.entities.visitor import kitten_library
from habitat.events import ALL
from habitat.personality import BEST_FRIENDS, Personality
from habitat.world import World
from tests.support import fixed_clock

pygame.init()
pygame.display.set_mode((64, 64))
DT = 1 / 30
VISIT = ALL["the ginger cat's kitten"]


def meadow(friends=BEST_FRIENDS, date=datetime.date(2026, 6, 10)):
    p = Personality.neutral()
    p.friends["ginger"] = friends
    w = World(427, 266, seed=7, clock=fixed_clock(12.0, date=date), weather="clear", weather_locked=True,
              personality=p)
    w.entities = [w.cat]
    cat = w.cat
    cat.posture = "stand"
    cat.activity = None
    cat.idle_pose()
    return w


class WhenItComes(unittest.TestCase):
    def test_only_for_old_friends(self):
        self.assertTrue(VISIT.ready(meadow()))
        self.assertFalse(VISIT.ready(meadow(friends=BEST_FRIENDS - 2)))

    def test_only_in_kitten_season(self):
        self.assertFalse(VISIT.ready(meadow(date=datetime.date(2026, 11, 20))))


class TheKitten(unittest.TestCase):
    def test_small_big_headed_and_crisp(self):
        kit, mochi = kitten_library()["stand_right"][0], cat_library()["stand_right"][0]
        k, m = kit.get_bounding_rect(), mochi.get_bounding_rect()
        self.assertLess(k.width, m.width * 0.85)
        self.assertLess(k.height, m.height * 0.9)
        self.assertEqual(k.bottom, m.bottom, "feet on the same ground line")

    def test_has_what_it_needs_both_ways(self):
        lib = kitten_library()
        for name in cat_anims.KITTEN:
            if f"{name}_right" in cat_library():
                self.assertIn(f"{name}_right", lib)
                self.assertIn(f"{name}_left", lib)

    def test_it_comes_meets_mochi_and_goes_home_with_him(self):
        w = meadow()
        self.assertTrue(VISIT.start(w, w.events))
        kitten = next(e for e in w.entities if e.kind == "kitten")
        labels = set()
        for _ in range(int(400 / DT)):
            w.update(DT)
            if kitten.alive:
                labels.add(kitten.label)
            if not kitten.alive and not any(e.kind == "visitor" for e in w.entities):
                break
        self.assertIn("trotting after the ginger cat", labels)
        self.assertIn("touching noses with Mochi", labels)
        self.assertFalse(kitten.alive, "it went home")


if __name__ == "__main__":
    unittest.main()
