"""The old tree: a roof in the rain, and a cat who doesn't always stay under
it."""
import datetime
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat.personality import Personality
from habitat.world import World
from tests.support import fixed_clock

pygame.init()
pygame.display.set_mode((64, 64))
DT = 1 / 30


def meadow(seed=3, weather="clear", date=datetime.date(2026, 5, 10), personality=None):
    w = World(427, 266, seed=seed, clock=fixed_clock(14.0, date=date), weather=weather, weather_locked=True,
              personality=personality)
    w.cat.posture = "stand"
    w.cat.activity = None
    w.cat.interruptible = True
    w.cat.idle_pose()
    return w


def rain(w):
    w.env.weather.force("rain", locked=True)
    w.env.weather.cloud = 1.0
    w.env.weather.rain = 0.85


class Placement(unittest.TestCase):
    def test_a_meadow_has_its_tree_with_room_beneath(self):
        t = meadow().terrain
        tree = t.tree
        self.assertIsNotNone(tree)
        self.assertFalse(t.walkable(tree.x, tree.y - 1), "the trunk is solid")
        self.assertTrue(t.spots["roof"])
        for s in t.spots["roof"]:
            self.assertTrue(t.under_roof(s.x, s.y))
            self.assertTrue(t.walkable(s.x, s.y))

    def test_the_tree_does_not_move_the_rest_of_the_meadow(self):
        # It is planted last, from its own random numbers.
        t = meadow(seed=11).terrain
        others = [(p.kind, round(p.x), round(p.y)) for p in t.props if p.kind not in ("trunk",)]
        again = [(p.kind, round(p.x), round(p.y)) for p in meadow(seed=11).terrain.props if p.kind != "trunk"]
        self.assertEqual(others, again)


class Roof(unittest.TestCase):
    def test_rain_does_not_reach_the_ground_beneath(self):
        w = meadow()
        rain(w)
        landed_under = 0
        for _ in range(int(20 / DT)):
            before = {id(p) for p in w.particles.items if p.kind == "splash"}
            w.update(DT)
            for p in w.particles.items:
                if p.kind == "splash" and id(p) not in before and w.terrain.tree.covers(p.x, p.y):
                    landed_under += 1
        self.assertEqual(landed_under, 0)

    def test_snow_leaves_a_dry_ring(self):
        w = meadow(date=datetime.date(2027, 1, 15))
        w.env.snow_cover = 1.0
        w._scenery_check = 0.0
        w.update(DT)
        ground = pygame.surfarray.array3d(w.terrain.ground).swapaxes(0, 1).astype(int)
        tree = w.terrain.tree
        under = ground[int(tree.roof_cy) - 2, int(tree.roof_cx) - 20]
        open_ = ground[int(tree.roof_cy), int(tree.roof_cx + tree.roof_rx + 15)]
        self.assertGreater(open_.sum(), under.sum() + 150)

    def test_the_crown_fades_over_the_cat(self):
        w = meadow()
        spot = w.terrain.spots["roof"][0]
        w.cat.x, w.cat.y = float(spot.x), float(spot.y)
        for _ in range(int(2 / DT)):
            w.update(DT)
        self.assertLess(w.terrain.tree.canopy.fade, 0.6)
        w.cat.x, w.cat.y = 60.0, 230.0
        for _ in range(int(2 / DT)):
            w.update(DT)
        self.assertGreater(w.terrain.tree.canopy.fade, 0.95)


class Mochi(unittest.TestCase):
    def test_she_usually_runs_for_the_tree(self):
        under_tree = 0
        trials = 0
        for seed in range(1, 9):
            w = meadow(seed=seed)
            if not w.terrain.spots["roof"]:
                continue
            trials += 1
            w.cat.needs.energy = 0.9
            rain(w)
            for _ in range(int(40 / DT)):
                w.update(DT)
            under_tree += w.terrain.under_roof(w.cat.x, w.cat.y)
        self.assertGreaterEqual(trials, 5)
        self.assertGreaterEqual(under_tree / trials, 0.6)

    def test_but_now_and_then_she_goes_out_in_it(self):
        p = Personality.neutral()
        p.traits.update(curious=0.9, bold=0.9)
        went_out = False
        for seed in (3, 4):
            w = meadow(seed=seed, personality=p)
            w.cat.needs.energy = 0.9
            rain(w)
            labels = set()
            for _ in range(int(400 / DT)):
                w.update(DT)
                labels.add(w.cat.label)
            went_out |= "out in the rain" in labels or "drinking from a puddle" in labels
        self.assertTrue(went_out)


if __name__ == "__main__":
    unittest.main()
