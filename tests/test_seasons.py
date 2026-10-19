"""The meadow's look and life through the year."""
import datetime
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from habitat.render import Renderer
from habitat.world import World
from tests.support import fixed_clock

pygame.init()
pygame.display.set_mode((64, 64))


def meadow(date, hour=12.0, weather="clear"):
    return World(427, 266, seed=3, clock=fixed_clock(hour, date=date), weather=weather, weather_locked=True)


def ground(world):
    return pygame.surfarray.array3d(world.terrain.ground).swapaxes(0, 1).astype(np.int32)


def greenness(world):
    rgb = ground(world)[~world.terrain.water]
    return float(np.mean(rgb[:, 1] - np.maximum(rgb[:, 0], rgb[:, 2])))


class Look(unittest.TestCase):
    def test_grass_fades_from_summer_to_winter(self):
        summer = greenness(meadow(datetime.date(2026, 6, 20)))
        autumn = greenness(meadow(datetime.date(2026, 11, 5)))
        winter = greenness(meadow(datetime.date(2026, 1, 20)))
        self.assertGreater(summer, autumn + 5)
        self.assertGreater(autumn, winter)

    def test_flowers_open_in_spring_and_are_gone_in_winter(self):
        spring = meadow(datetime.date(2026, 5, 20))
        winter = meadow(datetime.date(2026, 1, 20))
        flowers = lambda w: [p for p in w.terrain.props if p.kind == "flower"]
        self.assertTrue(any(not p.hidden for p in flowers(spring)))
        self.assertTrue(all(p.hidden for p in flowers(winter)))

    def test_settled_snow_whitens_the_ground_but_not_the_pond(self):
        w = meadow(datetime.date(2026, 1, 20))
        before = ground(w)
        w.env.snow_cover = 1.0
        w._scenery_check = 0.0
        w.update(1 / 30)
        after = ground(w)
        dry = ~w.terrain.water
        self.assertGreater(after[dry].mean(), before[dry].mean() + 60)
        self.assertTrue((after[w.terrain.water] == before[w.terrain.water]).all())

    def test_the_ground_is_only_regraded_when_something_changes(self):
        w = meadow(datetime.date(2026, 6, 20))
        version = w.scenery_version
        for _ in range(200):
            w.update(1 / 30)
        self.assertEqual(w.scenery_version, version)


class Weather(unittest.TestCase):
    def test_snow_falls_as_flakes_not_rain(self):
        w = World(427, 266, seed=3, clock=fixed_clock(10.0, date=datetime.date(2026, 1, 20), place=(60.2, 24.9)),
                  weather="rain", weather_locked=True)
        w.env.weather.rain = 0.85
        for _ in range(60):
            w.update(1 / 30)
        kinds = {p.kind for p in w.particles.items}
        self.assertIn("snow", kinds)
        self.assertNotIn("rain", kinds)
        flake = next(p for p in w.particles.items if p.kind == "snow" and p.z > 10)
        z = flake.z
        w.update(1 / 30)
        self.assertLess(flake.z, z, "flakes fall")
        surface = pygame.display.get_surface() or pygame.display.set_mode((64, 64))
        r = Renderer(surface, 1)
        r.bind(w, surface)
        r.draw(w)

    def test_autumn_leaves_fall_from_the_bushes_on_a_calm_day(self):
        w = meadow(datetime.date(2026, 10, 25))      # clear weather: never windy enough to blow leaves in
        leaves = 0
        for _ in range(int(60 * 30)):
            w.update(1 / 30)
            self.assertLess(w.env.wind.strength, 0.35)
            leaves = max(leaves, sum(1 for p in w.particles.items if p.kind == "leaf"))
        self.assertGreater(leaves, 0)


if __name__ == "__main__":
    unittest.main()
