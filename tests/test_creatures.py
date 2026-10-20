"""The birds and small creatures: true-to-life sizes, soft landings, and
how each one reacts to the cat."""
import math
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat.entities.cat import cat_library
from habitat.entities.wildlife import Bee, Frog, Hedgehog, Pigeon, Sparrow, art
from habitat.entities.wildlife import Deer as DeerEntity
from habitat.entities.wildlife import Duck as DuckEntity
from habitat.entities.wildlife import Heron as HeronEntity
from habitat.entities.wildlife import Fox as FoxEntity
from tests.support import fixed_clock
from habitat.world import World

pygame.init()
pygame.display.set_mode((64, 64))
DT = 1 / 60


def world(hour=12.0, weather="clear", seed=7):
    w = World(427, 266, seed=seed, clock=fixed_clock(hour), weather=weather, weather_locked=True)
    w.entities = [w.cat]          # start from a quiet meadow
    w.director.populate = lambda: None
    return w


def park_cat(w, x, y):
    """Hold the cat still at (x, y) by giving her an endless nap there."""
    cat = w.cat
    cat.x, cat.y = float(x), float(y)

    def stay():
        while True:
            cat.speed = 0.0
            yield
    cat._start("test", stay(), interruptible=False)


def width(frame):
    return frame.get_bounding_rect().width


class Sizes(unittest.TestCase):
    def test_birds_are_true_to_size_next_to_the_cat(self):
        # Nose to tail tip: cat ~76 cm, pigeon ~32 cm, sparrow ~16 cm.
        cat = width(cat_library()["stand_right"][0])
        pigeon = width(art()["pigeon"]["idle"][0])
        sparrow = width(art()["sparrow"]["idle"][0])
        self.assertTrue(0.36 < pigeon / cat < 0.5, pigeon / cat)
        self.assertTrue(0.4 < sparrow / pigeon < 0.65, sparrow / pigeon)


    def test_no_bird_frame_is_clipped_by_its_canvas(self):
        for species in ("pigeon", "sparrow"):
            for key, frames in art()[species].items():
                for frame in frames:
                    box = frame.get_bounding_rect()
                    w, h = frame.get_size()
                    self.assertTrue(box.left > 0 and box.top > 0 and box.right < w and box.bottom < h,
                                    f"{species} {key} touches the edge: {box}")


    def test_the_fox_is_bigger_than_the_cat(self):
        # Nose to tail tip: red fox ~110 cm, cat ~76 cm.
        cat = width(cat_library()["stand_right"][0])
        fox = width(art()["fox"]["stand_right"][0])
        self.assertTrue(1.3 < fox / cat < 1.6, fox / cat)
        for key, frames in art()["fox"].items():
            for frame in frames:
                box = frame.get_bounding_rect()
                self.assertTrue(box.left > 0 and box.top > 0 and box.right < frame.get_width(), key)


    def test_the_deer_towers_over_the_cat(self):
        # Shoulder height: roe deer ~70 cm, cat ~25 cm; the deer's head is higher still.
        cat = cat_library()["stand_right"][0].get_bounding_rect().height
        deer = art()["deer"]["stand_right"][0].get_bounding_rect().height
        self.assertTrue(1.8 < deer / cat < 3.2, deer / cat)
        for key, frames in art()["deer"].items():
            for frame in frames:
                box = frame.get_bounding_rect()
                self.assertTrue(box.left > 0 and box.top > 0 and box.right < frame.get_width(), key)


class Flight(unittest.TestCase):
    def fly_in(self, cls):
        w = world()
        park_cat(w, 30, 240)
        bird = cls(w, 300, 150)
        w.entities.append(bird)
        track = []
        for _ in range(int(20 / DT)):
            w.update(DT)
            track.append((bird.x, bird.y, bird.z, bird.state))
            if bird.state == "ground":
                break
        return bird, track

    def test_birds_touch_down_slowly(self):
        for cls in (Pigeon, Sparrow):
            bird, track = self.fly_in(cls)
            with self.subTest(cls.__name__):
                self.assertEqual(bird.state, "ground", "never landed")
                (x0, y0, z0, _), (x1, y1, z1, _) = track[-12], track[-2]
                ground_speed = math.hypot(x1 - x0, y1 - y0) / (10 * DT)
                sink = (z0 - z1) / (10 * DT)
                self.assertLess(ground_speed, 20.0)
                self.assertLess(sink, 15.0)

    def test_flight_has_no_jumps(self):
        bird, track = self.fly_in(Pigeon)
        for (x0, y0, z0, _), (x1, y1, z1, _) in zip(track, track[1:]):
            self.assertLess(math.hypot(x1 - x0, y1 - y0, z1 - z0), Pigeon.CRUISE * 1.4 * DT)

    def test_a_cat_rushing_in_flushes_the_flock(self):
        w = world()
        park_cat(w, 30, 240)
        flock = [Pigeon(w, 200 + i * 20, 150) for i in range(3)]
        for b in flock:
            b.flock = flock
            b.x, b.y, b.z, b.state = b.target[0], b.target[1], 0.0, "ground"
            w.entities.append(b)
        w.cat.x, w.cat.y, w.cat.speed = 190.0, 150.0, 90.0
        w.update(DT)
        self.assertTrue(all(b.state in ("taking_off", "leaving") for b in flock))


class Fox(unittest.TestCase):
    def test_the_fox_crosses_pauses_and_leaves(self):
        w = world(hour=19.6)
        park_cat(w, 30, 240)
        fox = FoxEntity(w)
        self.assertTrue(fox.ok)
        w.entities.append(fox)
        states = []
        for _ in range(int(90 / DT)):
            w.update(DT)
            if not states or states[-1] != fox.state:
                states.append(fox.state)
            if not fox.alive:
                break
        self.assertEqual(states, ["trot", "sniff", "look", "trot"])
        self.assertFalse(fox.alive)

    def test_fox_paws_stay_planted(self):
        """Stride-locked playback: the body covers one stride per cycle."""
        from habitat import fox_art
        self.assertAlmostEqual(fox_art.STRIDES["trot"], fox_art.TROT_STRIDE * fox_art.SCALE)


class DeerVisit(unittest.TestCase):
    def test_the_deer_grazes_and_walks_on(self):
        w = world(hour=6.0)
        park_cat(w, 30, 240)
        deer = DeerEntity(w)
        self.assertTrue(deer.ok)
        w.entities.append(deer)
        states = []
        for _ in range(int(150 / DT)):
            w.update(DT)
            if not states or states[-1] != deer.state:
                states.append(deer.state)
            if not deer.alive:
                break
        self.assertIn("graze", states)
        self.assertFalse(deer.alive)
        self.assertFalse(deer.fleeing)

    def test_a_cat_coming_close_makes_her_bound_away(self):
        w = world(hour=6.0)
        park_cat(w, 30, 240)
        deer = DeerEntity(w)
        w.entities.append(deer)
        for _ in range(int(40 / DT)):
            w.update(DT)
            if deer.state == "graze":
                break
        self.assertFalse(deer.fleeing)
        # An awake cat (the parked one stands still) comes within a few lengths.
        w.cat.posture = "stand"
        w.cat.x, w.cat.y = deer.x - 50, deer.y
        for _ in range(int(2 / DT)):
            w.update(DT)
        self.assertTrue(deer.fleeing)


class PondVisitors(unittest.TestCase):
    def test_the_heron_fishes_and_flies_off(self):
        w = world(hour=10.0)
        park_cat(w, 30, 240)
        heron = HeronEntity(w)
        self.assertTrue(heron.ok)
        w.entities.append(heron)
        states = set()
        for _ in range(int(240 / DT)):
            w.update(DT)
            states.add(heron.state)
            if not heron.alive:
                break
        self.assertTrue({"hunt", "strike", "leave"} <= states, states)
        self.assertFalse(heron.alive)

    def test_ducklings_follow_their_mother_into_the_water_and_away(self):
        w = world(hour=10.0)
        park_cat(w, 30, 240)
        hen = DuckEntity(w, brood=4)
        self.assertTrue(hen.ok)
        w.entities.append(hen)
        w.entities.extend(hen.ducklings)
        swam = False
        for _ in range(int(420 / DT)):
            w.update(DT)
            if hen.state == "swim":
                swam |= sum(w.terrain.is_water(d.x, d.y) for d in hen.ducklings) >= 3
            if not hen.alive and w.count("duckling") == 0:
                break
        self.assertTrue(swam, "the ducklings never swam behind her")
        self.assertEqual(w.count("duckling"), 0)
        self.assertFalse(hen.alive)


class SmallCreatures(unittest.TestCase):
    def test_a_frog_dives_when_the_cat_comes_close(self):
        w = world(hour=20.0)
        frog = Frog(w)
        frog.state, frog.timer = "sit", 30.0
        w.entities.append(frog)
        park_cat(w, frog.x + 60, frog.y)
        for _ in range(30):
            w.update(DT)
        self.assertEqual(frog.state, "sit")
        w.cat.x = frog.x + 20
        for _ in range(60):
            w.update(DT)
        self.assertIn(frog.state, ("hop", "under", "swim"))

    def test_a_hedgehog_curls_up_when_the_cat_is_near(self):
        w = world(hour=23.0)
        hog = Hedgehog(w)
        hog.x, hog.y = 200.0, 150.0
        w.entities.append(hog)
        park_cat(w, 300, 150)
        for _ in range(30):
            w.update(DT)
        self.assertNotEqual(hog.state, "ball")
        w.cat.x, w.cat.y = hog.x + 15, hog.y
        w.update(DT)
        self.assertEqual(hog.state, "ball")

    def test_bees_visit_flowers(self):
        w = world()
        park_cat(w, 30, 240)
        bee = Bee(w)
        w.entities.append(bee)
        for _ in range(int(30 / DT)):
            w.update(DT)
            if bee.state == "visit":
                break
        self.assertEqual(bee.state, "visit")
        nearest = min(math.hypot(p[0] - bee.x, p[1] - bee.y) for p in w.terrain.perches)
        self.assertLess(nearest, 2.0)

    def test_snails_come_out_after_rain(self):
        w = World(427, 266, seed=7, clock=fixed_clock(10.0), weather="rain", weather_locked=True)
        for _ in range(int(90 / (1 / 30))):
            w.update(1 / 30)
        self.assertEqual(w.count("snail"), 0, "snails wait for the rain to ease")
        w.env.weather.force("clear", locked=True)
        w.env.weather.rain = 0.0
        for _ in range(int(40 / (1 / 30))):
            w.update(1 / 30)
        self.assertGreater(w.count("snail"), 0)


if __name__ == "__main__":
    unittest.main()
