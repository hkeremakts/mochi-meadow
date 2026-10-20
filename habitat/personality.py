"""Who Mochi is: the same cat every time the meadow starts.

Five traits (0..1) are rolled once, the first time the meadow ever runs,
and kept in the journal, so every Mochi is a little different and stays
herself: one is a lazy pond-gazer, another a bold, playful night owl.

    playful       chases more, zoomies, tail chasing
    lazy          tires sooner, naps longer, loafs
    curious       explores, sniffs at new things, watches the pond
    bold          stares down crows, stands her ground with foxes
    affectionate  meows, slow-blinks, comes to the screen

On top of the traits she has two quirks (from QUIRKS), a mood that the
day's events push up and down, a favourite nap spot that she settles on
over time, and a friendship with the ginger cat next door that grows with
every good visit.
"""

import random

from .settings import SETTINGS

TRAITS = ("playful", "lazy", "curious", "bold", "affectionate")
QUIRKS = {
    "kneader": "kneads before every nap",
    "pond gazer": "loves to sit and watch the pond",
    "sunbather": "follows the sun and sprawls in it",
    "bowl watcher": "waits by the bowl before mealtimes",
    "chatterer": "chatters at birds",
    "night owl": "livelier at night",
    "early riser": "up at first light",
    "loafer": "a champion loafer",
}
# How a trait value reads in a sentence.
WORDS = {
    "playful": ("serious", "playful"),
    "lazy": ("energetic", "lazy"),
    "curious": ("unbothered", "curious"),
    "bold": ("timid", "bold"),
    "affectionate": ("aloof", "affectionate"),
}
FAVOURITE_AFTER = SETTINGS["mochi"]["favourite_after"]   # naps in one spot before it is her favourite
BEST_FRIENDS = SETTINGS["mochi"]["best_friends"]         # good visits before the ginger cat naps beside her


def _date(text):
    import datetime
    try:
        return datetime.date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


class Personality:
    def __init__(self, traits, quirks, name="Mochi", journal=None):
        self.traits = dict(traits)
        self.quirks = list(quirks)
        self.name = name
        self.journal = journal
        self.mood = 0.2
        self.naps = {}           # "seed:x,y" -> naps taken there
        self.friends = {}        # "ginger" -> good visits minus bad ones
        self.first_meeting = False
        self.born = None          # the day she was first met (a date)

    # --- making one -----------------------------------------------------

    @classmethod
    def neutral(cls):
        """Every trait at the middle, no quirks: the cat the tests know."""
        return cls({t: 0.5 for t in TRAITS}, [])

    @classmethod
    def roll(cls, rng, name="Mochi"):
        traits = {}
        for t in TRAITS:
            # Most cats are middling in most things, with one or two
            # strong leanings.
            v = rng.betavariate(1.6, 1.6)
            traits[t] = round(v, 2)
        quirks = rng.sample(sorted(QUIRKS), 2)
        if "night owl" in quirks and "early riser" in quirks:
            quirks.remove("early riser")
            quirks.append(rng.choice([q for q in sorted(QUIRKS) if q not in quirks + ["early riser"]]))
        return cls(traits, quirks, name)

    @classmethod
    def from_journal(cls, journal, name=None):
        """The cat in the journal, or a new one rolled (and kept) on the first
        ever run."""
        data = journal.notes.get("mochi")
        if data:
            p = cls(data.get("traits", {}), data.get("quirks", []), data.get("name", "Mochi"), journal)
            for t in TRAITS:
                p.traits.setdefault(t, 0.5)
            p.mood = data.get("mood", 0.2)
            p.naps = dict(data.get("naps", {}))
            p.friends = dict(data.get("friends", {}))
            if name and name != p.name:
                p.name = name
                p.save()
            p.first_meeting = False
            p.born = _date(journal.since)
            return p
        p = cls.roll(random.Random(), name or "Mochi")
        p.journal = journal
        p.first_meeting = True
        p.born = _date(journal.since)
        p.save()
        return p

    def save(self):
        if self.journal is None:
            return
        self.journal.note("mochi", {
            "name": self.name, "traits": self.traits, "quirks": self.quirks, "mood": round(self.mood, 2),
            "naps": self.naps, "friends": self.friends,
        })

    # --- reading it -------------------------------------------------------

    def __getitem__(self, trait):
        return self.traits.get(trait, 0.5)

    def has(self, quirk):
        return quirk in self.quirks

    def lean(self, trait, low=0.6, high=1.6):
        """A weight multiplier: ``low`` for the least of the trait, ``high``
        for the most, 1 in between."""
        return low + (high - low) * self[trait]

    def describe(self):
        """'curious and bold, a little lazy'."""
        strong = sorted(TRAITS, key=lambda t: -abs(self[t] - 0.5))
        parts = []
        for t in strong[:3]:
            v = self[t]
            if abs(v - 0.5) < 0.12:
                continue
            word = WORDS[t][1 if v > 0.5 else 0]
            parts.append(("a little " if abs(v - 0.5) < 0.25 else "") + word)
        if not parts:
            return "easy-going"
        if len(parts) == 1:
            return parts[0]
        return ", ".join(parts[:-1]) + " and " + parts[-1]

    @property
    def mood_word(self):
        m = self.mood
        if m > 0.55:
            return "happy"
        if m > 0.15:
            return "content"
        if m > -0.25:
            return "calm"
        return "grumpy"

    # --- living -----------------------------------------------------------

    def feel(self, delta):
        """Something good (positive) or bad (negative) happened."""
        self.mood = max(-1.0, min(1.0, self.mood + delta))

    def settle(self, dt):
        """Moods fade back toward her usual temper."""
        usual = 0.1 + 0.25 * self["affectionate"] - 0.1 * self["bold"]
        self.mood += (usual - self.mood) * min(1.0, dt / 900.0)

    def nap_key(self, seed, x, y):
        return f"{seed}:{round(x)},{round(y)}"

    def napped(self, seed, x, y):
        """Count a nap in a spot; True the moment it becomes her favourite."""
        key = self.nap_key(seed, x, y)
        self.naps[key] = self.naps.get(key, 0) + 1
        if len(self.naps) > 40:  # keep the journal small
            for k in sorted(self.naps, key=self.naps.get)[:len(self.naps) - 40]:
                del self.naps[k]
        self.save()
        return self.naps[key] == FAVOURITE_AFTER and self.favourite(seed) == key

    def favourite(self, seed):
        """Her favourite nap spot in this meadow (a nap key), if she has one."""
        mine = {k: n for k, n in self.naps.items() if k.startswith(f"{seed}:") and n >= FAVOURITE_AFTER}
        return max(mine, key=mine.get) if mine else None

    def friendship(self, who="ginger"):
        return self.friends.get(who, 0)

    def visit(self, who, outcome):
        good = outcome in ("friendly", "play")
        self.friends[who] = max(-3, self.friendship(who) + (1 if good else -1))
        self.feel(0.3 if good else -0.3)
        self.save()
