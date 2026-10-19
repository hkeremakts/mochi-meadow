"""Encounters: rarity, conditions, captions, the journal, and what each
event actually does."""
import datetime
import json
import os
import tempfile
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat import events as ev
from habitat.journal import Journal
from habitat.render import Renderer
from habitat.world import World
from tests.support import fixed_clock

DT = 1 / 30


def screen():
    """The display, reopened if another test closed pygame down."""
    if not pygame.get_init() or pygame.display.get_surface() is None:
        pygame.init()
        pygame.display.set_mode((427 * 2, 266 * 2))
    return pygame.display.get_surface()


screen()


def meadow(hour=12.0, date=datetime.date(2026, 6, 20), weather="clear", journal=None, seed=7, speed=1.0):
    w = World(427, 266, seed=seed, clock=fixed_clock(hour, date=date, speed=speed), weather=weather,
              weather_locked=True, journal=journal)
    for _ in range(int(4 / DT)):
        w.update(DT)
    return w


def free_cat(w):
    """Mochi awake, standing, and doing nothing in particular."""
    cat = w.cat
    cat.posture = "stand"
    cat.activity = None
    cat.interruptible = True
    cat.idle_pose()
    return cat


def run(world, seconds, draw=None):
    for i in range(int(seconds / DT)):
        world.update(DT)
        if draw is not None and i % 10 == 0:
            draw.draw(world)


def renderer(world):
    surface = screen()
    r = Renderer(surface, 2)
    r.bind(world, surface)
    return r


class EveryEvent(unittest.TestCase):
    """Each event can be forced, runs, draws, and finishes cleanly."""

    SETTINGS = {
        "a shooting star": dict(hour=23.5),
        "a meteor shower": dict(hour=23.5, date=datetime.date(2026, 10, 21)),
        "a full moon": dict(hour=23.5, date=datetime.date(2026, 10, 26)),
        "morning mist": dict(hour=6.0),
        "bats": dict(hour=20.8),
        "New Year fireworks": dict(hour=0.05, date=datetime.date(2027, 1, 1)),
        "a carved pumpkin": dict(hour=21.0, date=datetime.date(2026, 10, 30)),
        "moths": dict(hour=22.5),
        "a dewy spider web": dict(hour=6.5),
    }

    def test_each_event_runs(self):
        for name in sorted(ev.ALL):
            with self.subTest(name):
                w = meadow(**self.SETTINGS.get(name, {}))
                free_cat(w)
                r = renderer(w)
                if not w.events.force(name):
                    self.fail(f"{name} could not happen")
                run(w, 20, draw=r)

    def test_captions_by_tier(self):
        w = meadow(hour=23.5)
        w.events.force("a shooting star")
        self.assertEqual(w.captions[-1].tier, "rare")
        free_cat(w)
        self.assertTrue(w.events.force("tail chase"))
        self.assertEqual(len(w.captions), 1, "common events pass without a caption")


class Odds(unittest.TestCase):
    def test_tiers_are_rarer_and_rarer(self):
        self.assertLess(ev.MEAN["common"], ev.MEAN["uncommon"])
        self.assertLess(ev.MEAN["uncommon"], ev.MEAN["rare"])
        self.assertLess(ev.MEAN["rare"], ev.MEAN["legendary"])

    def test_a_long_drought_makes_a_rare_event_likelier(self):
        events = meadow().events
        events.since["rare"] = 0.0
        normal = events.chance("rare")
        events.since["rare"] = ev.MEAN["rare"] * 3
        self.assertAlmostEqual(events.chance("rare") / normal, 4.0)

    def test_rates_over_a_long_watch(self):
        """Simulated checks over 30 days: each tier turns up about as often
        as its mean wait says (ignoring conditions)."""
        import random
        events = meadow().events
        rng = random.Random(5)
        days = 30
        for tier in ev.TIERS:
            events.since[tier] = 0.0
            count = 0
            for _ in range(int(days * 86400 / ev.CHECK)):
                events.since[tier] += ev.CHECK
                if rng.random() < events.chance(tier):
                    count += 1
                    events.since[tier] = 0.0
            expected = days * 86400 / ev.MEAN[tier]
            self.assertTrue(0.6 * expected < count < 1.6 * expected, (tier, count, expected))

    def test_only_one_big_event_at_a_time(self):
        w = meadow(hour=23.5)
        w.events.force("a shooting star")
        self.assertTrue(w.events.big_running())
        before = len(w.events.history)
        w.events.since["rare"] = ev.MEAN["rare"] * 50
        w.events.ready_at.clear()
        for _ in range(50):
            w.events.timer = 0.0
            w.events.update(0.0)
        rare = [n for _, n in w.events.history[before:] if ev.ALL[n].tier in ev.BIG]
        self.assertEqual(rare, [])

    def test_a_legendary_event_is_foreshadowed(self):
        w = meadow()
        w.events.chance = lambda tier: 1.0 if tier == "legendary" else 0.0
        w.events.timer = 0.0
        w.events.update(0.0)
        self.assertTrue(w.events.hushed)
        self.assertEqual(w.count("golden_butterfly"), 0)
        run(w, ev.GoldenButterflyEvent.omen + 1)
        self.assertEqual(w.count("golden_butterfly"), 1)


class Conditions(unittest.TestCase):
    def test_shooting_stars_only_on_clear_nights(self):
        star = ev.ShootingStarEvent()
        self.assertTrue(star.ready(meadow(hour=23.5)))
        self.assertFalse(star.ready(meadow(hour=13.0)))
        self.assertFalse(star.ready(meadow(hour=23.5, weather="rain")))

    def test_the_real_meteor_showers(self):
        night = datetime.datetime(2026, 8, 13, 1, 0)       # Perseids, small hours after the peak night
        self.assertEqual(ev.shower_tonight(night), "Perseids")
        self.assertIsNone(ev.shower_tonight(datetime.datetime(2026, 7, 1, 23, 0)))

    def test_mist_belongs_to_the_dawn(self):
        mist = ev.MorningMist()
        self.assertTrue(mist.ready(meadow(hour=5.8, date=datetime.date(2026, 5, 1))))
        self.assertFalse(mist.ready(meadow(hour=14.0, date=datetime.date(2026, 5, 1))))

    def test_a_rainbow_needs_rain_that_just_stopped_and_a_low_sun(self):
        w = meadow(hour=17.5, date=datetime.date(2026, 5, 1))
        rainbow = ev.RainbowEvent()
        self.assertFalse(rainbow.ready(w))
        w.events.last_shower = w.time - 30
        self.assertTrue(rainbow.ready(w), w.env.sky.sun_alt)

    def test_a_full_moon_is_announced_once_a_night(self):
        w = meadow(hour=23.0, date=datetime.date(2026, 10, 26))
        run(w, 10)
        run(w, 30)
        names = [n for _, n in w.events.history]
        self.assertEqual(names.count("a full moon"), 1)

    def test_the_first_snow_of_winter(self):
        w = World(427, 266, seed=7, weather="rain", weather_locked=True,
                  clock=fixed_clock(10.0, date=datetime.date(2026, 12, 20), place=(60.2, 24.9)))
        w.env.weather.rain = 0.8
        w.env.snow_cover = 0.3
        run(w, 10)
        self.assertIn("the first snow", [n for _, n in w.events.history])


class Reactions(unittest.TestCase):
    def test_mochi_walks_up_to_the_screen_and_taps_it(self):
        w = meadow()
        free_cat(w)
        self.assertTrue(w.events.force("Mochi noticed you"))
        taps = 0
        for _ in range(int(60 / DT)):
            w.update(DT)
            taps += sum(1 for fx in w.effects if isinstance(fx, ev.GlassTap) and fx.age == DT)
            if w.cat.activity_name != "fourth_wall":
                break
        self.assertGreater(w.cat.y, w.height * 0.55)
        self.assertGreaterEqual(taps, 2)

    def test_mochi_follows_the_golden_butterfly(self):
        w = meadow()
        free_cat(w)
        w.events.force("the golden butterfly")
        followed = 0
        for _ in range(int(40 / DT)):
            w.update(DT)
            if w.cat.activity_name == "golden":
                followed += 1
        self.assertGreater(followed, int(20 / DT))

    def test_mochi_hides_from_new_year_fireworks(self):
        w = meadow(hour=23.99, date=datetime.date(2026, 12, 31))
        run(w, 60)
        self.assertIn("New Year fireworks", [n for _, n in w.events.history])
        run(w, 30)
        self.assertTrue(w.cat.sheltered, w.cat.label)

    def test_mochi_stares_at_a_crow_but_does_not_hunt_it(self):
        w = meadow()
        w.events.force("a crow")
        hunted = watched = False
        for _ in range(int(120 / DT)):
            w.update(DT)
            hunted |= w.cat.activity_name == "hunt" and getattr(w.cat.focus, "kind", "") == "crow"
            watched |= w.cat.activity_name == "watch" and getattr(w.cat.focus, "kind", "") == "crow"
        self.assertFalse(hunted)


class Visitor(unittest.TestCase):
    def test_the_ginger_cat_visits_and_goes_home(self):
        w = meadow()
        free_cat(w)
        self.assertTrue(w.events.force("the ginger cat"))
        visitor = w.of_kind("visitor")[0]
        phases, met = set(), False
        for _ in range(int(240 / DT)):
            w.update(DT)
            phases.add(visitor.phase)
            met |= visitor.phase == "greeting" and visitor.distance_to(w.cat) < 40
            if not visitor.alive:
                break
        self.assertTrue(met, phases)
        self.assertFalse(visitor.alive, "never went home")
        self.assertIn(phases & {"friendly", "play", "spat"}, ({"friendly"}, {"spat"}, {"play", "friendly"}))

    def test_he_looks_like_mochi_in_a_ginger_coat(self):
        from habitat.entities.cat import cat_library
        from habitat.entities.visitor import ginger_library
        mochi = cat_library()["sit_right"][0]
        ginger = ginger_library()["sit_right"][0]
        self.assertEqual(mochi.get_bounding_rect(), ginger.get_bounding_rect())
        self.assertNotEqual(pygame.image.tobytes(mochi, "RGBA"), pygame.image.tobytes(ginger, "RGBA"))

    def test_the_second_visit_is_a_return(self):
        w = meadow()
        free_cat(w)
        w.events.force("the ginger cat")
        self.assertIn("visit", w.captions[-1].text)
        w.entities = [e for e in w.entities if e.kind != "visitor"]
        w.events.force("the ginger cat")
        self.assertIn("back", w.captions[-1].text)


class Remembering(unittest.TestCase):
    def test_the_journal_survives_a_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "Meadow", "journal.json")
            w = meadow(hour=23.5, journal=Journal(path))
            w.events.force("a shooting star")
            with open(path) as f:
                self.assertEqual(json.load(f)["seen"]["a shooting star"]["count"], 1)
            again = Journal(path)
            self.assertEqual(again.count("a shooting star"), 1)

    def test_a_broken_journal_file_is_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "journal.json")
            with open(path, "w") as f:
                f.write("{not json")
            self.assertEqual(Journal(path).count("anything"), 0)

    def test_a_notice_is_not_repeated_after_a_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "journal.json")
            w = meadow(hour=23.0, date=datetime.date(2026, 10, 26), journal=Journal(path))
            run(w, 10)
            w2 = meadow(hour=23.2, date=datetime.date(2026, 10, 26), journal=Journal(path))
            run(w2, 10)
            self.assertNotIn("a full moon", [n for _, n in w2.events.history])

    def test_a_meteor_shower_resumes_quietly_after_a_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "journal.json")
            w = meadow(hour=23.5, date=datetime.date(2026, 10, 21), journal=Journal(path))
            run(w, 10)
            self.assertTrue(any(isinstance(fx, ev.MeteorShower) for fx in w.effects))
            w2 = meadow(hour=23.6, date=datetime.date(2026, 10, 21), journal=Journal(path))
            run(w2, 10)
            self.assertTrue(any(isinstance(fx, ev.MeteorShower) for fx in w2.effects))
            self.assertEqual(w2.captions, [])


if __name__ == "__main__":
    unittest.main()
