"""The creatures of the seasonal stories (see stories.py): the blackbirds
nesting in the old tree, their fledglings, and the froglets leaving the
pond.

The blackbirds go about errands written as generators, the way Mochi's
activities are: down onto the grass, a few quick runs and a stop to
listen, a stab and a tug, and up to the nest with the worm.  Anything
urgent (telling the cat off, fleeing her) is pushed on top of the errand,
which carries on afterwards.

They draw on the story's own random numbers, never the world's.
"""

import math

from .. import bird_art, story_art
from ..chance import sample
from ..settings import SETTINGS
from ..util import clamp
from .base import Entity
from .wildlife import art, bank_points

NEST = SETTINGS["stories"]["nest"]


def _toward(a, b):
    return 1 if b > a else -1


class Blackbird(Entity):
    """One of the pair nesting in the old tree, on an errand: a beakful of
    dry grass for the nest, worms for the chicks or the fledglings, the
    hen's break from sitting, or telling the cat off.  It runs over the
    grass in bursts, stops dead to listen, and stabs for worms."""

    kind = "blackbird"
    CRUISE = 60.0
    RUN = 24.0
    WARY = (30.0, 46.0, 66.0)     # flee distance for a still, walking, running cat
    SHADOW = 4.4

    def __init__(self, world, story, hen, errand, rng, at_nest=False, young=None):
        self.story = story
        self.hen = hen
        self.rng = rng
        self.species = "blackbird_hen" if hen else "blackbird"
        self.lib = art()[self.species]
        nest = story.nest
        if at_nest and nest is not None:
            x, y, z = nest.rim(rng.choice((-1, 1)))
        else:
            side = rng.choice((-1, 1))
            x, y, z = (-20.0 if side < 0 else world.width + 20.0), rng.uniform(30, world.height - 30), \
                rng.uniform(40, 70)
        super().__init__(world, x, y)
        self.z = z
        self.facing = 1 if x < world.width / 2 else -1
        self.carry = None          # "worm" or "straw" in the bill
        self.scolding = None       # the cat it is telling off
        self.at_nest = at_nest
        self.leaving = False
        self.young = young
        self.moved = 0.0
        self.dt = 0.0
        self.plans = [getattr(self, f"_{errand}")()]
        self._play("idle", fps=0.0)

    # --- for the cat -------------------------------------------------------
    def interest(self, cat):
        if self.z > 1.0 or self.leaving:
            return 0.0
        d = self.distance_to(cat)
        return 0.0 if d > 140 else 0.6 * (1.0 - d / 140.0) + 0.15

    def on_pounce(self, cat):
        self._flee()

    startle = scare = on_pounce

    def notices_crouch(self, cat):
        if self.z < 1.0 and self.distance_to(cat) < 40:
            self._flee()

    @property
    def hidden(self):
        return False

    @property
    def can_scold(self):
        return self.scolding is None and not self.leaving and not self.at_nest

    # --- what the story asks of it ------------------------------------------
    def scold(self, cat):
        self.plans.append(self._scold_at(cat))

    def go_home(self):
        """Dusk: the hen back onto her nest, anyone else off to roost."""
        if self.leaving:
            return
        stage = self.story.nest_stage.name if self.story.nest_stage else None
        if self.hen and stage in ("laying", "sitting", "chicks") and not self.story.nest.hen_on:
            self.plans = [self.to_nest("settle")]
        else:
            self.plans = [self.leave()]

    def _flee(self):
        if self.leaving or self.z > 1.0:
            return
        stage = self.story.nest_stage.name if self.story.nest_stage else None
        cat = self.world.cat
        if stage in ("sitting", "chicks", "fledglings") and self.rng.random() < 0.5:
            self.plans.append(self._scold_at(cat))      # up, and straight into a scolding
        else:
            self.plans = [self.leave()]

    # --- moving -----------------------------------------------------------
    def _play(self, name, fps=None, stride=None, loop=True, restart=False):
        key = f"{name}~{self.carry}" if self.carry and f"{name}~{self.carry}" in self.lib else name
        self.anim.play(key, self.lib[key], fps=fps, stride=stride, loop=loop, restart=restart)

    def _threatened(self):
        cat = self.world.cat
        speed = getattr(cat, "speed", 0.0)
        still, walking, running = self.WARY
        reach = still if speed < 12 else walking if speed < 40 else running
        return self.distance_to(cat) < reach and cat.posture != "sleep"

    def wait(self, seconds, watch=True):
        """Stay put for a while; False if the cat came too close."""
        t = 0.0
        while t < seconds:
            if watch and self.z < 1.0 and self._threatened():
                return False
            t += self.dt
            yield
        return True

    def fly_to(self, tx, ty, tz=0.0):
        """Fly to (tx, ty), arriving ``tz`` up: a rise, a direct line, a glide
        in and a flare to land."""
        x0, y0, z0 = self.x, self.y, self.z
        dist = max(1.0, math.hypot(tx - x0, ty - y0))
        lift = clamp(dist * 0.18, 6.0, 26.0)
        travelled = 0.0
        self.at_nest = False
        while True:
            dx, dy = tx - self.x, ty - self.y
            d = math.hypot(dx, dy)
            if d < 0.8:
                break
            speed = self.CRUISE * clamp(d / 26.0, 0.35, 1.0)
            step = min(d, speed * self.dt)
            self.x += dx / d * step
            self.y += dy / d * step
            travelled += step
            f = clamp(travelled / dist, 0.0, 1.0)
            self.z = z0 + (tz - z0) * f + lift * math.sin(math.pi * f)
            if abs(dx) > 0.5:
                self.facing = _toward(0, dx)
            if d < 9:
                self._play("flare", fps=10, loop=False)
            elif f > 0.55 and self.rng.random() < 0.6:
                self._play("glide", fps=0.0)
            else:
                self._play("flap", fps=16)
            yield
        self.x, self.y, self.z = tx, ty, tz
        self._play("idle", fps=0.0)

    def run_to(self, tx, ty):
        """Over the grass in a quick run; False if the cat put it up."""
        while True:
            dx, dy = tx - self.x, ty - self.y
            d = math.hypot(dx, dy)
            if d < 0.6:
                break
            if self._threatened():
                return False
            step = min(d, self.RUN * self.dt)
            self.x += dx / d * step
            self.y += dy / d * step
            self.moved = step
            if abs(dx) > 0.3:
                self.facing = _toward(0, dx)
            self._play("walk", stride=bird_art.STRIDE[self.species])
            yield
        self._play("idle", fps=0.0)
        return True

    def _ground_spot(self, around, lo, hi, keep_off=60.0):
        """A patch of open grass ``lo``..``hi`` from ``around``, away from
        the cat and not under the tree."""
        world = self.world
        t = world.terrain
        cat = world.cat
        rng = self.rng
        for _ in range(16):
            a = rng.uniform(0, 2 * math.pi)
            r = rng.uniform(lo, hi)
            x, y = around[0] + math.cos(a) * r, around[1] + math.sin(a) * r * 0.6
            if not (14 < x < world.width - 14 and 26 < y < world.height - 8):
                continue
            if not t.walkable(x, y) or t.under_roof(x, y) or math.hypot(x - cat.x, y - cat.y) < keep_off:
                continue
            return x, y
        return None

    def _landing(self, near=None):
        """Somewhere to come down: within a short flight of the tree (or of
        ``near``)."""
        around = near or self.story.nest.foot
        return self._ground_spot(around, 24 if near is None else 10, 110 if near is None else 34, keep_off=70.0)

    def forage(self, find, near=None):
        """Run, stop, listen, stab, until it has ``find`` ("worm" or
        "straw") in its bill.  False if the cat put it up first."""
        rng = self.rng
        tries = rng.randint(2, 5)
        for i in range(tries + 3):
            spot = self._ground_spot(near or (self.x, self.y), 8, 26, keep_off=50.0)
            if spot is not None:
                ok = yield from self.run_to(*spot)
                if not ok:
                    return False
            self._play("listen", fps=6, loop=False, restart=True)
            ok = yield from self.wait(rng.uniform(0.5, 1.6))
            if not ok:
                return False
            self._play("peck", fps=10, loop=False, restart=True)
            ok = yield from self.wait(0.5)
            if not ok:
                return False
            if i >= tries - 1 and rng.random() < 0.7:
                if find == "worm":
                    self._play("tug", fps=7, loop=False, restart=True)
                    ok = yield from self.wait(1.0)
                    if not ok:
                        return False
                self.carry = find
                self._play("idle", fps=0.0)
                yield from self.wait(0.4, watch=False)
                return True
        return False

    def to_nest(self, what):
        """Up to the nest's rim: to work grass into it, to feed the chicks,
        or (the hen) to settle on it."""
        nest = self.story.nest
        side = 1 if self.x > nest.x else -1
        x, y, z = nest.rim(side)
        yield from self.fly_to(x, y, z)
        self.facing = -side
        self.at_nest = True
        if what == "settle":
            self.story.hen_settles()
            self.alive = False
            yield
            return
        if what == "feed":
            nest.feeding = 3.2               # the chicks are all mouth
            nest.dirty = True
        self._play("feed", fps=5, loop=False, restart=True)
        yield from self.wait(1.3, watch=False)
        self.carry = None
        self._play("idle", fps=0.0)
        yield from self.wait(self.rng.uniform(0.6, 1.8), watch=False)

    def leave(self):
        """Off out of the meadow."""
        self.leaving = True
        self.scolding = None
        world = self.world
        side = -1 if self.x < world.width / 2 else 1
        if self.rng.random() < 0.3:
            side = -side
        tx = -30.0 if side < 0 else world.width + 30.0
        ty = clamp(self.y + self.rng.uniform(-60, 60), 20, world.height - 20)
        yield from self.fly_to(tx, ty, 55.0)
        self.alive = False

    # --- errands -------------------------------------------------------------
    def _build(self):
        """Nest material: down for a beakful of dry grass, up into the tree."""
        for _ in range(self.rng.randint(1, 3)):
            spot = self._landing()
            if spot is None:
                break
            yield from self.fly_to(*spot)
            found = yield from self.forage("straw")
            if not found and self.carry is None:
                break
            yield from self.to_nest("build")
            if self.story.nest_stage is None or self.story.nest_stage.name != "building":
                break
        yield from self.leave()

    def _feed(self):
        """Worms for the chicks: from the grass, up to the nest, again."""
        for _ in range(self.rng.randint(1, 3)):
            spot = self._landing()
            if spot is None:
                break
            yield from self.fly_to(*spot)
            found = yield from self.forage("worm")
            if not found and self.carry is None:
                break
            yield from self.to_nest("feed")
            if self.story.nest_stage is None or self.story.nest_stage.name != "chicks":
                break
        yield from self.leave()

    def _break(self):
        """The hen's break from sitting: down to the grass to feed herself,
        then back onto the eggs."""
        nest = self.story.nest
        spot = self._landing()
        if spot is not None:
            yield from self.fly_to(*spot)
            while self.world.time < nest.hen_until:
                found = yield from self.forage("worm")
                self.carry = None              # (that one she eats)
                if not found:
                    yield from self.leave()    # put up: she'll be back by another way
                    return
        yield from self.to_nest("settle")

    def _return(self):
        """Back from wherever she went: straight onto the eggs."""
        yield from self.to_nest("settle")

    def _feed_young(self):
        """Worms for a fledgling: found near it, then a hop over and into
        its open mouth."""
        young = self.young
        spot = self._landing(near=(young.x, young.y)) or self._landing()
        if spot is None:
            yield from self.leave()
            return
        yield from self.fly_to(*spot)
        for _ in range(self.rng.randint(1, 3)):
            if not young.alive or young.hidden:
                break
            found = yield from self.forage("worm", near=(young.x, young.y))
            if not found:
                break
            side = 1 if self.x > young.x else -1
            t = self.world.terrain
            if not t.free_ground(young.x + side * 7, young.y):
                side = -side                 # (the bush is on that side)
            if t.free_ground(young.x + side * 7, young.y):
                ok = yield from self.run_to(young.x + side * 7, young.y)
                if not ok or not young.alive or young.hidden:
                    break
            self.facing = _toward(self.x, young.x)
            young.beg(1.8, self)
            self._play("feed", fps=6, loop=False, restart=True)
            yield from self.wait(1.2, watch=False)
            self.carry = None
            self._play("idle", fps=0.0)
            yield from self.wait(self.rng.uniform(1.0, 3.0))
        yield from self.leave()

    def _scold(self):
        yield from self._scold_at(self.world.cat)
        yield from self.leave()

    def _scold_at(self, cat):
        """Tell the cat off from a safe distance: tail flicking, calling,
        never letting her closer; a cat after a fledgling gets a swoop
        low over her head first."""
        self.scolding = cat
        world = self.world
        hunting = cat.activity_name == "hunt" and getattr(getattr(cat, "focus", None), "kind", "") == "fledgling"
        if hunting:
            yield from self.fly_to(cat.x + self.rng.uniform(-6, 6), cat.y - 2, 12.0)
        spot = self._ground_spot((cat.x, cat.y), 34, 52, keep_off=32.0)
        if spot is None:
            self.scolding = None
            return
        yield from self.fly_to(*spot)
        end = world.time + sample(self.rng, NEST["scold_seconds"])
        reach = NEST["scold_distance"]
        while world.time < end and self.distance_to(cat) < reach * 1.8 and cat.posture != "sleep":
            if self.distance_to(cat) < 26:
                spot = self._ground_spot((cat.x, cat.y), 36, 54, keep_off=34.0)
                if spot is not None:
                    yield from self.fly_to(*spot)
            self.facing = _toward(self.x, cat.x)
            self._play("scold", fps=8)
            yield
        self.scolding = None
        self._play("idle", fps=0.0)

    # --- the frame -------------------------------------------------------------
    def update(self, dt):
        self.dt = dt
        self.moved = 0.0
        while self.plans:
            try:
                next(self.plans[-1])
                break
            except StopIteration:
                self.plans.pop()
        if not self.plans:
            self.alive = False
        self.anim.update(dt, self.moved)

    def sprite(self):
        return self.anim.frame, bird_art.ANCHORS[self.species], self.facing < 0

    def shadow(self):
        if self.at_nest or self.z > 40:
            return None
        k = 1.0 / (1.0 + self.z * 0.011)
        return self.SHADOW * k, self.SHADOW * 0.3 * k, int(76 / (1.0 + self.z * 0.012))


class Fledgling(Entity):
    """A young blackbird out of the nest: speckled and stub-tailed, it sits
    tight by a bush most of the time, hops about a little, begs with its
    wings quivering when a parent comes with food, and flutters off
    clumsily into cover if the cat gets too close."""

    kind = "fledgling"

    def __init__(self, world, story, rng, from_nest=False):
        self.story = story
        self.rng = rng
        self.lib = art()["fledgling"]
        self.cover = self._cover_spot(world)
        x, y = self.cover
        super().__init__(world, x, y)
        self.facing = rng.choice((-1, 1))
        self.state = "hidden"
        self.timer = rng.uniform(0.5, 4.0)
        self.flight = None
        self.leaving = False
        nest = story.nest
        if from_nest and nest is not None:
            # The first morning: out of the nest and down, all flap.
            nx, ny, nz = nest.rim(rng.choice((-1, 1)))
            self.x, self.y, self.z = nx, ny, nz
            land = self._near_cover(10, 26) or self.cover
            self._flutter(land, hide=False)
        self.anim.play("idle", self.lib["idle"], fps=1.2)

    def _cover_spot(self, world):
        """By a bush (or the foot of the tree), where it can dive in."""
        t = world.terrain
        rng = self.rng
        places = [(b.x, b.y, b.rx, b.ry) for b in t.bushes]
        if t.tree is not None:
            places.append((t.tree.x, t.tree.y, 6.0, 3.0))
        rng.shuffle(places)
        for bx, by, rx, ry in places:
            for _ in range(10):
                a = rng.uniform(0.15 * math.pi, 0.85 * math.pi)        # the front of it, toward you
                x, y = bx + math.cos(a) * (rx + 3), by + math.sin(a) * (ry + 2)
                if t.free_ground(x, y) and not t.is_water(x, y) and 10 < x < world.width - 10 \
                        and 20 < y < world.height - 4:
                    return x, y
        return world.width / 2, world.height / 2

    def _near_cover(self, lo, hi, start=None):
        """Somewhere a hop from cover, the way there clear (not through the
        tree's trunk or the edge of a bush)."""
        t = self.world.terrain
        sx, sy = start or (self.x, self.y)
        for _ in range(10):
            a = self.rng.uniform(0, 2 * math.pi)
            r = self.rng.uniform(lo, hi)
            x, y = self.cover[0] + math.cos(a) * r, self.cover[1] + math.sin(a) * r * 0.6
            if not (10 < x < self.world.width - 10 and 20 < y < self.world.height - 4):
                continue
            if all(t.free_ground(sx + (x - sx) * k, sy + (y - sy) * k) and not t.is_water(sx + (x - sx) * k,
                                                                                         sy + (y - sy) * k)
                   for k in (0.0, 0.25, 0.5, 0.75, 1.0)):
                return x, y
        return None

    # --- for the cat -------------------------------------------------------
    @property
    def hidden(self):
        return self.state in ("hidden", "roost")

    def interest(self, cat):
        if self.hidden or self.z > 2.0:
            return 0.0
        d = self.distance_to(cat)
        return 0.0 if d > 150 else 0.75 * (1.0 - d / 150.0) + 0.2

    def on_pounce(self, cat):
        self._escape()

    startle = on_pounce

    def notices_crouch(self, cat):
        if self.distance_to(cat) < 34 and self.rng.random() < self.world.dt_hint * 1.5:
            self._escape()

    def leave(self):
        self.go_to_roost()

    # --- what the parents and the story ask -----------------------------------
    def beg(self, seconds, parent):
        if self.state in ("sit", "beg"):
            self.state, self.timer = "beg", seconds
            self.facing = 1 if parent.x > self.x else -1

    def go_to_roost(self):
        """Into cover for the night (or for good)."""
        self.leaving = True
        if self.state in ("hidden", "roost"):
            self.state, self.timer = "roost", 0.0
        elif self.flight is None:
            self._flutter(self.cover, hide=True)

    def _escape(self):
        if self.flight is not None or self.hidden:
            return
        self._flutter(self.cover, hide=True)

    def _flutter(self, to, hide):
        """A short, clumsy flight: fast beats, legs dangling."""
        self.flight = (self.x, self.y, self.z, to[0], to[1], 0.0, hide)
        self.state = "flutter"
        self.facing = 1 if to[0] > self.x else -1
        self.anim.play("flap", self.lib["flap"], fps=16)

    # --- the frame -------------------------------------------------------------
    def update(self, dt):
        world = self.world
        rng = self.rng
        cat = world.cat
        if self.state == "flutter":
            x0, y0, z0, tx, ty, t, hide = self.flight
            dist = max(1.0, math.hypot(tx - x0, ty - y0))
            t += dt * 30.0 / dist
            f = min(1.0, t)
            self.x, self.y = x0 + (tx - x0) * f, y0 + (ty - y0) * f
            self.z = z0 * (1 - f) + 7.0 * math.sin(math.pi * f)
            self.flight = (x0, y0, z0, tx, ty, t, hide)
            self.anim.update(dt)
            if f >= 1.0:
                self.z = 0.0
                self.flight = None
                if hide or self.leaving:
                    self.state, self.timer = ("roost", 0.0) if self.leaving else ("hidden", rng.uniform(40, 150))
                else:
                    self.state, self.timer = "sit", rng.uniform(4, 14)
                    self.anim.play("idle", self.lib["idle"], fps=1.2)
            return
        if self.state == "roost":
            self.alive = False
            return
        if self.state == "hidden":
            self.timer -= dt
            if self.timer <= 0 and self.distance_to(cat) > 70 and not self.leaving:
                spot = self._near_cover(4, 12, start=self.cover)
                if spot is not None:
                    self.x, self.y = self.cover
                    self.state, self.timer = "hop", 0.0
                    self.hop = (self.x, self.y, spot[0], spot[1])
                else:
                    self.timer = 10.0
            return
        d = self.distance_to(cat)
        if cat.posture != "sleep" and (d < 24 or (d < 40 and getattr(cat, "speed", 0.0) > 30)):
            self._escape()
            return
        if self.state == "hop":
            x0, y0, x1, y1 = self.hop
            self.timer += dt / 0.35
            f = min(1.0, self.timer)
            self.x, self.y = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            self.z = 2.5 * math.sin(math.pi * f)
            self.facing = 1 if x1 > x0 else -1
            self.anim.play("walk", self.lib["walk"], fps=0.0)
            self.anim.phase = f * (len(self.lib["walk"]) - 0.01)
            if f >= 1.0:
                self.z = 0.0
                self.state, self.timer = "sit", rng.uniform(4, 16)
                self.anim.play("idle", self.lib["idle"], fps=1.2)
            return
        self.timer -= dt
        if self.state == "beg":
            self.anim.play("beg", self.lib["beg"], fps=10)
            if self.timer <= 0:
                self.state, self.timer = "sit", rng.uniform(4, 12)
                self.anim.play("idle", self.lib["idle"], fps=1.2)
        elif self.timer <= 0:
            roll = rng.random()
            if roll < 0.55:
                spot = self._near_cover(3, 16)
                if spot is not None:
                    self.state, self.timer = "hop", 0.0
                    self.hop = (self.x, self.y, spot[0], spot[1])
                    return
            elif roll < 0.75:
                self.anim.play("preen", self.lib["preen"], fps=4, loop=False, restart=True)
            elif roll < 0.9:
                self.anim.play("peck", self.lib["peck"], fps=8, loop=False, restart=True)
            self.timer = rng.uniform(3, 12)
        elif self.anim.done:
            self.anim.play("idle", self.lib["idle"], fps=1.2)
        self.anim.update(dt)

    def sprite(self):
        if self.hidden:
            return None
        return self.anim.frame, bird_art.ANCHORS["fledgling"], self.facing < 0

    def shadow(self):
        if self.hidden:
            return None
        k = 1.0 / (1.0 + self.z * 0.02)
        return 3.2 * k, 1.0 * k, int(70 * k)


class Froglet(Entity):
    """One of the tiny frogs leaving the pond in early summer: out of the
    water at the bank, then away into the grass in little hops, a pause
    between each, until it's lost among the stems."""

    kind = "froglet"

    def __init__(self, world, rng):
        self.rng = rng
        self.frames = art()["froglet"]
        x, y, toward_water = rng.choice(bank_points(world.terrain))
        super().__init__(world, x + toward_water * 3.0, y)
        self.away = -toward_water
        self.facing = self.away
        self.hops = rng.randint(4, 11)
        self.state = "hop"
        self.hop = (self.x, self.y, x - toward_water * 3.0, y, 0.0)
        self.timer = 0.0
        self.anim.play("hop", self.frames["hop"], fps=0.0)

    @property
    def hidden(self):
        return False

    def interest(self, cat):
        if self.z > 1.0:
            return 0.0
        d = self.distance_to(cat)
        return 0.0 if d > 110 else 0.45 * (1.0 - d / 110.0) + 0.12

    def on_pounce(self, cat):
        self.hops = min(self.hops, 1)
        self._next_hop(away_from=cat, far=True)

    startle = on_pounce

    def notices_crouch(self, cat):
        if self.distance_to(cat) < 26 and self.state == "sit":
            self._next_hop(away_from=cat, far=True)

    def leave(self):
        self.hops = min(self.hops, 1)

    def _next_hop(self, away_from=None, far=False):
        t = self.world.terrain
        rng = self.rng
        if away_from is not None:
            base = math.atan2(self.y - away_from.y, self.x - away_from.x)
        else:
            base = 0.0 if self.away > 0 else math.pi
        for _ in range(10):
            a = base + rng.uniform(-1.0, 1.0)
            r = rng.uniform(7, 12) if far else rng.uniform(3.5, 7)
            x, y = self.x + math.cos(a) * r, self.y + math.sin(a) * r * 0.6
            if t.free_ground(x, y) and not t.is_water(x, y) and 4 < x < self.world.width - 4 \
                    and 8 < y < self.world.height - 2:
                self.state = "hop"
                self.hop = (self.x, self.y, x, y, 0.0)
                self.facing = 1 if x > self.x else -1
                return
        self.timer = rng.uniform(0.5, 1.5)

    def update(self, dt):
        if self.state == "hop":
            x0, y0, x1, y1, t = self.hop
            t += dt / 0.32
            f = min(1.0, t)
            self.hop = (x0, y0, x1, y1, t)
            self.x, self.y = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            self.z = 3.0 * math.sin(math.pi * f)
            self.anim.play("hop", self.frames["hop"], fps=0.0)
            self.anim.phase = 0.0 if f < 0.15 else 1.0 if f < 0.55 else 2.0 if f < 0.9 else 3.0
            if f >= 1.0:
                self.z = 0.0
                self.hops -= 1
                if self.hops <= 0:
                    self.alive = False          # lost among the grass stems
                    return
                self.state = "sit"
                self.timer = self.rng.uniform(0.8, 5.0)
                self.anim.play("sit", self.frames["sit"], fps=1.5)
            return
        cat = self.world.cat
        if self.distance_to(cat) < 22 and cat.posture != "sleep":
            self._next_hop(away_from=cat, far=True)
            return
        self.timer -= dt
        if self.timer <= 0:
            self._next_hop()
        self.anim.update(dt)

    def sprite(self):
        return self.anim.frame or self.frames["sit"][0], story_art.FROGLET_ANCHOR, self.facing < 0

    def shadow(self):
        return 2.0, 0.6, 50

    @property
    def airborne(self):
        return self.z > 3.0
