"""The meadow and everything in it."""

import collections
import itertools
import math
import random

from . import art
from .config import MEAL_TIMES
from .chance import Hawkes, count, peaks, sample
from .settings import SETTINGS
from .environment import Clock, Environment
from .events import CAPTION_TIME, Caption, Events, GlassTap
from .entities.cat import Cat
from .entities.wildlife import (Bee, BirdFlock, Butterfly, Dragonfly, Firefly, Frog, Hedgehog, Ladybug, Mouse,
                                Pigeon, Snail, Sparrow, bank_points)
from .particles import Particles
from .seasons import Scenery
from .shade import TreeShade
from .marks import Marks
from .places import Places
from .sky import mean_temperature
from .stories import Stories
from .util import clamp
from .terrain import generate_terrain
from .water import WaterFX

# ...and if it sits empty this long (real seconds), it gets topped up anyway.
MEALS = SETTINGS["meals"]
WILD = SETTINGS["wildlife"]
HOURS = WILD["hours"]


class World:
    def __init__(self, width, height, seed=None, clock=None, weather="clear", weather_locked=False, journal=None,
                 personality=None):
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.rng = random.Random(self.seed + 1)
        self.serials = itertools.count()    # every creature's own number (Entity.serial)
        self.width = width
        self.height = height
        self.time = 0.0
        self.dt_hint = 1 / 60
        self.terrain = generate_terrain(width, height, self.seed)
        self.env = Environment(self.rng, width, height, clock or Clock(), weather, weather_locked, seed=self.seed)
        self.day = self.env.day
        self.shade = TreeShade(self)
        self.marks = Marks(self, journal)
        self.places = Places(self, journal)
        self.shade.update(10.0)
        self.particles = Particles(self)
        self.water = WaterFX(self)
        self.entities = []
        self.overhead = []
        self.effects = []
        self.captions = []
        self.later = []           # [at world.time, text, tier]: captions still to come
        self.storm = None         # a thunderstorm going on now (events.Thunderstorm)
        self.stats = collections.Counter()   # what Mochi got up to this session
        self.bowl_fill = 1.0
        self._bowl_level = None
        self._bowl_sprites = [art.bowl(level, random.Random(self.seed + i)) for i, level in
                              enumerate((0.0, 0.34, 0.67, 1.0))]
        self._empty_for = 0.0
        self._patience = 0.0
        self._meals_for = None
        self._meals = []
        self._last_hour = self.env.hour
        self.scenery = Scenery(self.terrain)
        self.scenery_version = 0
        self._scenery_check = 0.0
        self._update_scenery(0.0)
        self.personality = personality
        self.cat = Cat(self, *self.terrain.spawn)
        self.entities.append(self.cat)
        self.director = Director(self)
        self.events = Events(self, journal)
        self.stories = Stories(self)
        self.director.populate()
        self._sync_bowl()
        if personality is not None and personality.first_meeting:
            personality.first_meeting = False
            self.say(f"Meet {personality.name}: {personality.describe()}", "uncommon")

    # --- simulation -----------------------------------------------------

    def update(self, dt, real=None):
        """``real``: the real seconds this step stands for, when the meadow
        is being fast-forwarded (testing mode), so captions still last
        long enough to read."""
        self.time += dt
        self.dt_hint = dt
        self.env.update(dt)
        self.shade.update(dt)
        self._update_bowl(dt)
        self._update_scenery(dt)
        self._update_canopy(dt)
        self.director.update(dt)
        self.events.update(dt)
        self.stories.update(dt)
        for e in list(self.entities):
            e.update(dt)
        self.entities = [e for e in self.entities if e.alive]
        self.marks.update(dt)
        for flock in self.overhead:
            flock.update(dt)
        self.overhead = [f for f in self.overhead if f.alive]
        self.particles.update(dt)
        self.water.update(dt)
        for fx in list(self.effects):
            fx.update(dt)
        self.effects = [fx for fx in self.effects if fx.alive]
        for item in list(self.later):
            if self.time >= item[0]:
                self.later.remove(item)
                self.say(item[1], item[2])
        for c in self.captions:
            c.age += dt if real is None else real
        self.captions = [c for c in self.captions if c.age < CAPTION_TIME]

    def say(self, text, tier):
        """A caption for something worth noticing."""
        self.captions.append(Caption(text, tier))

    def say_later(self, delay, text, tier):
        self.later.append([self.time + delay, text, tier])

    def summary(self):
        """This session in brief, for next time's recap."""
        return {
            "ended": self.env.clock.moment.isoformat(timespec="minutes"),
            "events": [[m.strftime("%H:%M"), name, tier] for m, name, tier in self.events.log[-20:]],
            "naps": self.stats["nap"],
            "pounces": self.stats["pounce"],
        }

    def glass_tap(self, x, y):
        self.effects.append(GlassTap(x, y))

    def meal_times(self):
        """Today's mealtimes: the usual hours, a little early or late, and
        differently so each day (the same however often the meadow
        restarts that day)."""
        date = self.env.clock.date
        if self._meals_for != date:
            rng = random.Random(date.toordinal() * 31 + self.seed)
            self._meals = [meal + sample(rng, MEALS["lateness"]) for meal in MEAL_TIMES]
            self._meals_for = date
        return self._meals

    def _refill(self):
        self.bowl_fill = sample(self.rng, MEALS["refill"])

    def _update_bowl(self, dt):
        hour = self.env.hour
        for meal in self.meal_times():
            crossed = self._last_hour < meal <= hour or (hour < self._last_hour and (meal > self._last_hour or meal <= hour))
            if crossed:
                self._refill()
        self._last_hour = hour
        if self.bowl_fill <= 0.02:
            if self._empty_for == 0.0:
                self._patience = sample(self.rng, MEALS["empty_bowl_patience"], self.day.spread)
            self._empty_for += dt
            if self._empty_for > self._patience:
                self._refill()
        else:
            self._empty_for = 0.0
        self._sync_bowl()

    def _update_canopy(self, dt):
        """Fade the tree's crown when Mochi is under it, so she stays in sight."""
        tree = self.terrain.tree
        if tree is None:
            return
        cat = self.cat
        c = tree.canopy
        w, h = c.frames[0].get_size()
        beneath = abs(cat.x - c.x) < w / 2 and c.y - h / 2 < cat.y - 12 < c.y + h / 2 + 4
        target = 0.38 if beneath else 1.0
        c.fade += (target - c.fade) * min(1.0, dt * 4.0)

    def _update_scenery(self, dt):
        """Regrade the ground when the week, the snow or the frost changes."""
        self._scenery_check -= dt
        if self._scenery_check > 0:
            return
        self._scenery_check = 2.0
        if self.scenery.apply(Scenery.key_for(self.env)):
            self.scenery_version += 1

    def _sync_bowl(self):
        prop = self.terrain.bowl_prop
        if prop is None:
            return
        level = 0 if self.bowl_fill <= 0.02 else 1 if self.bowl_fill < 0.4 else 2 if self.bowl_fill < 0.75 else 3
        if level != self._bowl_level:
            self._bowl_level = level
            prop.frames = [self._bowl_sprites[level]]

    # --- queries ----------------------------------------------------------

    def calm(self):
        """Nothing on screen is moving fast: a lower frame rate will do."""
        cat = self.cat
        if cat.speed > 1.0 or cat.moved > 0.0 or cat.z > 0:
            return False
        if self.effects or self.captions or self.env.rain > 0.05:
            return False
        if any(getattr(f, "fast", False) for f in self.overhead):
            return False         # geese and storks crossing: their shadows would judder
        for e in self.entities:
            if e is cat or e.kind == "bee":     # a bee is a two-pixel speck: no need
                continue
            speed = getattr(e, "speed", None)
            if speed is None and hasattr(e, "vx"):
                speed = math.hypot(e.vx, e.vy) + abs(getattr(e, "vz", 0.0))
            if (speed or 0.0) > 25.0:      # butterflies and bees drift; birds and bats dart
                return False
        return True

    def count(self, kind):
        return sum(1 for e in self.entities if e.kind == kind and not getattr(e, "leaving", False))

    def of_kind(self, kind):
        return [e for e in self.entities if e.kind == kind]

    def flush_bush(self, bush, cat):
        """The cat pawed at a bush: anything hiding in it may bolt."""
        if self.rng.random() < 0.35 and self.count("mouse") < 3:
            mouse = Mouse(self, bush)
            mouse.flee_from = cat
            mouse.state = "dash"
            far = [b for b in self.terrain.bushes if b is not bush]
            if far:
                mouse.home = min(far, key=lambda b: (b.x - bush.x) ** 2 + (b.y - bush.y) ** 2)
            mouse.flee(cat)
            self.entities.append(mouse)


class Director:
    """Keeps the meadow populated according to the hour and the weather."""

    def __init__(self, world):
        self.world = world
        self.timer = 0.0
        rng = world.rng
        # Bird visits cluster: one flock makes another likelier for a while.
        self.pigeons = Hawkes(rng, **WILD["pigeons"])
        self.sparrows = Hawkes(rng, **WILD["sparrows"])
        self.flyovers = Hawkes(rng, **WILD["overhead"])
        self.wet = 0.0            # how recently it rained: snails come out
        self.hog_night = rng.random() < WILD["hedgehog_night_chance"]
        self._rolled = False
        self.spawn_wait = {}
        self.day_mouse = False
        self.day_mouse_timer = sample(rng, WILD["day_mouse_first"])

    def targets(self):
        env = self.world.env
        clock = env.clock
        area = self.world.width * self.world.height / (480 * 320)
        sun, rain = env.sun, env.rain
        cloud, wind = env.weather.cloud, env.wind.strength
        warm = self.warmth
        calm = 1.0 - max(0.0, wind - 0.5) * 1.6
        dry = rain < 0.08
        summer = env.season == "summer" or (env.season == "spring" and env.sky.year_phase > 0.36)
        t = {}
        # Insects need warmth: few in spring and autumn, none in winter.
        insects = clamp((warm - 10.0) / 8.0, 0.0, 1.0)
        hour = clock.standard_hour
        busy = self.world.day.busyness
        t["butterfly"] = round(4 * area * (1 - 0.55 * cloud) * calm * insects * busy) if (sun > 0.55 and dry) else 0
        glow = peaks(hour, HOURS["fireflies"])
        firefly_ok = summer and warm > 16 and sun < 0.05 and dry and glow > 0.1
        t["firefly"] = round(22 * area * (1 - 0.4 * cloud) * glow) if firefly_ok else 0
        if rain > 0.4 or env.snowing:
            t["mouse"] = 0
        else:
            night_mice = round((2 if area > 1.2 else 1) * peaks(hour, HOURS["mice"]))
            t["mouse"] = night_mice or (1 if self.day_mouse else 0)
        t["ladybug"] = round(2 * area * insects) if (sun > 0.6 and dry) else 0
        pond = self.world.terrain.pond is not None
        t["dragonfly"] = (2 if area > 1.2 else 1) if (pond and sun > 0.6 and dry and wind < 0.65 and warm > 17) else 0
        t["bee"] = round(4 * area * calm * insects * busy) if (sun > 0.6 and dry and cloud < 0.6) else 0
        if pond:
            evening = peaks(hour, HOURS["frogs_evening"]) > 0.5 or rain > 0.15
            awake = warm > 8 and not env.snowing   # frogs sleep through the cold months in the mud
            t["frog"] = (2 if evening else 1) if awake and (sun > 0.02 or evening) else 0
        t["snail"] = round(3 * area * self.wet) if (self.wet > 0.3 and rain < 0.3 and warm > 6) else 0
        hog_awake = warm > 7          # hedgehogs hibernate through the winter
        out_and_about = peaks(hour, HOURS["hedgehog"]) > 0.35
        t["hedgehog"] = 1 if (self.hog_night and hog_awake and out_and_about and rain < 0.4) else 0
        return t

    @property
    def warmth(self):
        """The day's warmth for the season (daily mean, Celsius): what
        decides whether insects fly and hedgehogs are awake, rather than one
        cold hour."""
        env = self.world.env
        return mean_temperature(env.clock.date, env.sky.lat)

    def update(self, dt):
        world = self.world
        env = world.env
        rng = world.rng
        if env.rain > 0.25 and not env.snowing:
            self.wet = min(1.0, self.wet + dt / 60.0)
        else:
            self.wet = max(0.0, self.wet - dt / 900.0)
        # Each midday decides whether a hedgehog will come by that night.
        if env.clock.between(12.0, 13.0):
            if not self._rolled:
                self.hog_night = rng.random() < WILD["hedgehog_night_chance"]
                self._rolled = True
        else:
            self._rolled = False
        self.day_mouse_timer -= dt
        if self.day_mouse_timer <= 0:
            self.day_mouse_timer = sample(rng, WILD["day_mouse_check"])
            self.day_mouse = rng.random() < WILD["day_mouse_chance"]
        self.timer -= dt
        if self.timer <= 0:
            self.timer = 1.0
            for kind, target in self.targets().items():
                have = world.count(kind)
                wait = self.spawn_wait.get(kind, 0.0) - 1.0
                self.spawn_wait[kind] = wait
                if have < target and wait <= 0:
                    self._spawn(kind)
                    wait = WILD["mouse_wait"] if kind == "mouse" else WILD["spawn_wait"]
                    self.spawn_wait[kind] = sample(rng, wait)
                elif have > target:
                    for e in world.of_kind(kind):
                        if not getattr(e, "leaving", False):
                            leave = getattr(e, "leave", None)
                            if leave:
                                leave()
                            break

        if world.events.hushed:
            return   # something is about to happen: the birds stay away
        busy = world.day.busyness
        # Pigeons visit in small flocks during the day.
        if self.pigeons.step(dt, busy if (env.sun > 0.4 and env.rain < 0.2) else 0.0):
            if world.count("pigeon") == 0:
                self._spawn_flock(Pigeon, count(rng, WILD["pigeon_flock"]))
        # Sparrows drop in, peck about and whirr off again.
        if self.sparrows.step(dt, busy if (env.sun > 0.35 and env.rain < 0.2) else 0.0):
            if world.count("sparrow") == 0:
                self._spawn_flock(Sparrow, count(rng, WILD["sparrow_flock"]), spread=(24, 12), gap=(10, 6))
        # Birds pass high overhead; only their shadows reach the meadow.
        if self.flyovers.step(dt, busy if (env.sun > 0.5 and env.rain < 0.3) else 0.0):
            world.overhead.append(BirdFlock(world))

    def populate(self):
        """Start with the meadow already alive instead of waiting for
        visitors to wander in."""
        world = self.world
        rng = world.rng
        for kind, target in self.targets().items():
            for _ in range(target):
                if kind in ("mouse", "hedgehog"):
                    continue  # these prefer to make an entrance
                before = len(world.entities)
                self._spawn(kind)
                if len(world.entities) > before:
                    e = world.entities[-1]
                    if kind in ("butterfly", "dragonfly"):
                        e.x = rng.uniform(30, world.width - 30)
                        e.y = rng.uniform(40, world.height - 20)
                        if kind == "dragonfly" and world.terrain.pond is not None:
                            e.x, e.y = e._spot()
                    if kind == "firefly":
                        e.fade = 1.0

    def _spawn(self, kind):
        world = self.world
        rng = world.rng
        if kind == "butterfly":
            world.entities.append(Butterfly(world))
        elif kind == "firefly":
            ff = Firefly(world)
            world.entities.append(ff)
        elif kind == "mouse" and world.terrain.bushes:
            world.entities.append(Mouse(world, rng.choice(world.terrain.bushes)))
        elif kind == "ladybug":
            world.entities.append(Ladybug(world))
        elif kind == "dragonfly" and world.terrain.pond is not None:
            world.entities.append(Dragonfly(world))
        elif kind == "frog" and world.terrain.pond is not None and bank_points(world.terrain):
            world.entities.append(Frog(world))
        elif kind == "bee" and world.terrain.perches:
            world.entities.append(Bee(world))
        elif kind == "snail":
            world.entities.append(Snail(world))
        elif kind == "hedgehog":
            world.entities.append(Hedgehog(world))

    def _spawn_flock(self, cls, count, spread=(30, 14), gap=(18, 9)):
        world = self.world
        rng = world.rng
        t = world.terrain
        for _ in range(20):
            x = rng.uniform(40, world.width - 40)
            y = rng.uniform(50, world.height - 20)
            if t.free_ground(x, y) and world.cat.distance_to(_Point(x, y)) > 90:
                break
        else:
            return
        flock = []
        spots = []
        for i in range(count):
            for _ in range(12):
                lx = x + rng.uniform(-spread[0], spread[0])
                ly = y + rng.uniform(-spread[1], spread[1])
                if t.free_ground(lx, ly) and all(abs(lx - sx) > gap[0] or abs(ly - sy) > gap[1] for sx, sy in spots):
                    break
            else:
                continue  # no room for this one
            spots.append((lx, ly))
            flock.append(cls(world, lx, ly, delay=i * rng.uniform(0.2, 1.0)))
        for p in flock:
            p.flock = flock
            world.entities.append(p)


class _Point:
    def __init__(self, x, y):
        self.x, self.y = x, y
