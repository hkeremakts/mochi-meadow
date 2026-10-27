"""Places Mochi remembers.

Where she saw a mouse, the fox, the deer or the hedgehog, and where she
found a gift.  Each memory has a strength that fades over a few days (a
fortnight and it's gone), grows when the same thing turns up there again,
and weakens when she goes back and finds nothing.  She goes back to
check, more often the more curious she is, and not straight away: a
memory has to sit for a while first.

The places are kept in the journal for each meadow, so she may go back
to a bush days after the mouse.
"""

import datetime
import math

from .settings import SETTINGS

PLACES = SETTINGS["mochi"]["places"]
SAME_PLACE = 30.0           # art pixels: closer than this is the same place
# What she's checking, as the end of a sentence ("Mochi is checking ...").
PHRASES = {
    "mouse": "the bush where she saw a mouse",
    "fox": "where she saw the fox",
    "deer": "where the deer grazed",
    "hedgehog": "where she met the hedgehog",
    "gift": "where she found the {what}",
}


class Place:
    __slots__ = ("kind", "x", "y", "look", "what", "strength", "when")

    def __init__(self, kind, x, y, look, what, strength, when):
        self.kind, self.x, self.y = kind, x, y
        self.look = look            # what she looks at when she's there
        self.what = what
        self.strength = strength    # as it was at ``when``
        self.when = when            # last time something happened here

    @property
    def phrase(self):
        return PHRASES[self.kind].format(what=self.what or "something")


def ago(when, now):
    """'yesterday', '3 days ago', 'last night'... or None for earlier today."""
    days = (now.date() - when.date()).days
    if days <= 0:
        return None
    if days == 1:
        return "last night" if when.hour >= 20 else "yesterday"
    return f"{days} days ago"


class Places:
    def __init__(self, world, journal=None):
        self.world = world
        self.journal = journal
        self.all = []
        self.load()

    def _now(self):
        return self.world.env.clock.moment

    def strength(self, place, now=None):
        hours = max(0.0, ((now or self._now()) - place.when).total_seconds() / 3600.0)
        return place.strength * math.exp(-hours / PLACES["forget_hours"])

    def remember(self, kind, x, y, look=None, what=None):
        """Something happened here: a new memory, or an old one renewed."""
        now = self._now()
        for place in self.all:
            if place.kind == kind and math.hypot(place.x - x, place.y - y) < SAME_PLACE:
                place.strength = min(PLACES["cap"], self.strength(place, now) + PLACES["renew"])
                place.when = now
                if what:
                    place.what = what
                return place
        place = Place(kind, float(x), float(y), tuple(look) if look else (float(x), float(y)), what,
                      PLACES["first"][kind], now)
        self.all.append(place)
        if len(self.all) > PLACES["keep"]:
            self.all.remove(min(self.all, key=lambda p: self.strength(p, now)))
        return place

    def visited(self, place, found):
        """She went back.  Something there makes it stronger; nothing, and
        she cares a little less."""
        now = self._now()
        if found:
            place.strength = min(PLACES["cap"], self.strength(place, now) + PLACES["renew"])
        else:
            place.strength = self.strength(place, now) * PLACES["nothing_there"]
        place.when = now
        if place.strength < PLACES["floor"] and place in self.all:
            self.all.remove(place)

    def forget(self, place):
        if place in self.all:
            self.all.remove(place)

    def pull(self, place, now=None):
        """How much a place calls her back: its strength, once it has had
        time to sink in (smoothly, over about ``ripen_minutes``)."""
        now = now or self._now()
        minutes = max(0.0, (now - place.when).total_seconds() / 60.0)
        ripe = 1.0 - math.exp(-(minutes / PLACES["ripen_minutes"]) ** 2)
        s = self.strength(place, now)
        return 0.0 if s < PLACES["floor"] else s * ripe

    # --- remembering between runs ---------------------------------------

    def save(self):
        if self.journal is None:
            return
        now = self._now()
        spots = [{"kind": p.kind, "x": round(p.x, 1), "y": round(p.y, 1), "look": [round(v, 1) for v in p.look],
                  "what": p.what, "strength": round(p.strength, 3), "when": p.when.isoformat(timespec="minutes")}
                 for p in self.all if self.strength(p, now) >= PLACES["floor"]]
        self.journal.notes["places"] = {"seed": self.world.seed, "size": [self.world.width, self.world.height],
                                        "spots": spots}

    def load(self):
        data = self.journal.notes.get("places") if self.journal is not None else None
        if not isinstance(data, dict):
            return
        if data.get("seed") != self.world.seed or data.get("size") != [self.world.width, self.world.height]:
            return              # a different meadow, or a different screen
        for spot in data.get("spots", []):
            try:
                if spot["kind"] not in PHRASES:
                    continue
                self.all.append(Place(spot["kind"], float(spot["x"]), float(spot["y"]),
                                      tuple(float(v) for v in spot["look"]), spot.get("what"),
                                      float(spot["strength"]), datetime.datetime.fromisoformat(spot["when"])))
            except (KeyError, ValueError, TypeError):
                continue
