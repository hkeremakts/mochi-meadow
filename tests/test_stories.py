"""The seasonal stories: the blackbirds' nest, the frogs, the storks and the
geese, on the real calendar (see habitat/stories.py)."""
import datetime
import math
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat import stories as st
from habitat.entities.cat import cat_library
from habitat.entities.seasonal import Fledgling
from habitat.personality import Personality
from habitat.render import Renderer
from habitat.world import World
from tests.support import fixed_clock

pygame.init()
pygame.display.set_mode((64, 64))
DT = 1 / 30
SEED = 4
YEAR = 2027


def almanac(seed=SEED, year=YEAR):
    return st.Almanac(seed, year)


def on(day, year=YEAR):
    """The date ``day`` days into the (northern) year, and the hour."""
    date = datetime.date(year, 1, 1) + datetime.timedelta(days=int(day))
    return date, (day % 1) * 24


def meadow(day, hour=None, seed=SEED, speed=1.0, weather="clear"):
    date, h = on(day)
    w = World(427, 266, seed=seed, clock=fixed_clock(h if hour is None else hour, date=date, speed=speed),
              weather=weather, weather_locked=True, personality=Personality.neutral())
    return w


def still(cat):
    """Keep Mochi where she is, awake, doing nothing."""
    cat.posture = "sit"
    cat.activity = iter(lambda: None, 1)
    cat.idle_pose()


def run(w, seconds, each=None):
    for _ in range(int(seconds / DT)):
        w.update(DT)
        if each is not None:
            each(w)


class Calendar(unittest.TestCase):
    def test_the_same_dates_every_time_and_a_little_different_each_year(self):
        a, b, c = almanac(), almanac(), almanac(year=YEAR + 1)
        self.assertEqual(a.nest.hatch, b.nest.hatch)
        self.assertEqual(a.frogs.spawn, b.frogs.spawn)
        self.assertNotEqual(a.frogs.spawn, c.frogs.spawn)
        self.assertNotEqual(almanac(seed=5).frogs.spawn, a.frogs.spawn, "each meadow its own")

    def test_the_nest_in_order_through_the_spring(self):
        nests = [almanac(seed=s).nest for s in range(120)]
        made = [n for n in nests if n is not None]
        self.assertGreater(len(made), 95, "most years they nest in the tree")
        for n in made:
            self.assertTrue(n.build < n.lay <= n.sit < n.hatch < n.fledge < n.free)
            self.assertTrue(68 <= n.build <= 118, "begun in late March or April")
            self.assertTrue(3 <= n.eggs <= 5)
            self.assertTrue(12 <= n.hatch - n.sit <= 14.5, "a fortnight's sitting")
            self.assertAlmostEqual(n.fledge % 1, 0.3, 6, "the young leave in the morning")
            self.assertLess(n.fledge - n.build, 50)

    def test_the_frogs_from_march_to_early_summer(self):
        for s in range(60):
            f = almanac(seed=s).frogs
            self.assertTrue(50 <= f.spawn <= 106, "spawn in March")
            self.assertGreater(f.spawn % 1, 0.8, "laid after dark")
            self.assertTrue(140 <= f.out <= 215, "the froglets leave in June or July")
            self.assertTrue(1 <= f.clumps <= 4)

    def test_storks_late_in_august_and_fewer_coming_back(self):
        for s in range(40):
            storks = almanac(seed=s).storks
            autumn, spring = storks.waves
            self.assertTrue(222 <= autumn[0] <= 250)
            self.assertEqual(autumn[3], "south")
            self.assertEqual(spring[3], "north")
            self.assertLess(spring[2], autumn[2])
        storks = almanac().storks
        peak = storks.waves[0][0]
        self.assertEqual(storks.strength(peak - 60)[0], 0.0, "none in June")
        self.assertEqual(storks.strength(peak + 0.5)[1], "south")

    def test_in_the_south_the_seasons_turn_round(self):
        north = datetime.datetime(2027, 4, 10, 12)
        south = datetime.datetime(2027, 10, 10, 12)
        self.assertAlmostEqual(st.story_day(north, 41.0)[1], st.story_day(south, -34.0)[1], delta=3)
        self.assertEqual(st.story_day(south, -34.0)[0], 2027)
        self.assertEqual(st.story_day(datetime.datetime(2027, 3, 1), -34.0)[0], 2026, "still last year's spring")


class TheNest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n = almanac().nest

    def look(self, day, hour=None, hen=None):
        w = meadow(day, hour)
        if hen is not None:
            w.stories.nest.hen_on = hen
            w.stories._review()
        return w.stories.nest.look

    def test_it_looks_like_the_story_so_far(self):
        n = self.n
        self.assertIsNone(self.look(n.build - 3), "not yet")
        self.assertTrue(self.look(n.build + 0.2).startswith("build"))
        self.assertEqual(self.look(n.lay + 1.1, hen=False), "eggs2", "an egg each morning")
        self.assertEqual(self.look(n.sit + 2.2, hen=True), "hen")
        self.assertEqual(self.look(n.sit + 2.2, hen=False), f"eggs{n.eggs}")
        self.assertTrue(self.look(n.hatch + 1.2, hen=False).startswith("chicks"))
        self.assertEqual(self.look(n.fledge + 3), "empty")
        self.assertIsNone(self.look(n.gone + 1))

    def test_the_chicks_are_fed_by_day_and_gape_when_they_are(self):
        w = meadow(self.n.hatch + 7.4)            # a week old, at about ten in the morning
        still(w.cat)
        w.cat.x, w.cat.y = 30.0, w.height - 30.0
        w.stories.nest.hen_on = False
        looks, worms = set(), 0

        def watch(w):
            nonlocal worms
            looks.add(w.stories.nest.look)
            worms += sum(1 for e in w.entities if e.kind == "blackbird" and e.carry == "worm")
        run(w, 900, watch)
        self.assertTrue(any(k and k.startswith("gape") for k in looks), "a parent came with food")
        self.assertGreater(worms, 0)

    def test_at_night_the_hen_broods_and_no_one_comes(self):
        w = meadow(math.floor(self.n.hatch) + 2, hour=1.0)
        visits = 0

        def watch(w):
            nonlocal visits
            visits += sum(1 for e in w.entities if e.kind == "blackbird")
        run(w, 120, watch)
        self.assertTrue(w.stories.nest.hen_on)
        self.assertEqual(w.stories.nest.look, "hen")
        self.assertEqual(visits, 0)

    def test_drawn_in_the_crown_and_fading_with_it(self):
        screen = pygame.display.set_mode((427 * 2, 266 * 2))
        w = meadow(self.n.sit + 3.4)
        w.cat.x, w.cat.y = 30.0, w.height - 30.0
        nest = w.stories.nest
        nest.hen_on = True
        w.stories._review()
        r = Renderer(screen, 2)
        r.bind(w)
        spot = (int(nest.x * 2), int((nest.y - 1) * 2))

        def pixel():
            r.draw(w)
            return tuple(screen.get_at(spot))[:3]
        with_nest = pixel()
        nest.look = None
        r.draw(w)
        without = tuple(screen.get_at(spot))[:3]
        self.assertNotEqual(with_nest, without, "the nest shows over the leaves")
        nest.look = "hen"
        w.terrain.canopies[0].fade = 0.38          # Mochi underneath: the crown goes see-through...
        faded = pixel()
        nest.look = None
        r.draw(w)
        bare = tuple(screen.get_at(spot))[:3]
        self.assertLess(sum(abs(a - b) for a, b in zip(faded, bare)), sum(abs(a - b) for a, b in zip(with_nest, without)),
                        "...and the nest with it")


class Fledglings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n = almanac().nest

    def young(self, w):
        f = Fledgling(w, w.stories, w.stories.rng)
        w.entities.append(f)
        return f

    def test_by_day_they_keep_to_cover_and_never_go_into_anything(self):
        w = meadow(self.n.fledge + 2.1)
        t = w.terrain

        def check(w):
            for e in w.entities:
                if e.kind == "fledgling" and not e.hidden and e.z < 1:
                    self.assertTrue(t.free_ground(e.x, e.y) and not t.is_water(e.x, e.y), (e.x, e.y))
        run(w, 600, check)
        self.assertTrue(any(e.kind == "fledgling" for e in w.entities))

    def test_tucked_away_at_night(self):
        w = meadow(math.floor(self.n.fledge) + 3, hour=23.5)
        for _ in range(3):
            self.young(w)
        run(w, 30)
        self.assertFalse([e for e in w.entities if e.kind == "fledgling"])

    def test_mochi_never_catches_one(self):
        w = meadow(self.n.fledge + 2.1)
        f = self.young(w)
        run(w, 6)
        cat = w.cat
        cat.posture = "stand"
        cat.x, cat.y = f.x - 22, f.y
        gen = cat.pounce(f)
        for _ in range(int(8 / DT)):
            cat.dt = DT
            try:
                next(gen)
            except StopIteration:
                break
            f.update(DT)
        self.assertTrue(f.alive)
        self.assertTrue(f.hidden or f.state == "flutter", "it got away into cover")

    def test_a_cat_near_them_gets_a_scolding(self):
        w = meadow(self.n.fledge + 2.1)
        still(w.cat)
        f = self.young(w)
        run(w, 6)
        w.cat.x, w.cat.y = f.x + 30, f.y
        scolded, cross = False, False

        def watch(w):
            nonlocal scolded, cross
            scolded |= any(getattr(e, "scolding", None) is w.cat for e in w.entities)
            cross |= w.cat.air == "cross"
        run(w, 45, watch)
        self.assertTrue(scolded, "a parent came to tell her off")
        self.assertTrue(cross, "her ears went back")


class Frogs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = almanac().frogs

    def test_the_spawn_lies_in_the_shallows(self):
        w = meadow(self.f.spawn + 2.5)
        pond = w.stories.pond
        self.assertEqual(pond.stage, "spawn")
        self.assertEqual(len(pond.clumps), self.f.clumps)
        for x, y, _ in pond.clumps:
            self.assertTrue(w.terrain.is_water(x, y))
        self.assertIn("frogspawn", w.stories.sightings)

    def test_tadpoles_keep_to_the_water(self):
        w = meadow(self.f.hatch + 20.5)
        pond = w.stories.pond
        self.assertTrue(pond.tadpoles)

        def check(w):
            for x, y, *_ in pond.tadpoles:
                self.assertTrue(w.terrain.is_water(x, y), (x, y))
        run(w, 120, check)

    def test_froglets_leave_the_pond_for_the_grass(self):
        w = meadow(self.f.out + 2.3, hour=19.5, speed=8.0)     # a short time-lapse: the evening's exodus sooner
        t = w.terrain
        seen = 0

        def check(w):
            nonlocal seen
            for e in w.entities:
                if e.kind == "froglet":
                    seen += 1
                    if e.state == "sit":
                        self.assertFalse(t.is_water(e.x, e.y))
                        self.assertTrue(t.free_ground(e.x, e.y))
        run(w, 240, check)
        self.assertGreater(seen, 0)

    def test_a_frozen_pond_shows_nothing(self):
        w = meadow(self.f.hatch + 3.5)
        w.env.ice = 1.0
        screen = pygame.display.set_mode((427 * 2, 266 * 2))
        r = Renderer(screen, 2)
        r.bind(w)
        before = pygame.surfarray.array3d(screen).copy()
        w.stories.pond.draw(r)
        self.assertTrue((pygame.surfarray.array3d(screen) == before).all())


class Migrants(unittest.TestCase):
    def test_storks_come_on_a_sunny_midday_in_late_august_only(self):
        a = almanac()
        peak = a.storks.waves[0][0]
        day = next(d for d in (peak, peak + 1, peak - 1, peak + 2, peak - 2) if a.storks.luck(d) > 0.5)

        def kettles(day, hour, weather="clear"):
            w = meadow(day, hour=hour, speed=20.0, weather=weather)
            n = 0

            def count(w):
                nonlocal n
                n = max(n, sum(1 for f in w.overhead if isinstance(f, st.StorkKettle)))
            run(w, 240, count)
            return n
        self.assertGreater(kettles(day, 12.5), 0)
        self.assertEqual(kettles(day, 2.0), 0, "no thermals at night")
        self.assertEqual(kettles(day, 12.5, "rain"), 0, "nor in the rain")
        self.assertEqual(kettles(day - 60, 12.5), 0, "nor in June")

    def test_geese_head_south_in_autumn_and_north_in_spring(self):
        w = meadow(300, hour=9.0)
        for way, sign in (("south", 1), ("north", -1)):
            heading = st.HEADINGS["geese"] + (0.0 if way == "south" else math.pi)
            skein = st.GooseSkein(w, w.stories.rng, 12, heading)
            y0 = sum(b[1] for b in skein.birds)
            for _ in range(60):
                skein.update(DT)
            self.assertGreater(sign * (sum(b[1] for b in skein.birds) - y0), 0, way)

    def test_reflections_only_on_open_water_and_shadows_only_in_sunshine(self):
        screen = pygame.display.set_mode((427 * 2, 266 * 2))
        w = meadow(236, hour=12.5)
        w.cat.x, w.cat.y = 30.0, w.height - 30.0
        kettle = st.StorkKettle(w, w.stories.rng, 30, st.HEADINGS["storks"], 300.0)
        pond = w.terrain.pond
        for i, bird in enumerate(kettle.birds):       # all of them where the pond mirrors the sky, or near it
            bird[0] = pond.cx + (i % 6 - 2.5) * 18
            bird[1] = pond.cy - st.MIRROR_NORTH + (i // 6 - 2) * 10
        r = Renderer(screen, 2)
        r.bind(w)
        r.draw(w)
        before = pygame.surfarray.array3d(screen).astype(int)
        kettle.draw_reflection(r)
        after = pygame.surfarray.array3d(screen).astype(int)
        changed = (after != before).any(axis=2)
        xs, ys = changed.nonzero()
        self.assertTrue(len(xs))
        for x, y in zip(xs[::7], ys[::7]):
            self.assertTrue(w.terrain.is_water(x // 2, y // 2), (x // 2, y // 2))
        light = pygame.Surface((w.width, w.height))
        light.fill((255, 255, 255))
        kettle.draw_shadow(light)
        self.assertLess(pygame.surfarray.array3d(light).min(), 255, "their shadows on the grass")
        w.env.clock.moment = w.env.clock.moment.replace(hour=23)
        w.env.sky.invalidate()
        w.env.update(DT)
        light.fill((255, 255, 255))
        kettle.draw_shadow(light)
        self.assertEqual(pygame.surfarray.array3d(light).min(), 255, "none in the dark")

    def test_mochi_looks_up_at_them(self):
        self.assertIn("sit_skyward_right", cat_library())
        self.assertIn("sit_skyward_left", cat_library())
        w = meadow(236, hour=12.5)
        cat = w.cat
        cat.posture = "stand"
        cat.activity = None
        cat.interruptible = True
        kettle = st.StorkKettle(w, w.stories.rng, 20, st.HEADINGS["storks"], 300.0)
        for bird in kettle.birds:
            bird[0], bird[1] = cat.x, cat.y - 40
        w.overhead.append(kettle)
        cat.attend("look_up", cat.act_look_up(kettle, "watching storks circling high overhead"))
        keys = set()
        run(w, 6, lambda w: keys.add(cat.anim.key))
        self.assertTrue(any(k and k.startswith("sit_skyward") for k in keys))


class Notices(unittest.TestCase):
    def test_each_step_of_a_story_is_noticed_once_a_year(self):
        n = almanac().nest
        w = meadow(n.hatch + 7.4)
        w.stories.nest.hen_on = False
        w.stories.nest.feeding = 3.0
        w.stories._review()
        self.assertIn("chicks", w.stories.sightings)
        texts = []
        for _ in range(3):
            w.events.timer = 0.0
            w.events.update(DT)
            texts += [c.text for c in w.captions]
            w.captions.clear()
        self.assertEqual(texts.count("The blackbird's eggs have hatched"), 1)

    def test_the_migrants_once_each_way(self):
        w = meadow(236, hour=12.5)
        w.stories.sightings = {"storks"}
        w.stories._update_sightings = lambda: None
        texts = []
        for way in ("south", "south", "north"):
            w.stories.heading["storks"] = way
            w.events.timer = 0.0
            w.events.update(DT)
            texts += [c.text for c in w.captions]
            w.captions.clear()
        self.assertEqual(texts, ["White storks circling high overhead, on their way to Africa",
                                 "White storks circling overhead, flying north again"])


class Pace(unittest.TestCase):
    def test_stories_keep_up_with_a_time_lapse_but_only_so_far(self):
        w = meadow(100, hour=10.0)
        base = w.stories.rate(60)
        w.env.clock.speed = 600
        self.assertAlmostEqual(w.stories.rate(60) / base, st.RATE_CAP)

    def test_a_day_without_a_story_goes_exactly_as_it_would_without_them(self):
        def trace(stories_on):
            w = meadow(11.4, seed=11)                  # mid-January: nothing nesting, spawning or passing over
            if not stories_on:
                w.stories.update = lambda dt: None
            out = []
            for i in range(int(180 / DT)):
                w.update(DT)
                if i % 10 == 0:
                    out.append((round(w.cat.x, 4), round(w.cat.y, 4), w.cat.activity_name, len(w.entities)))
            return out
        self.assertEqual(trace(True), trace(False))


class Serials(unittest.TestCase):
    def test_a_newcomer_is_never_taken_for_one_that_has_gone(self):
        """Mochi remembers creatures by number, not by where they sit in
        memory: a new one that lands in the same place is new to her."""
        w = meadow(11.4)
        first = Fledgling(w, w.stories, w.stories.rng)
        w.cat._ignored[first.serial] = 1e9
        serial = first.serial
        del first
        second = Fledgling(w, w.stories, w.stories.rng)
        self.assertNotEqual(second.serial, serial)
        self.assertEqual(w.cat._ignored.get(second.serial, 0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
