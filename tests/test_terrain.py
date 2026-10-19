"""Generated terrain must always be livable for the cat."""
import os
import time
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from habitat.paths import find_path
from habitat.terrain import generate_terrain

SIZES = [(480, 320), (640, 360), (320, 200), (720, 260)]
SEEDS = range(1, 7)


def leg_cells(a, b):
    (x0, y0), (x1, y1) = a, b
    if y0 == y1:
        return [(x, y0) for x in range(min(x0, x1), max(x0, x1) + 1)]
    return [(x0, y) for y in range(min(y0, y1), max(y0, y1) + 1)]


class Livability(unittest.TestCase):
    def test_spawn_point_is_walkable(self):
        for size in SIZES:
            for seed in SEEDS:
                t = generate_terrain(*size, seed=seed)
                x, y = t.spawn
                with self.subTest(size=size, seed=seed):
                    self.assertFalse(t.blocked[int(y), int(x)])

    def test_every_interaction_spot_is_reachable_from_spawn(self):
        for size in SIZES:
            for seed in SEEDS:
                t = generate_terrain(*size, seed=seed)
                start = (int(t.spawn[0]), int(t.spawn[1]))
                for kind, spots in t.spots.items():
                    for spot in spots:
                        with self.subTest(size=size, seed=seed, kind=kind, at=(spot.x, spot.y)):
                            route = find_path(t.blocked, start, spot.approach)
                            self.assertIsNotNone(route, "approach point unreachable")
                            ax, ay = spot.approach
                            self.assertTrue(ax == spot.x or ay == spot.y, "final step not straight")
                            for x, y in leg_cells(spot.approach, (spot.x, spot.y)):
                                self.assertFalse(t.solid[y, x], f"final step crosses {(x, y)}")

    def test_full_size_world_offers_food_water_and_shelter(self):
        for seed in SEEDS:
            t = generate_terrain(640, 360, seed=seed)
            with self.subTest(seed=seed):
                self.assertTrue(t.spots["bowl"], "nowhere to eat")
                self.assertTrue(t.spots["drink"], "nowhere to drink")
                self.assertTrue(t.spots["shelter"], "nowhere to shelter")

    def test_pond_stays_inside_the_world(self):
        for size in SIZES:
            for seed in SEEDS:
                w = generate_terrain(*size, seed=seed).water
                with self.subTest(size=size, seed=seed):
                    self.assertFalse(w[0].any() or w[-1].any() or w[:, 0].any() or w[:, -1].any())

    def test_generation_is_fast_enough_for_live_resizing(self):
        generate_terrain(640, 360, seed=99)  # warm imports / asset cache
        start = time.perf_counter()
        generate_terrain(640, 360, seed=100)
        self.assertLess(time.perf_counter() - start, 0.6)


if __name__ == "__main__":
    unittest.main()
