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


if __name__ == "__main__":
    unittest.main()
