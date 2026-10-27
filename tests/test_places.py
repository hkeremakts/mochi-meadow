"""Places Mochi remembers: where she saw a mouse, a fox, a deer; where she
found a gift.  She goes back to check, sometimes days later."""
import collections
import datetime
import os
import random
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat.entities.wildlife import Mouse
from habitat.journal import Journal
from habitat.personality import Personality
from habitat.places import PLACES
from habitat.world import World
from tests.support import fixed_clock

pygame.init()
pygame.display.set_mode((64, 64))
DT = 1 / 30
DAY = datetime.date(2026, 6, 20)


def meadow(journal=None, hour=12.0, date=DAY, seed=7, p=None):
    w = World(427, 266, seed=seed, clock=fixed_clock(hour, date=date), weather="clear", weather_locked=True,
              journal=journal, personality=p or Personality.neutral())
    w.entities = [w.cat]
    w.cat.posture = "stand"
    w.cat.activity = None
    w.cat.interruptible = True
    w.cat.idle_pose()
    return w


def run(w, seconds, watch=None):
    seen = []
    for _ in range(int(seconds / DT)):
        w.update(DT)
        if watch is not None:
            seen.append(watch(w))
    return seen


def near_bush(w):
    """A bush, with Mochi standing a little way off it."""
    spot = w.terrain.spots["shelter"][0]
    w.cat.x, w.cat.y = float(spot.approach[0]), float(spot.approach[1])
    return spot.owner


def hours_ago(w, place, hours):
    place.when = w.env.clock.moment - datetime.timedelta(hours=hours)


class Noticing(unittest.TestCase):
    def test_she_remembers_the_bush_where_she_saw_a_mouse(self):
        w = meadow()
        bush = near_bush(w)
        w.cat._start("sit", w.cat.act_sit())
        w.entities.append(Mouse(w, bush))
        run(w, 1.0)
        mice = [p for p in w.places.all if p.kind == "mouse"]
        self.assertEqual(len(mice), 1)
        self.assertLess(abs(mice[0].look[0] - bush.x) + abs(mice[0].look[1] - bush.y), 1)
        self.assertTrue(w.terrain.walkable(mice[0].x, mice[0].y), "somewhere she can stand")

    def test_one_mouse_is_one_memory(self):
        w = meadow()
        bush = near_bush(w)
        w.cat._start("sit", w.cat.act_sit())
        w.entities.append(Mouse(w, bush))
        run(w, 4.0)
        place = w.places.all[0]
        self.assertAlmostEqual(place.strength, PLACES["first"]["mouse"])

    def test_another_mouse_there_makes_it_stronger(self):
        w = meadow()
        bush = near_bush(w)
        w.cat._start("sit", w.cat.act_sit())
        w.entities.append(Mouse(w, bush))
        run(w, 1.0)
        w.entities.append(Mouse(w, bush))
        run(w, 1.0)
        self.assertEqual(len(w.places.all), 1)
        self.assertGreater(w.places.all[0].strength, PLACES["first"]["mouse"])

    def test_a_sleeping_cat_sees_nothing(self):
        w = meadow()
        bush = near_bush(w)
        w.cat.posture = "sleep"
        w.cat._start("nap", w.cat.act_sleep_on())
        w.entities.append(Mouse(w, bush))
        run(w, 1.0)
        self.assertEqual(w.places.all, [])

    def test_she_remembers_where_she_found_a_gift(self):
        w = meadow()
        w.cat._start("gift", w.cat.act_gift("feather"))
        run(w, 120)
        gifts = [p for p in w.places.all if p.kind == "gift"]
        self.assertEqual(len(gifts), 1)
        self.assertEqual(gifts[0].what, "feather")


class Forgetting(unittest.TestCase):
    def test_memories_fade_over_days(self):
        w = meadow()
        place = w.places.remember("fox", 200, 150)
        now = w.env.clock.moment
        fresh = w.places.strength(place, now)
        later = w.places.strength(place, now + datetime.timedelta(days=2))
        much_later = w.places.strength(place, now + datetime.timedelta(days=12))
        self.assertGreater(fresh, later)
        self.assertGreater(later, 0.25, "two days on she still remembers")
        self.assertLess(much_later, PLACES["floor"], "after a fortnight it's gone")

    def test_they_are_kept_between_runs(self):
        journal = Journal()
        w = meadow(journal)
        w.places.remember("fox", 200, 150)
        w.places.save()
        again = meadow(journal, date=DAY + datetime.timedelta(days=1))
        self.assertEqual([p.kind for p in again.places.all], ["fox"])
        self.assertEqual(again.places.all[0].when, w.places.all[0].when)

    def test_another_meadow_has_its_own(self):
        journal = Journal()
        w = meadow(journal)
        w.places.remember("fox", 200, 150)
        w.places.save()
        self.assertEqual(meadow(journal, seed=8).places.all, [])

    def test_forgotten_ones_are_dropped_on_saving(self):
        journal = Journal()
        w = meadow(journal)
        hours_ago(w, w.places.remember("fox", 200, 150), 24 * 30)
        w.places.save()
        self.assertEqual(journal.notes["places"]["spots"], [])

    def test_only_a_handful_are_kept(self):
        w = meadow()
        for i in range(PLACES["keep"] + 10):
            w.places.remember("gift", 20 + (i % 9) * 45, 30 + (i // 9) * 45, what="leaf")
        self.assertEqual(len(w.places.all), PLACES["keep"])


class GoingBack(unittest.TestCase):
    def test_she_goes_back_to_check(self):
        w = meadow()
        bush = near_bush(w)
        place = w.places.remember("mouse", *w.terrain.spots["shelter"][0].approach, look=(bush.x, bush.y))
        hours_ago(w, place, 3)
        w.cat.x, w.cat.y = float(w.terrain.spawn[0]), float(w.terrain.spawn[1])
        w.cat._start("revisit", w.cat.act_revisit(place))
        seen = run(w, 90, watch=lambda w: (w.cat.label, w.cat.x, w.cat.y))
        checking = [(x, y) for label, x, y in seen if label == "checking the bush where she saw a mouse"]
        self.assertTrue(checking)
        x, y = checking[0]
        self.assertLess(abs(x - place.x) + abs(y - place.y), 30)

    def test_nothing_there_and_she_cares_less(self):
        w = meadow()
        place = w.places.remember("fox", *w.terrain.spawn)
        hours_ago(w, place, 3)
        before = w.places.strength(place, w.env.clock.moment)
        w.cat._start("revisit", w.cat.act_revisit(place))
        run(w, 90)
        self.assertLess(w.places.strength(place, w.env.clock.moment), before * 0.8)

    def test_it_is_one_of_the_things_she_chooses(self):
        w = meadow()
        place = w.places.remember("fox", *w.terrain.spawn)
        hours_ago(w, place, 5)
        w.cat.rng = random.Random(1)
        picks = collections.Counter(w.cat._choose()[0] for _ in range(600))
        self.assertGreater(picks["revisit"], 5)

    def test_not_straight_away(self):
        w = meadow()
        w.places.remember("fox", *w.terrain.spawn)        # just now
        w.cat.rng = random.Random(1)
        picks = collections.Counter(w.cat._choose()[0] for _ in range(600))
        self.assertLess(picks["revisit"], 3)

    def test_a_timid_cat_keeps_away_from_where_the_fox_was(self):
        def visits(bold):
            p = Personality.neutral()
            p.traits["bold"] = bold
            w = meadow(p=p)
            hours_ago(w, w.places.remember("fox", *w.terrain.spawn), 5)
            w.cat.rng = random.Random(2)
            return collections.Counter(w.cat._choose()[0] for _ in range(1500))["revisit"]
        self.assertLess(visits(0.05) * 2, visits(0.95))

    def test_a_caption_when_it_was_days_ago(self):
        w = meadow()
        place = w.places.remember("fox", *w.terrain.spawn)
        hours_ago(w, place, 30)
        w.cat._start("revisit", w.cat.act_revisit(place))
        texts = {c.text for frame in run(w, 60, watch=lambda w: list(w.captions)) for c in frame}
        self.assertIn("Mochi went back to where she saw the fox yesterday", texts)

    def test_no_caption_for_this_morning(self):
        w = meadow()
        place = w.places.remember("fox", *w.terrain.spawn)
        hours_ago(w, place, 2)
        w.cat._start("revisit", w.cat.act_revisit(place))
        texts = {c.text for frame in run(w, 60, watch=lambda w: list(w.captions)) for c in frame}
        self.assertFalse([t for t in texts if "went back" in t])


if __name__ == "__main__":
    unittest.main()
