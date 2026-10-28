"""Mochi's body language: her tail and ears show her mood."""
import datetime
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat import cat_anims
from habitat.entities.cat import cat_library
from habitat.entities.wildlife import Fox
from habitat.personality import Personality
from habitat.world import World
from tests.support import fixed_clock

pygame.init()
pygame.display.set_mode((64, 64))
DT = 1 / 30


def meadow(mood=0.2, weather="clear"):
    p = Personality.neutral()
    p.mood = mood
    w = World(427, 266, seed=7, clock=fixed_clock(12.0, date=datetime.date(2026, 6, 20)), weather=weather,
              weather_locked=True, personality=p)
    w.entities = [w.cat]
    cat = w.cat
    cat.posture = "stand"
    cat.activity = None
    cat.interruptible = True
    cat.idle_pose()
    return w


def out_in_the_open(w):
    t = w.terrain
    for y in range(40, 240, 8):
        for x in range(30, 400, 8):
            if t.walkable(x, y) and not t.under_roof(x, y) and not t.under_roof(x, y + 6):
                w.cat.x, w.cat.y = float(x), float(y)
                return
    raise AssertionError("no open ground")


def airs(w, seconds):
    seen = set()
    for _ in range(int(seconds / DT)):
        w.update(DT)
        seen.add(w.cat.air)
    return seen


def mood_held(w, mood):
    """Keep her mood where the test wants it (moods drift on their own)."""
    w.cat.p.mood = mood
    w.cat.p.settle = lambda dt: None
    w.cat._mood_wander.step = lambda dt: w.cat._mood_wander.value


class Library(unittest.TestCase):
    def test_every_mood_has_its_idles_and_gaits_in_every_view(self):
        lib = cat_library()
        for air in cat_anims.AIRS:
            for name in ("stand", "walk", "trot"):
                for view in ("right", "left", "front", "back"):
                    self.assertIn(f"{name}~{air}_{view}", lib)

    def test_a_happy_tail_stands_up(self):
        lib = cat_library()
        calm = lib["stand_right"][0].get_bounding_rect()
        happy = lib["stand~happy_right"][0].get_bounding_rect()
        self.assertGreater(happy.left, calm.left + 4, "the tail no longer trails out behind")
        tail_top = min(y for y in range(64) for x in range(happy.left, happy.left + 6)
                       if lib["stand~happy_right"][0].get_at((x, y)).a)
        self.assertLess(tail_top, 30, "...it stands up over her back")


class Mood(unittest.TestCase):
    def test_calm_by_default(self):
        w = meadow()
        self.assertEqual(airs(w, 3), {None})
        self.assertNotIn("~", w.cat.anim.key)

    def test_a_happy_cat_holds_her_tail_up(self):
        w = meadow()
        mood_held(w, 0.8)
        airs(w, 2)
        self.assertEqual(w.cat.air, "happy")
        w.cat.show("stand")                  # (lying or sitting, a happy cat looks like any other)
        self.assertIn("~happy", w.cat.anim.key)

    def test_a_grumpy_cat_flattens_her_ears_back(self):
        w = meadow()
        mood_held(w, -0.6)
        airs(w, 2)
        self.assertEqual(w.cat.air, "cross")
        self.assertIn("~cross", w.cat.anim.key)

    def test_wary_when_the_fox_is_near_whatever_her_mood(self):
        w = meadow()
        mood_held(w, 0.8)
        fox = Fox(w)
        fox.x, fox.y = w.cat.x + 60, w.cat.y
        w.cat.p.traits["bold"] = 0.9         # a bold cat stands her ground, but her ears still go flat
        w.entities.append(fox)
        for _ in range(int(2 / DT)):
            fox.x, fox.y = w.cat.x + 60, w.cat.y
            w.update(DT)
        self.assertEqual(w.cat.air, "wary")

    def test_wary_with_rain_on_her_fur_but_not_under_cover(self):
        w = meadow(weather="rain")
        out_in_the_open(w)
        w.cat.activity = iter(lambda: None, 1)
        w.cat._perceive = lambda: None      # stay put: no running for cover in this test
        airs(w, 2)
        self.assertEqual(w.cat.air, "wary")
        w.cat.sheltered = True
        airs(w, 2)
        self.assertNotEqual(w.cat.air, "wary")

    def test_a_mood_change_keeps_her_stride(self):
        w = meadow()
        cat = w.cat
        cat.show("walk", stride=cat_anims.STRIDES["walk"], keep_phase=True)
        cat.anim.phase = 5.0
        mood_held(w, 0.8)
        cat._perceive_timer = 0.0
        cat.activity = iter(lambda: None, 1)   # an activity that does nothing, so the walk stays on
        w.update(DT)
        self.assertIn("walk~happy", cat.anim.key)
        self.assertAlmostEqual(cat.anim.phase, 5.0, delta=0.5)

    def test_no_flicker_on_the_edge_of_a_mood(self):
        w = meadow()
        mood_held(w, 0.8)
        airs(w, 1)
        w.cat.p.mood = 0.46                  # just below where happy begins, but not far enough to stop
        self.assertEqual(airs(w, 2), {"happy"})


class Dreams(unittest.TestCase):
    def test_deep_in_a_long_sleep_she_dreams(self):
        w = meadow()
        cat = w.cat
        cat.needs.energy = 0.0
        cat._start("nap", cat.doze(until=lambda: False))
        seen = set()
        for _ in range(int(8 * 60 / DT)):
            w.update(DT)
            seen.add((cat.label, (cat.anim.key or "").split("_")[0]))
        self.assertIn(("dreaming", "dream"), seen)

    def test_not_in_the_first_light_doze(self):
        w = meadow()
        cat = w.cat
        cat._start("nap", cat.doze(until=lambda: False))
        labels = {cat.label for _ in range(int(60 / DT)) if not w.update(DT)}
        self.assertNotIn("dreaming", labels)

    def test_every_sleep_style_has_a_dream(self):
        lib = cat_library()
        for style in ("loaf", "curl", "flat"):
            self.assertIn(f"dream_{style}_right", lib)
            self.assertIn(f"dream_{style}_left", lib)


class Rain(unittest.TestCase):
    def test_rain_soaks_her_and_cover_keeps_her_dry(self):
        w = meadow(weather="rain")
        cat = w.cat
        out_in_the_open(w)
        cat._perceive = lambda: None          # stay out in it
        cat.activity = iter(lambda: None, 1)
        for _ in range(int(10 / DT)):
            w.update(DT)
        self.assertGreater(cat.wet, 6.0)
        cat.sheltered = True
        before = cat.wet
        for _ in range(int(10 / DT)):
            w.update(DT)
        self.assertLess(cat.wet, before, "drying, slowly")
        self.assertGreater(cat.wet, before - 1.0)

    def test_wet_through_she_shakes_then_grooms_for_longer(self):
        w = meadow()
        cat = w.cat
        cat.wet = 12.0
        cat._start("shake", cat.shake_off())
        labels, keys = [], set()
        for _ in range(int(30 / DT)):
            w.update(DT)
            labels.append(cat.label)
            keys.add((cat.anim.key or "").split("_")[0])
        self.assertIn("shaking off the rain", labels)
        self.assertIn("shake", keys)
        self.assertEqual(cat.wet, 0.0)

    def test_only_damp_and_a_groom_is_enough(self):
        w = meadow()
        cat = w.cat
        cat.wet = 2.0
        cat._start("shake", cat.shake_off())
        keys = set()
        for _ in range(int(20 / DT)):
            w.update(DT)
            keys.add((cat.anim.key or "").split("_")[0])
        self.assertNotIn("shake", keys)
        self.assertIn("groom", keys)


if __name__ == "__main__":
    unittest.main()
