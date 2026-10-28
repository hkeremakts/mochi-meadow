"""How Mochi gets about: she arrives where she's going, without circling it."""
import datetime
import math
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat.entities.cat import ARRIVED
from habitat.personality import Personality
from habitat.world import World
from tests.support import fixed_clock

pygame.init()
pygame.display.set_mode((64, 64))
DT = 1 / 30


def meadow():
    w = World(427, 266, seed=11, clock=fixed_clock(12.0, date=datetime.date(2026, 6, 20)), weather="clear",
              weather_locked=True, personality=Personality.neutral())
    w.entities = [w.cat]
    cat = w.cat
    cat.posture = "stand"
    cat.activity = None
    cat.idle_pose()
    cat._perceive = lambda: None
    return w


def open_ground(w, room=30):
    """A spot with clear ground all round it (every pixel)."""
    t = w.terrain
    for y in range(60, 230, 7):
        for x in range(40, 380, 7):
            if not t.blocked[y - room // 2:y + room // 2 + 1, x - room:x + room + 1].any():
                return float(x), float(y)
    raise AssertionError("no open ground")


def walk(w, goal, seconds=20.0, **kw):
    """Drive go() to ``goal``: (status, seconds taken, total turning in turns)."""
    cat = w.cat
    gen = cat.go(*goal, **kw)
    turned, last, t = 0.0, cat.heading, 0.0
    try:
        while t < seconds:
            cat.dt = DT
            cat.moved = 0.0
            next(gen)
            turned += abs((cat.heading - last + math.pi) % (2 * math.pi) - math.pi)
            last = cat.heading
            cat.anim.update(DT, cat.moved)
            t += DT
    except StopIteration as done:
        return done.value, t, turned / (2 * math.pi)
    return None, t, turned / (2 * math.pi)


class Arriving(unittest.TestCase):
    def test_a_goal_just_behind_her_is_reached_without_circling(self):
        for behind in (3.0, 6.0, 10.0, 16.0):
            for side in (0.0, 2.0, -3.0):
                w = meadow()
                cat = w.cat
                cat.x, cat.y = open_ground(w)
                cat.heading = 0.0                        # facing right; the goal is behind her
                cat.speed = 20.0                         # and she's still walking
                status, t, turns = walk(w, (cat.x - behind, cat.y + side))
                with self.subTest(behind=behind, side=side):
                    self.assertEqual(status, ARRIVED)
                    self.assertLess(t, 6.0)
                    self.assertLess(turns, 1.0, "no laps round the goal")

    def test_a_goal_beside_her_at_walking_pace(self):
        for angle in (60, 90, 120, 150):
            w = meadow()
            cat = w.cat
            cat.x, cat.y = open_ground(w)
            cat.heading = 0.0
            cat.speed = 26.0
            a = math.radians(angle)
            status, t, turns = walk(w, (cat.x + math.cos(a) * 8, cat.y + math.sin(a) * 8))
            with self.subTest(angle=angle):
                self.assertEqual(status, ARRIVED)
                self.assertLess(turns, 1.0)

    def test_she_never_goes_round_in_circles_over_an_hour(self):
        w = World(427, 266, seed=11, clock=fixed_clock(9.0, date=datetime.date(2026, 6, 20)), weather="clear",
                  weather_locked=True, personality=Personality.neutral())
        cat = w.cat
        spinning, last = 0.0, cat.heading
        for _ in range(int(1800 / DT)):
            w.update(DT)
            rate = abs((cat.heading - last + math.pi) % (2 * math.pi) - math.pi) / DT
            last = cat.heading
            if rate > 2.0 and cat.speed > 1.0:
                spinning += DT
        self.assertLess(spinning, 30.0, f"{spinning:.0f} s spent turning hard while on the move")


def an_hour(seed=11):
    """Turn speeds (deg/s) while walking, speeds (px/s), and seconds per clip."""
    import collections
    w = World(427, 266, seed=seed, clock=fixed_clock(9.0, date=datetime.date(2026, 6, 20)), weather="clear",
              weather_locked=True, personality=Personality.neutral())
    cat = w.cat
    turns, speeds, clips = [], [], collections.Counter()
    last, px, py = cat.heading, cat.x, cat.y
    for _ in range(int(1800 / DT)):
        w.update(DT)
        key = (cat.anim.key or "").split("~")[0].rsplit("_", 1)[0]
        moved = math.hypot(cat.x - px, cat.y - py)
        px, py = cat.x, cat.y
        rate = math.degrees(abs((cat.heading - last + math.pi) % (2 * math.pi) - math.pi)) / DT
        last = cat.heading
        if key in ("amble", "walk", "trot") and moved > 0.25 * DT * 10:
            turns.append(rate)
            speeds.append(moved / DT)
            clips[key] += DT
    return sorted(turns), sorted(speeds), clips


class Walking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.turns, cls.speeds, cls.clips = an_hour()

    def test_turns_are_curves_not_snaps(self):
        worst = self.turns[int(0.99 * (len(self.turns) - 1))]
        self.assertLess(worst, 160, f"the sharpest 1% of walking turns ran at {worst:.0f} deg/s")

    def test_she_ambles_as_well_as_walks(self):
        self.assertGreater(self.clips["amble"], 20)
        self.assertGreater(self.clips["walk"], 20)
        slow, quick = self.speeds[int(0.1 * len(self.speeds))], self.speeds[int(0.9 * len(self.speeds))]
        self.assertGreater(quick, slow * 1.6, "her pace varies")

    def test_turning_on_the_spot_is_in_steps(self):
        w = meadow()
        cat = w.cat
        cat.x, cat.y = open_ground(w)
        cat.heading = 0.0
        gen = cat.pivot(math.pi)
        legs, turning = [], []
        try:
            while True:
                cat.dt = DT
                before = cat.heading
                next(gen)
                legs.append(cat.moved)
                turning.append(abs((cat.heading - before + math.pi) % (2 * math.pi) - math.pi) > 1e-6)
        except StopIteration:
            pass
        self.assertIn(False, turning[1:-1], "short pauses between the steps")
        self.assertTrue(all(m == 0.0 for m, t in zip(legs, turning) if not t), "the legs rest while she pauses")
        seconds = len(turning) * DT
        self.assertGreater(seconds, 0.9, "a half turn takes a few steps, not a spin")
        self.assertLess(seconds, 2.5)


if __name__ == "__main__":
    unittest.main()
