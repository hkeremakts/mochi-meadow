"""Paw prints in snow and mud, and the paths Mochi wears in the grass."""
import datetime
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat.events import Puddle, Puddles
from habitat.journal import Journal
from habitat.marks import Marks
from habitat.world import World
from tests.support import fixed_clock

pygame.init()
pygame.display.set_mode((64, 64))
DT = 1 / 30
WINTER = datetime.date(2027, 1, 20)


class Walker:
    """Just feet: something that leaves tracks, moved by hand."""

    def __init__(self, x, y, track="cat"):
        self.x, self.y, self.z = x, y, 0.0
        self.TRACK = track
        self.alive = True
        self.kind = "walker"

    def update(self, dt):
        pass

    def shadow(self):
        return None

    def sprite(self):
        return None

    airborne = False


def meadow(date=datetime.date(2026, 6, 10), snow=0.0, journal=None, seed=3):
    w = World(427, 266, seed=seed, clock=fixed_clock(11.0, date=date), weather="cloudy", weather_locked=True,
              journal=journal)
    w.entities = []           # only the walker, so nothing else leaves marks
    w.env.snow_cover = snow
    return w


def open_line(w):
    """A clear stretch of meadow, out from under the tree."""
    t = w.terrain
    for y in range(60, 240, 6):
        for x in range(30, 300, 6):
            if all(t.walkable(x + d, y) and not t.under_roof(x + d, y) for d in range(0, 101, 4)):
                return x, y
    raise AssertionError("no open stretch")


def walk(w, walker, dx, seconds=None, speed=26.0):
    steps = int(abs(dx) / speed / DT)
    for _ in range(steps):
        walker.x += speed * DT * (1 if dx > 0 else -1)
        w.marks.update(DT)


class SnowPrints(unittest.TestCase):
    def test_walking_in_snow_leaves_a_trail(self):
        w = meadow(WINTER, snow=1.0)
        x, y = open_line(w)
        cat = Walker(x, y)
        w.entities.append(cat)
        walk(w, cat, 100)
        prints = [p for p in w.marks.prints if p.kind == "snow"]
        self.assertGreater(len(prints), 12)
        self.assertTrue(all(x - 2 <= p.x <= x + 102 for p in prints))

    def test_no_prints_on_bare_ground_or_under_the_tree(self):
        w = meadow(WINTER, snow=0.0)
        x, y = open_line(w)
        cat = Walker(x, y)
        w.entities.append(cat)
        walk(w, cat, 100)
        self.assertEqual(w.marks.prints, [])
        w = meadow(WINTER, snow=1.0)
        tree = w.terrain.tree
        cat = Walker(tree.roof_cx - tree.roof_rx * 0.6, tree.roof_cy)
        w.entities.append(cat)
        walk(w, cat, tree.roof_rx * 1.2)
        self.assertFalse([p for p in w.marks.prints if w.terrain.under_roof(p.x, p.y)])

    def test_falling_snow_fills_them_in(self):
        w = meadow(WINTER, snow=1.0)
        x, y = open_line(w)
        cat = Walker(x, y)
        w.entities.append(cat)
        walk(w, cat, 60)
        self.assertTrue(w.marks.prints)
        w.env.weather.rain = 0.9
        w.env.temperature = -3.0
        w.marks._fade(400.0)
        self.assertEqual(w.marks.prints, [])

    def test_a_thaw_takes_them(self):
        w = meadow(WINTER, snow=1.0)
        x, y = open_line(w)
        cat = Walker(x, y)
        w.entities.append(cat)
        walk(w, cat, 60)
        w.env.snow_cover = 0.1
        w.marks._fade(60.0)
        self.assertEqual(w.marks.prints, [])

    def test_the_fox_and_the_deer_leave_tracks_too(self):
        for track in ("fox", "deer"):
            w = meadow(WINTER, snow=1.0)
            x, y = open_line(w)
            animal = Walker(x, y, track)
            w.entities.append(animal)
            walk(w, animal, 100)
            self.assertGreater(len(w.marks.prints), 5, track)


class MuddyPaws(unittest.TestCase):
    def test_a_puddle_leaves_a_few_muddy_prints_that_dry(self):
        w = meadow()
        x, y = open_line(w)
        fx = Puddles.__new__(Puddles)
        fx.world, fx.alive, fx._cache = w, True, {}
        fx.items = [Puddle(x + 10, y, 6, 3, 9999)]
        w.effects = [fx]
        cat = Walker(x, y)
        w.entities.append(cat)
        walk(w, cat, 100)
        mud = [p for p in w.marks.prints if p.kind == "mud"]
        self.assertTrue(4 <= len(mud) <= 14, len(mud))
        self.assertGreater(mud[0].strength, mud[-1].strength, "the mud wears off her paws")
        w.marks._fade(3600.0)
        self.assertEqual(w.marks.prints, [])


class Paths(unittest.TestCase):
    def tread(self, w, times):
        x, y = open_line(w)
        cat = Walker(x, y)
        w.entities.append(cat)
        for i in range(times):
            walk(w, cat, 100 if i % 2 == 0 else -100)
        return x, y

    def test_a_route_walked_often_wears_a_path(self):
        w = meadow()
        x, y = self.tread(w, 1)
        once = w.marks.wear.max()
        w = meadow()
        self.tread(w, 30)
        often = w.marks.wear.max()
        self.assertLess(once, 0.42, "one walk leaves no path")
        self.assertGreater(often, 0.6)

    def test_the_grass_grows_back(self):
        w = meadow()
        self.tread(w, 30)
        before = w.marks.wear.max()
        w.marks._fade(3 * 24 * 3600.0)
        self.assertLess(w.marks.wear.max(), before * 0.15)

    def test_a_path_shows_in_the_ground_picture(self):
        w = meadow()
        self.assertIs(w.marks.paint(w.terrain.ground), w.terrain.ground, "nothing to paint")
        x, y = self.tread(w, 40)
        painted = w.marks.paint(w.terrain.ground)
        changed = sum(painted.get_at((x + d, y)) != w.terrain.ground.get_at((x + d, y)) for d in range(10, 90))
        self.assertGreater(changed, 20)

    def test_paths_are_remembered_between_runs_and_fade_while_away(self):
        journal = Journal(None)
        w = meadow(journal=journal)
        self.tread(w, 30)
        before = w.marks.wear.max()
        w.marks.save()
        again = Marks(meadow(journal=journal), journal)
        self.assertAlmostEqual(float(again.wear.max()), float(before), places=2)
        later = meadow(date=datetime.date(2026, 6, 12), journal=journal)
        self.assertLess(later.marks.wear.max(), before * 0.4, "two days away: mostly grown back")
        other = meadow(journal=journal, seed=4)
        self.assertEqual(other.marks.wear.max(), 0.0, "another meadow's paths aren't this one's")


if __name__ == "__main__":
    unittest.main()
