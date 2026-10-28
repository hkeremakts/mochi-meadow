"""Animals on foot go round the pond, the bushes and the rocks, not through."""
import datetime
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat.entities.wildlife import Hedgehog, Pigeon
from habitat.world import World
from tests.support import fixed_clock

pygame.init()
pygame.display.set_mode((64, 64))
DT = 1 / 30


def meadow(seed, hour=23.0):
    w = World(427, 266, seed=seed, clock=fixed_clock(hour, date=datetime.date(2026, 6, 20)), weather="clear",
              weather_locked=True)
    w.entities = [w.cat]
    w.cat.x, w.cat.y = 5.0, 5.0             # out of the way: nothing to curl up from
    w.cat.activity = iter(lambda: None, 1)
    return w


def inside(w, e):
    return 0 <= e.x < w.width and 0 <= e.y < w.height


def solid(w, x, y):
    """In the pond, or inside a bush, a rock or the trunk."""
    t = w.terrain
    return bool(t.water[int(y), int(x)] or t.solid[int(y), int(x)])


class Hedgehogs(unittest.TestCase):
    def test_never_through_the_pond_or_anything_solid(self):
        for seed in range(8):
            w = meadow(seed)
            hogs = [Hedgehog(w) for _ in range(3)]
            w.entities += hogs
            for _ in range(int(240 / DT)):
                w.update(DT)
                for h in hogs:
                    if h.alive and inside(w, h):
                        self.assertFalse(solid(w, h.x, h.y), f"seed {seed}: through the pond or something solid "
                                                              f"at {h.x:.0f},{h.y:.0f}")

    def test_it_still_gets_about_and_goes_home(self):
        w = meadow(3)
        hog = Hedgehog(w)
        w.entities.append(hog)
        start = (hog.x, hog.y)
        far, t = 0.0, 0.0
        while hog.alive and t < 900:
            w.update(DT)
            t += DT
            far = max(far, abs(hog.x - start[0]))
        self.assertGreater(far, 60, "it wandered in")
        self.assertFalse(hog.alive, "and left again")


class GroundBirds(unittest.TestCase):
    def test_their_little_walks_go_round_the_water(self):
        for seed in range(6):
            w = meadow(seed, hour=12.0)
            pond = w.terrain.pond
            birds = []
            t = w.terrain
            x = next(x for x in range(int(pond.cx), w.width) if t.free_ground(x, pond.cy))   # just off the bank
            for _ in range(4):
                b = Pigeon(w, x + 2, pond.cy)
                b.x, b.y = x + 2.0, float(pond.cy)
                b.state = "ground"
                b.z = 0.0
                birds.append(b)
            w.entities += birds
            for _ in range(int(60 / DT)):
                w.update(DT)
                for b in birds:
                    if b.alive and b.state == "ground" and inside(w, b):
                        self.assertFalse(w.terrain.is_water(b.x, b.y), f"seed {seed}: a pigeon walked into the pond")


if __name__ == "__main__":
    unittest.main()
