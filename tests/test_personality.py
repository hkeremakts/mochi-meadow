"""Mochi's character: kept between runs, and visible in what she does."""
import datetime
import os
import random
import tempfile
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat.entities.wildlife import Crow, Fox, Sparrow
from habitat.journal import Journal
from habitat.personality import BEST_FRIENDS, FAVOURITE_AFTER, TRAITS, Personality
from habitat.world import World
from tests.support import fixed_clock

pygame.init()
pygame.display.set_mode((64, 64))
DT = 1 / 30


def cat(traits=None, quirks=(), **mood):
    p = Personality.neutral()
    p.traits.update(traits or {})
    p.quirks = list(quirks)
    for k, v in mood.items():
        setattr(p, k, v)
    return p


def meadow(p, hour=12.0, seed=7, date=datetime.date(2026, 6, 20)):
    w = World(427, 266, seed=seed, clock=fixed_clock(hour, date=date), weather="clear", weather_locked=True,
              personality=p)
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


class Kept(unittest.TestCase):
    def test_the_same_cat_comes_back_after_a_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "journal.json")
            first = Personality.from_journal(Journal(path))
            self.assertTrue(first.first_meeting)
            again = Personality.from_journal(Journal(path))
            self.assertFalse(again.first_meeting)
            self.assertEqual(first.traits, again.traits)
            self.assertEqual(first.quirks, again.quirks)

    def test_a_new_name_is_remembered(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "journal.json")
            Personality.from_journal(Journal(path), name="Pamuk")
            self.assertEqual(Personality.from_journal(Journal(path)).name, "Pamuk")

    def test_cats_differ(self):
        cats = [Personality.roll(random.Random(i)) for i in range(20)]
        self.assertGreater(len({c.describe() for c in cats}), 10)
        for c in cats:
            self.assertEqual(len(c.quirks), 2)
            self.assertFalse({"night owl", "early riser"} <= set(c.quirks))
            self.assertTrue(all(0 <= c[t] <= 1 for t in TRAITS))

    def test_she_is_introduced_the_first_time(self):
        p = Personality.roll(random.Random(3))
        p.first_meeting = True
        w = meadow(p)
        self.assertIn("Meet Mochi", w.captions[-1].text)

    def test_describe_reads_naturally(self):
        p = cat({"curious": 0.95, "bold": 0.9, "lazy": 0.7})
        self.assertEqual(p.describe(), "curious, bold and a little lazy")
        self.assertEqual(Personality.neutral().describe(), "easy-going")


class Character(unittest.TestCase):
    def asleep_share(self, lazy):
        total = 0.0
        for seed in (2, 5, 9):
            w = meadow(cat({"lazy": lazy}), seed=seed)
            w.cat.needs.energy = 0.6
            total += sum(run(w, 600, watch=lambda w: w.cat.posture == "sleep")) / (600 / DT)
        return total / 3

    def test_a_lazy_cat_sleeps_more(self):
        self.assertGreater(self.asleep_share(0.95), self.asleep_share(0.05) + 0.1)

    def test_a_kneader_kneads_before_a_nap(self):
        w = meadow(cat(quirks=["kneader"]))
        w.cat._start("nap", w.cat.act_nap())
        labels = run(w, 40, watch=lambda w: w.cat.label)
        self.assertIn("kneading", labels)
        self.assertLess(labels.index("kneading"), labels.index("napping"))

    def test_a_timid_cat_hides_from_the_fox(self):
        w = meadow(cat({"bold": 0.05, "playful": 0.9}), hour=19.6)
        w.cat.needs.play = 1.0
        fox = Fox(w)
        w.entities.append(fox)
        labels = set(run(w, 40, watch=lambda w: w.cat.label))
        self.assertIn("hiding from the fox", labels)

    def test_a_bold_cat_hisses_at_a_crow(self):
        hissed = False
        for seed in (1, 2, 3):
            w = meadow(cat({"bold": 0.95, "playful": 0.9}), seed=seed)
            w.cat.needs.play = 1.0
            crow = Crow(w, w.cat.x + 50, w.cat.y)
            crow.x, crow.y, crow.z, crow.state = crow.target[0], crow.target[1], 0.0, "ground"
            w.entities.append(crow)
            hissed |= "hissing at a crow" in run(w, 30, watch=lambda w: w.cat.label)
        self.assertTrue(hissed)

    def test_a_chatterer_chatters_at_sparrows(self):
        chattered = False
        for seed in (1, 2, 3):
            w = meadow(cat({"playful": 0.9}, quirks=["chatterer"]), seed=seed)
            w.cat.needs.play = 1.0
            b = Sparrow(w, w.cat.x + 70, w.cat.y)
            b.x, b.y, b.z, b.state = b.target[0], b.target[1], 0.0, "ground"
            b.stay = 1e9
            w.entities.append(b)
            chattered |= any("chattering" in s for s in run(w, 30, watch=lambda w: w.cat.label))
        self.assertTrue(chattered)

    def test_a_bowl_watcher_waits_for_dinner(self):
        w = meadow(cat(quirks=["bowl watcher"]), hour=17.8)
        w.cat.needs.hunger = 0.3
        w.cat.needs.energy = 0.9
        labels = run(w, 60, watch=lambda w: w.cat.label)
        self.assertIn("waiting for dinner", labels)


class Gifts(unittest.TestCase):
    def test_she_carries_a_gift_to_the_bowl_and_leaves_it(self):
        w = meadow(cat())
        w.entities = [w.cat]            # nothing to distract her on the way
        w.cat._start("gift", w.cat.act_gift("feather"))
        carried = False
        for _ in range(int(120 / DT)):
            w.update(DT)
            if w.cat.carrying:
                carried = True
                frame, _, _ = w.cat.sprite()
                self.assertIsNot(frame, w.cat.anim.frame, "the gift is drawn in her mouth")
            if w.count("gift"):
                break
        self.assertTrue(carried)
        gift = w.of_kind("gift")[0]
        bowl = w.terrain.bowl
        self.assertLess(abs(gift.x - bowl[0]) + abs(gift.y - bowl[1]), 40)
        self.assertIn("left you a feather", w.captions[-1].text)

    def test_the_gift_is_taken_in_at_dinner(self):
        w = meadow(cat())
        from habitat.entities.wildlife import Gift
        w.bowl_fill = 0.0
        w.update(DT)
        w.entities.append(Gift(w, *w.terrain.bowl, "leaf"))
        w.bowl_fill = 1.0
        w.update(DT)
        self.assertEqual(w.count("gift"), 0)

    def test_a_bow_on_her_birthday(self):
        p = cat()
        p.born = datetime.date(2025, 6, 20)
        w = meadow(p, date=datetime.date(2026, 6, 20))
        self.assertTrue(w.cat.birthday)
        w.update(DT)
        frame, _, _ = w.cat.sprite()
        self.assertIsNot(frame, w.cat.anim.frame)
        w.events.timer = 0.0
        w.update(DT)
        self.assertIn("birthday", " ".join(c.text for c in w.captions))
        self.assertFalse(meadow(p, date=datetime.date(2026, 6, 21)).cat.birthday)
        p.born = datetime.date(2026, 6, 20)
        self.assertFalse(meadow(p, date=datetime.date(2026, 6, 20)).cat.birthday, "not on the day she was met")


class Memory(unittest.TestCase):
    def test_a_favourite_nap_spot(self):
        p = cat()
        w = meadow(p)
        spot = w.terrain.spots["nap"][0]
        for i in range(FAVOURITE_AFTER):
            became = p.napped(w.terrain.seed, spot.x, spot.y)
        self.assertTrue(became)
        self.assertIsNotNone(p.favourite(w.terrain.seed))
        picks = [w.cat._nap_spot() for _ in range(40)]
        self.assertGreater(sum(1 for s in picks if s is spot), 15)

    def test_friendship_grows_into_naps_together(self):
        p = cat()
        p.friends["ginger"] = BEST_FRIENDS
        p.mood = 0.6
        snuggled = False
        for seed in (1, 2, 3, 4):
            w = meadow(p, seed=seed)
            w.events.force("the ginger cat")
            visitor = w.of_kind("visitor")[0]
            phases = run(w, 200, watch=lambda w: visitor.phase)
            snuggled |= "snuggle" in phases
        self.assertTrue(snuggled)

    def test_a_good_visit_counts(self):
        p = cat()
        p.visit("ginger", "friendly")
        p.visit("ginger", "play")
        p.visit("ginger", "spat")
        self.assertEqual(p.friendship("ginger"), 1)

    def test_moods_fade_back(self):
        p = cat()
        p.feel(-1.0)
        for _ in range(3600):
            p.settle(1.0)
        self.assertGreater(p.mood, 0.0)


if __name__ == "__main__":
    unittest.main()
