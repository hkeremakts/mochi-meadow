"""The living world: long-run stability and the cat's core behaviours."""
import datetime
import math
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat.world import World
from tests.support import TEST_DATE, fixed_clock

MIDSUMMER = datetime.date(2026, 6, 21)
MIDWINTER = datetime.date(2026, 12, 21)

pygame.init()
pygame.display.set_mode((64, 64))

DT = 1 / 30


def run(world, seconds, until=None):
    t = 0.0
    while t < seconds:
        world.update(DT)
        t += DT
        if until is not None and until():
            return t
    return None


class LongRun(unittest.TestCase):
    """A full simulated day with changing weather must stay sane."""

    @classmethod
    def setUpClass(cls):
        cls.world = World(427, 266, seed=11, clock=fixed_clock(6.0, speed=72))  # a day in 20 minutes
        cls.activities = set()
        cls.max_entities = 0
        cls.max_particles = 0
        cls.cat_positions = []
        weathers = ["clear", "cloudy", "windy", "drizzle", "rain", "clear"]
        for i in range(int(20 * 60 / DT)):
            if i % int(200 / DT) == 0:
                cls.world.env.weather.force(weathers[(i // int(200 / DT)) % len(weathers)])
            cls.world.update(DT)
            cat = cls.world.cat
            cls.activities.add(cat.activity_name)
            cls.max_entities = max(cls.max_entities, len(cls.world.entities))
            cls.max_particles = max(cls.max_particles, len(cls.world.particles.items))
            cls.cat_positions.append((cat.x, cat.y))

    def test_cat_never_leaves_the_world_or_enters_the_pond(self):
        t = self.world.terrain
        for x, y in self.cat_positions:
            self.assertFalse(math.isnan(x) or math.isnan(y))
            self.assertTrue(0 <= x < t.width and 0 <= y < t.height, (x, y))
            self.assertFalse(t.water[int(y), int(x)], f"cat in the pond at {(x, y)}")

    def test_the_cat_leads_a_varied_life(self):
        self.assertGreaterEqual(len(self.activities - {"wake"}), 7, sorted(self.activities))

    def test_populations_stay_bounded(self):
        self.assertLess(self.max_entities, 60)
        self.assertLessEqual(self.max_particles, 900)


class Behaviours(unittest.TestCase):
    def make(self, hour=12.0, weather="clear", seed=7, date=TEST_DATE):
        world = World(427, 266, seed=seed, clock=fixed_clock(hour, date=date), weather=weather, weather_locked=True)
        run(world, 4.0)  # let the wake-up yawn finish
        return world

    def test_a_hungry_cat_eats_from_the_bowl(self):
        world = self.make()
        world.cat.needs.hunger = 1.0
        world.cat.activity = None  # choose again with the new need
        before = world.bowl_fill
        self.assertIsNotNone(run(world, 90, until=lambda: world.cat.label == "eating"), "never started eating")
        run(world, 4)
        self.assertLess(world.bowl_fill, before)

    def test_a_thirsty_cat_drinks_from_the_pond(self):
        world = self.make()
        world.cat.needs.thirst = 1.0
        world.cat.activity = None
        self.assertIsNotNone(run(world, 90, until=lambda: world.cat.label == "drinking from the pond"))

    def test_rain_sends_the_cat_under_cover(self):
        world = self.make()
        world.env.weather.force("rain", locked=True)
        world.env.weather.cloud = 1.0
        world.env.weather.rain = 0.85
        self.assertIsNotNone(run(world, 90, until=lambda: world.cat.sheltered), "never sheltered")
        bush_near = min(math.hypot(b.x - world.cat.x, b.y - world.cat.y) for b in world.terrain.bushes)
        self.assertTrue(bush_near < 30 or world.terrain.under_roof(world.cat.x, world.cat.y))

    def test_an_exhausted_cat_falls_asleep_and_wakes_rested(self):
        # (A catnap: deep sleeps can last a quarter of an hour.)
        from habitat.entities import cat as cat_module
        saved = cat_module.MOCHI["nap_minutes"]
        cat_module.MOCHI["nap_minutes"] = 3
        try:
            self._exhausted_cat_sleeps()
        finally:
            cat_module.MOCHI["nap_minutes"] = saved

    def _exhausted_cat_sleeps(self):
        world = self.make()
        world.cat.needs.energy = 0.05
        world.cat.activity = None
        self.assertIsNotNone(run(world, 120, until=lambda: world.cat.state == "sleeping"), "never slept")
        self.assertIsNotNone(run(world, 400, until=lambda: world.cat.label == "waking up"), "never woke")
        self.assertGreater(world.cat.needs.energy, 0.55)     # rested enough (a catnap needn't top her up)

    def test_an_empty_bowl_is_refilled_at_mealtime(self):
        probe = World(427, 266, seed=7, clock=fixed_clock(12.0), weather="clear", weather_locked=True)
        dinner = probe.meal_times()[1]        # today's dinner: about 18:00, give or take
        self.assertLess(abs(dinner - 18.0), 0.8)
        world = World(427, 266, seed=7, clock=fixed_clock(dinner - 0.1, speed=60), weather="clear",
                      weather_locked=True)
        world.bowl_fill = 0.0
        run(world, 12)  # 12 s at 60x = 12 game minutes, past dinner time
        self.assertGreater(world.bowl_fill, 0.55)

    def test_summer_nights_bring_fireflies_and_days_bring_butterflies(self):
        night = self.make(hour=22.5, date=MIDSUMMER)
        self.assertGreater(night.count("firefly"), 5)
        self.assertEqual(night.count("butterfly"), 0)
        day = self.make(hour=12.0, date=MIDSUMMER)
        self.assertGreater(day.count("butterfly"), 0)
        self.assertEqual(day.count("firefly"), 0)

    def test_winter_has_no_insects_and_the_hedgehog_hibernates(self):
        day = self.make(hour=12.0, date=MIDWINTER)
        for kind in ("butterfly", "bee", "ladybug", "dragonfly"):
            self.assertEqual(day.director.targets()[kind], 0, kind)
        night = self.make(hour=23.0, date=MIDWINTER)
        night.director.hog_night = True
        self.assertEqual(night.director.targets()["hedgehog"], 0)
        self.assertEqual(night.director.targets()["firefly"], 0)

    def test_the_meadow_follows_the_real_sunset(self):
        # 19:30 is broad daylight in June but full night in December.
        june = self.make(hour=19.3, date=MIDSUMMER)
        december = self.make(hour=19.3, date=MIDWINTER)
        self.assertGreater(june.env.sun, 0.2)
        self.assertEqual(december.env.sun, 0.0)


if __name__ == "__main__":
    unittest.main()
