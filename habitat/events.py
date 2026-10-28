"""Encounters: the things that make a long watch worth it.

Events come in four tiers of rarity.  Roughly, while you watch:

    common      a few an hour      the meadow being playful (no caption)
    uncommon    a few a day        mist, a rainbow, bats at dusk
    rare        about one a day    a shooting star, Mochi noticing you
    legendary   about one a week   a golden butterfly, a meteor shower

Every event has conditions (time of day, weather, season, the real date,
the moon) and a cooldown.  At most one rare-or-better event runs at once.
The longer a tier goes without an event, the likelier one becomes, so a
long watch is always rewarded.  Legendary events are foreshadowed: the
birds go quiet and leave a little before.

Some events aren't rolled for but noticed when the world makes them true:
a full moon on a clear night, the first snow of winter, a meteor shower on
its real peak night, New Year's midnight.

Uncommon and rarer events show a short caption and are written to the
journal.
"""

import datetime
import math

import numpy as np
import pygame

from .entities.cat import Mark
from .entities.wildlife import (Bat, Bird, BirdFlock, Butterfly, Crow, Deer, Duck, Fox, GoldenButterfly, Grasshopper,
                                Heron, Moth, PeekingMouse, Pumpkin, Sparrow, art, halloween)
from .chance import Hawkes, count, lognormal, peaks, sample
from .settings import SETTINGS
from .util import clamp, value_noise

TIERS = ("common", "uncommon", "rare", "legendary")
# Mean real seconds between events of each tier while you watch.
_EVENTS = SETTINGS["events"]
FX = SETTINGS["effects"]
MEAN = {tier: 60.0 * minutes for tier, minutes in _EVENTS["tiers"].items()}
CHECK = float(_EVENTS["check"])
CAPTION_TIME = float(_EVENTS["caption_seconds"])
OVERDUE_BOOST = float(_EVENTS["overdue_boost"])
HOURS = _EVENTS.get("hours", {})
COUNTS = FX["counts"]
STAYS = FX["stays"]
BIG = ("rare", "legendary")

# Real meteor showers: (month, peak day, name).  Active the night of the
# peak and the nights either side.
SHOWERS = [(1, 3, "Quadrantids"), (4, 22, "Lyrids"), (5, 6, "Eta Aquariids"), (8, 12, "Perseids"),
           (10, 21, "Orionids"), (11, 17, "Leonids"), (12, 14, "Geminids")]


def shower_tonight(moment):
    """The meteor shower whose peak is tonight (within a night), or None."""
    night_of = (moment - datetime.timedelta(hours=12)).date()   # the small hours belong to last night
    for month, day, name in SHOWERS:
        try:
            peak = datetime.date(night_of.year, month, day)
        except ValueError:
            continue
        if abs((night_of - peak).days) <= 1:
            return name
    return None


def night_key(moment):
    return (moment - datetime.timedelta(hours=12)).date().isoformat()


# ==========================================================================
# Effects: things drawn for a while that aren't creatures

class Effect:
    alive = True

    def update(self, dt):
        pass

    def draw_ground(self, r):
        """On the ground, under everything that stands on it."""

    def draw(self, r):
        """Under the lighting (lit like the meadow)."""

    def draw_glow(self, r):
        """After the lighting (light of its own)."""


class ShootingStar(Effect):
    """A streak across the pond's mirror of the night sky."""

    DURATION = float(FX["shooting_star"])

    def __init__(self, world):
        self.world = world
        rng = world.rng
        pond = world.terrain.pond
        angle = rng.uniform(math.radians(20), math.radians(70)) * rng.choice((1, -1))
        self.dx, self.dy = math.cos(angle) * rng.choice((1, -1)), abs(math.sin(angle))
        length = rng.uniform(18, 34)
        self.x0 = pond.cx - self.dx * length / 2 + rng.uniform(-pond.rx * 0.3, pond.rx * 0.3)
        self.y0 = pond.cy - self.dy * length / 2 + rng.uniform(-pond.ry * 0.3, pond.ry * 0.3)
        self.length = length
        self.age = 0.0

    def update(self, dt):
        self.age += dt
        if self.age > self.DURATION + 0.4:
            self.alive = False

    def draw_glow(self, r):
        terrain = self.world.terrain
        f = min(1.0, self.age / self.DURATION)
        fade = 1.0 if self.age < self.DURATION else max(0.0, 1.0 - (self.age - self.DURATION) / 0.4)
        hx = self.x0 + self.dx * self.length * f
        hy = self.y0 + self.dy * self.length * f
        for i in range(12):
            x, y = hx - self.dx * i * 0.9, hy - self.dy * i * 0.9
            if not terrain.is_water(x, y):
                continue
            a = int(255 * (1.0 - i / 12) * fade)
            if a > 12:
                r.blit_px(r.dot((210, 220, 255), a, 1, 1), x, y, add=True)


class MeteorShower(Effect):
    """Shooting stars every little while, all night, while the sky is
    clear."""

    def __init__(self, world):
        self.world = world
        m = FX["meteors"]
        self.stars = Hawkes(world.rng, m["mean_wait"], m["excite"], m["memory"])   # they come in little bursts

    def update(self, dt):
        env = self.world.env
        if env.sun > 0.05 or not shower_tonight(env.clock.moment):
            self.alive = False
            return
        if self.stars.step(dt):
            if env.weather.cloud < 0.5:
                self.world.effects.append(ShootingStar(self.world))


class Mist(Effect):
    """Dawn mist lying over the grass, drifting, lifting as the sun climbs."""


    def __init__(self, world):
        self.world = world
        self.age = 0.0
        self.density = 0.0
        self.lifting = None
        spread = world.day.spread
        self.rise = sample(world.rng, FX["mist_rise"], spread)
        self.lift = sample(world.rng, FX["mist_lift"], spread)
        self.max_age = sample(world.rng, FX["mist_lasts_minutes"], spread) * 60
        self._surface = None
        self._for = None

    def update(self, dt):
        self.age += dt
        env = self.world.env
        if self.lifting is None and (env.sun > 0.8 or env.wind.strength > 0.6 or self.age > self.max_age):
            self.lifting = self.density
        if self.lifting is not None:
            self.density = max(0.0, self.density - self.lifting * dt / self.lift)
            if self.density <= 0:
                self.alive = False
        else:
            self.density = min(1.0, self.age / self.rise)

    def _fog(self, r):
        key = (r.S, self.world.width, self.world.height)
        if self._for != key:
            w, h = self.world.width + 64, self.world.height
            nrng = np.random.default_rng(self.world.seed + 7)
            # A thin veil everywhere, thicker in long soft banks.
            n = value_noise(w, h, 90, nrng) * 0.7 + value_noise(w, h, 30, nrng) * 0.3
            bayer = np.tile(np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0,
                            (h // 4 + 1, w // 4 + 1))[:h, :w]
            level = np.floor(np.clip(n * 1.3 - 0.15, 0, 1) * 6 + bayer * 0.999) / 6
            alpha = (34 + level * 64).astype(np.uint8)
            small = pygame.Surface((w, h), pygame.SRCALPHA, 32)
            pygame.surfarray.pixels3d(small)[...] = (236, 240, 244)
            pygame.surfarray.pixels_alpha(small)[...] = alpha.T
            self._surface = pygame.transform.scale(small, (w * r.S, h * r.S))
            self._for = key
        return self._surface

    def draw(self, r):
        if self.density <= 0.01:
            return
        fog = self._fog(r)
        fog.set_alpha(int(255 * self.density))
        shift = (self.world.time * 1.2) % 64
        r.screen.blit(fog, (-round(shift) * r.S, 0))


class Rainbow(Effect):
    """After a shower, with the sun low enough, a rainbow stands opposite
    it: we see it mirrored in the pond."""

    BANDS = [(120, 34, 34), (124, 74, 24), (110, 104, 26), (34, 96, 40), (30, 56, 120), (64, 32, 96)]
    FADE = float(FX["rainbow_fade"])

    def __init__(self, world):
        self.world = world
        self.age = 0.0
        self.duration = sample(world.rng, FX["rainbow_lasts_minutes"], world.day.spread) * 60
        self._levels = {}
        self._for = None

    def update(self, dt):
        self.age += dt
        if self.age > self.duration or self.world.env.rain > 0.3:
            self.alive = False

    def strength(self):
        a, d = self.age, self.duration
        return clamp(min(a / self.FADE, (d - a) / self.FADE), 0.0, 1.0)

    def _image(self, r, level):
        if self._for != r.S:
            self._levels = {}
            self._for = r.S
        hit = self._levels.get(level)
        if hit is None:
            t = self.world.terrain
            pond = t.pond
            w, h = t.width, t.height
            img = pygame.Surface((w, h))
            img.fill((0, 0, 0))
            cx, cy = pond.cx, pond.cy + pond.ry * 1.6
            radius = pond.rx * 1.25
            k = level / 6
            for i, col in enumerate(self.BANDS):
                rad = radius - i
                c = tuple(int(v * k) for v in col)
                for step in range(int(rad * 4)):
                    a = math.pi + math.pi * step / (rad * 4)
                    x, y = cx + math.cos(a) * rad, cy + math.sin(a) * rad * 0.62
                    if t.is_water(x, y):
                        img.set_at((int(x), int(y)), c)
            hit = pygame.transform.scale(img, (w * r.S, h * r.S))
            self._levels[level] = hit
        return hit

    def draw_glow(self, r):
        level = int(round(self.strength() * 6))
        if level > 0:
            r.screen.blit(self._image(r, level), (0, 0), special_flags=pygame.BLEND_ADD)


class Whirl(Effect):
    """A gust spins up a little whirlwind of leaves that wanders across the
    meadow."""

    def __init__(self, world):
        self.world = world
        rng = world.rng
        self.dir = world.env.wind.direction
        self.x = -10.0 if self.dir > 0 else world.width + 10.0
        self.y = rng.uniform(world.height * 0.3, world.height * 0.85)
        self.speed = rng.uniform(20, 30)
        autumn = world.env.season == "autumn"
        from .particles import AUTUMN_LEAF_COLORS, LEAF_COLORS
        colors = AUTUMN_LEAF_COLORS if autumn else LEAF_COLORS
        self.leaves = [[rng.uniform(0, 6.28), rng.uniform(3, 10), rng.uniform(2, 22), rng.uniform(4, 8),
                        rng.choice(colors)] for _ in range(count(rng, COUNTS["whirl_leaves"]))]
        self.t = 0.0
        self.seen = False

    def update(self, dt):
        world = self.world
        self.t += dt
        self.x += self.dir * self.speed * dt
        self.y += math.sin(self.t * 0.7) * 8 * dt
        for leaf in self.leaves:
            leaf[0] += leaf[3] * dt
            leaf[2] = clamp(leaf[2] + math.sin(self.t * 2 + leaf[0]) * 10 * dt, 1, 26)
        if world.rng.random() < dt * 6:
            world.particles.dust(self.x, self.y, count=1, spread=5)
        cat = world.cat
        if not self.seen and abs(cat.x - self.x) < 60 and abs(cat.y - self.y) < 30:
            self.seen = cat.attend("whirl", cat.act_gaze(self.x + self.dir * 30, self.y, 2.5, "watching the leaves spin"))
        if self.x < -30 or self.x > world.width + 30:
            # The last leaves drop where the wind lets them go.
            for leaf in self.leaves[:4]:
                world.particles.leaf(clamp(self.x, 0, world.width), self.y, 10)
            self.alive = False

    def draw(self, r):
        for a, rad, z, _, color in self.leaves:
            x = self.x + math.cos(a) * rad
            y = self.y + math.sin(a) * rad * 0.45
            r.blit_px(r.dot((20, 24, 30), 50, 1, 1), x + 1, y)
            r.blit_px(r.dot(color, 255, 2 if int(a * 2) % 2 else 1, 1), x, y - z)


class Thunderstorm(Effect):
    """Lightning in a warm downpour: silent flashes, now and then a double
    flicker, lighting the whole meadow for a split second.  They come in
    little bursts (a Hawkes process) until the rain eases.  Mochi keeps her
    ears flat while it lasts, and a flash sends her for cover if she's out
    in it."""

    FLASH = 0.5            # seconds a flash takes to come and go

    def __init__(self, world):
        self.world = world
        storm = FX["thunderstorm"]
        self.strikes = Hawkes(world.rng, storm["mean_wait"], storm["excite"], storm["memory"])
        self.flash = None          # seconds into the flash now showing
        self.double = False
        self.age = 0.0
        self.duration = sample(world.rng, FX["thunderstorm_minutes"]) * 60.0
        self.timer = world.rng.uniform(2.0, 6.0)     # the first one comes soon
        world.storm = self

    def update(self, dt):
        world = self.world
        self.age += dt
        if self.flash is not None:
            self.flash += dt
            if self.flash > self.FLASH:
                self.flash = None
        over = world.env.rain < 0.45 or self.age > self.duration
        if over and self.flash is None:
            self.alive = False
            world.storm = None
            return
        self.timer -= dt
        if not over and self.flash is None and (self.timer <= 0 or self.strikes.step(dt)):
            self.timer = 1e9
            self.strike()

    def strike(self):
        world = self.world
        self.flash = 0.0
        self.double = world.rng.random() < 0.4
        cat = world.cat
        cat.p.feel(-0.04)
        if cat.posture != "sleep" and not cat.sheltered and cat.interruptible:
            cat.attend("shelter", cat.act_shelter())

    def brightness(self):
        """How much the flash lights the meadow now, 0..1."""
        t = self.flash
        if t is None:
            return 0.0
        k = max(0.0, 1.0 - t / 0.12)
        if self.double and 0.2 < t < 0.32:
            k = max(k, 0.7 * (1.0 - (t - 0.2) / 0.12))
        return max(k, 0.25 * max(0.0, 1.0 - t / self.FLASH))     # and a faint afterglow

    def draw_glow(self, r):
        k = self.brightness() * FX["lightning_brightness"]
        if k > 0.02:
            r.screen.fill((int(96 * k), int(100 * k), int(124 * k)), special_flags=pygame.BLEND_ADD)


class Fireworks(Effect):
    """New Year's midnight: distant fireworks, seen as flashes on the
    meadow and as bursts mirrored in the pond."""

    COLORS = [(255, 120, 120), (255, 214, 120), (140, 220, 255), (190, 140, 255), (150, 255, 160)]

    def __init__(self, world):
        self.world = world
        self.bursts = []          # [x, y, age, colour, speed]
        self.timer = 1.0
        self.age = 0.0
        self.duration = sample(world.rng, FX["fireworks_minutes"]) * 60

    def update(self, dt):
        rng = self.world.rng
        self.age += dt
        self.timer -= dt
        if self.timer <= 0 and self.age < self.duration:
            self.timer = rng.uniform(0.8, 3.5)
            pond = self.world.terrain.pond
            if pond is not None:
                x, y = pond.cx + rng.uniform(-pond.rx, pond.rx) * 0.6, pond.cy + rng.uniform(-pond.ry, pond.ry) * 0.5
            else:
                x, y = rng.uniform(0, self.world.width), rng.uniform(0, self.world.height)
            self.bursts.append([x, y, 0.0, rng.choice(self.COLORS), rng.uniform(10, 18)])
        for b in self.bursts:
            b[2] += dt
        self.bursts = [b for b in self.bursts if b[2] < 1.8]
        if self.age > self.duration and not self.bursts:
            self.alive = False

    def draw_glow(self, r):
        terrain = self.world.terrain
        for x, y, age, color, speed in self.bursts:
            if age < 0.25:
                k = 0.06 * (1.0 - age / 0.25)
                r.screen.fill(tuple(int(c * k) for c in color), special_flags=pygame.BLEND_ADD)
            rad = speed * (1.0 - math.exp(-age * 2.2))
            fade = max(0.0, 1.0 - age / 1.8)
            drop = age * age * 2.0
            for i in range(20):
                a = i * math.tau / 20
                px, py = x + math.cos(a) * rad, y + math.sin(a) * rad * 0.6 + drop
                if terrain.is_water(px, py):
                    r.blit_px(r.dot(color, int(255 * fade), 1, 1), px, py, add=True)


class GlassTap(Effect):
    """Where Mochi's paw meets the screen."""

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.age = 0.0

    def update(self, dt):
        self.age += dt
        if self.age > 0.6:
            self.alive = False

    def draw_glow(self, r):
        f = self.age / 0.6
        rad = 1 + int(f * 4)
        r.blit_px(r.ring(rad, int(200 * (1 - f))), self.x - rad, self.y - rad * 0.5)
        if self.age < 0.12:
            r.blit_px(r.dot((255, 255, 255), 200, 1, 1), self.x, self.y, add=True)


class Seeds(Effect):
    """A puff of dandelion seeds sails across on the breeze."""

    def __init__(self, world):
        self.world = world
        rng = world.rng
        self.left = count(rng, COUNTS["dandelion_seeds"])
        self.y = rng.uniform(40, world.height - 40)
        self.timer = 0.0

    def update(self, dt):
        world = self.world
        rng = world.rng
        self.timer -= dt
        if self.timer <= 0 and self.left > 0:
            self.timer = rng.uniform(0.2, 1.2)
            self.left -= 1
            direction = world.env.wind.direction
            x = -4 if direction > 0 else world.width + 4
            world.particles.seed(x, self.y + rng.uniform(-24, 24), rng.uniform(8, 26), direction)
        if self.left <= 0:
            self.alive = False


class Feather(Effect):
    """A feather comes down out of a clear sky; Mochi may go and see."""

    def __init__(self, world):
        self.world = world
        rng = world.rng
        t = world.terrain
        for _ in range(20):
            x, y = rng.uniform(40, world.width - 40), rng.uniform(50, world.height - 30)
            if t.walkable(x, y):
                break
        self.x, self.y, self.z = x, y, rng.uniform(60, 80)
        self.t = rng.random() * 6
        self.landed = 0.0

    def update(self, dt):
        world = self.world
        self.t += dt
        if self.z > 0:
            sway = math.sin(self.t * 1.6)
            self.z = max(0.0, self.z - (7.0 + sway * 3) * dt)
            self.x += (sway * 9.0 + world.env.wind.drift * 0.4) * dt
            if self.z == 0:
                cat = world.cat
                if cat.distance_to(self) < 170 and world.rng.random() < 0.7:
                    cat.attend("feather", cat.act_sniff_at(self.x, self.y, "sniffing a feather"))
        else:
            self.landed += dt
            if self.landed > 40:
                self.alive = False

    def draw(self, r):
        fade = 1.0 if self.landed < 36 else (40 - self.landed) / 4
        if self.z > 0:
            r.blit_px(r.dot((20, 24, 30), 50, 2, 1), self.x + 1, self.y)
        tilt = int(self.t * 2) % 2 if self.z > 0 else 0
        w, h = (3, 1) if tilt == 0 else (2, 1)
        r.blit_px(r.dot((214, 214, 220), int(255 * fade), w, h), self.x, self.y - self.z)
        r.blit_px(r.dot((150, 150, 164), int(255 * fade), 1, 1), self.x, self.y - self.z)


class TumbleLeaf(Effect):
    """One dry leaf skittering along the ground in fits and starts."""

    def __init__(self, world):
        self.world = world
        rng = world.rng
        cat = world.cat
        self.dir = world.env.wind.direction
        self.mark = Mark("leaf", -6.0 if self.dir > 0 else world.width + 6.0,
                         clamp(cat.y + rng.uniform(-12, 12), 30, world.height - 10))
        self.mark.on_pounce = self._flip
        self.speed = 0.0
        self.gust = 0.0
        self.t = 0.0
        from .particles import AUTUMN_LEAF_COLORS, LEAF_COLORS
        self.color = rng.choice(AUTUMN_LEAF_COLORS if world.env.season == "autumn" else LEAF_COLORS)
        self.called = False

    def _flip(self, cat):
        self.gust = 1.2          # a puff of wind, just in time

    def update(self, dt):
        world = self.world
        rng = world.rng
        self.t += dt
        if self.gust <= 0 and rng.random() < dt * 0.9:
            self.gust = rng.uniform(0.4, 1.1)
        if self.gust > 0:
            self.gust -= dt
            self.speed = min(46.0, self.speed + 140 * dt)
        else:
            self.speed = max(0.0, self.speed - 90 * dt)
        m = self.mark
        m.x += self.dir * self.speed * dt
        m.y += math.sin(self.t * 1.3) * 4 * dt
        cat = world.cat
        if not self.called and abs(m.x - cat.x) < 110:
            self.called = cat.attend("leaf", cat.act_chase(m))
        if m.x < -12 or m.x > world.width + 12:
            m.alive = False
            self.alive = False

    def draw(self, r):
        m = self.mark
        flip = int(self.t * 6) % 2 if self.speed > 5 else 0
        w, h = (2, 1) if flip == 0 else (1, 2)
        r.blit_px(r.dot(self.color, 255, w, h), m.x, m.y - (1 if self.speed > 20 else 0))


class Puddle:
    __slots__ = ("x", "y", "rx", "ry", "life", "age", "alive")

    def __init__(self, x, y, rx, ry, life):
        self.x, self.y, self.rx, self.ry, self.life = x, y, rx, ry, life
        self.age = 0.0
        self.alive = True


class Puddles(Effect):
    """After a downpour, puddles on the path: they mirror the sky and dry
    up in the sun."""

    PUDDLES = True      # muddy paws (marks.py)

    def __init__(self, world):
        self.world = world
        rng = world.rng
        t = world.terrain
        self.items = []
        for _ in range(rng.randint(2, 4)):
            for _ in range(30):
                x, y = rng.uniform(30, world.width - 30), rng.uniform(40, world.height - 20)
                rx, ry = rng.uniform(4, 9), rng.uniform(2, 3.5)
                clear = all(t.walkable(x + dx, y + dy) and not t.under_roof(x + dx, y + dy)
                            for dx, dy in ((-rx - 3, 0), (rx + 3, 0), (0, -ry - 2), (0, ry + 2)))
                if clear and all(abs(x - p.x) > 30 for p in self.items):
                    life = sample(rng, FX["puddles_last_minutes"], world.day.spread) * 60
                    self.items.append(Puddle(x, y, rx, ry, life))
                    break
        if not self.items:
            self.alive = False
        self._cache = {}

    def update(self, dt):
        env = self.world.env
        dry = 1.0 + 2.0 * env.sun * (1.0 - env.weather.cloud)
        for p in self.items:
            p.age += dt * dry
            if p.age >= p.life:
                p.alive = False
        self.items = [p for p in self.items if p.alive]
        if not self.items:
            self.alive = False

    def _image(self, r, rx, ry):
        key = (r.S, rx, ry)
        hit = self._cache.get(key)
        if hit is None:
            small = pygame.Surface((rx * 2 + 1, ry * 2 + 1), pygame.SRCALPHA)
            pygame.draw.ellipse(small, (58, 74, 84, 255), small.get_rect())
            inner = small.get_rect().inflate(-2, -2)
            if inner.width > 1 and inner.height > 0:
                pygame.draw.ellipse(small, (92, 120, 136, 255), inner)
            small.set_at((rx // 2 + 1, max(0, ry - 1)), (190, 214, 224, 255))      # a glint of sky
            hit = pygame.transform.scale(small, (small.get_width() * r.S, small.get_height() * r.S))
            self._cache[key] = hit
        return hit

    def draw_ground(self, r):
        for p in self.items:
            f = 1.0 - p.age / p.life
            rx, ry = max(1, round(p.rx * f ** 0.5)), max(1, round(p.ry * f ** 0.5))
            r.blit_px(self._image(r, rx, ry), p.x - rx, p.y - ry)


class ButterflyDance(Effect):
    """Two butterflies spiralling round each other, rising, then going
    their own ways."""

    def __init__(self, world):
        self.world = world
        rng = world.rng
        self.DURATION = sample(rng, FX["butterfly_dance"], world.day.spread)
        self.species = rng.choice(["white", "brimstone", "orange", "blue"])
        self.frames = art()["butterfly"][self.species]
        cat = world.cat
        for _ in range(20):
            self.cx = rng.uniform(50, world.width - 50)
            self.cy = rng.uniform(60, world.height - 30)
            if 50 < math.hypot(self.cx - cat.x, self.cy - cat.y) < 160:
                break
        self.age = 0.0
        self.spin = rng.choice((-1, 1)) * rng.uniform(5.0, 7.0)
        if _awake(cat):
            cat.attend("dance", cat.act_gaze(self.cx, self.cy, 6.0, "watching two butterflies dance"))

    def positions(self):
        f = self.age / self.DURATION
        z = 6 + 30 * f
        out = []
        for k in (0, 1):
            a = self.age * self.spin + k * math.pi
            rad = 3.0 + 2.0 * math.sin(self.age * 1.3)
            out.append((self.cx + math.cos(a) * rad + f * 10, self.cy + math.sin(a) * rad * 0.5, z + k * 2))
        return out

    def update(self, dt):
        self.age += dt
        if self.age >= self.DURATION:
            self.alive = False
            for x, y, z in self.positions():
                b = Butterfly(self.world, species=self.species)
                b.x, b.y, b.z = x, y, z
                b.heading = self.world.rng.uniform(0, 2 * math.pi)
                self.world.entities.append(b)

    def draw(self, r):
        for i, (x, y, z) in enumerate(self.positions()):
            r.blit_px(r.shadow_sprite(2, 1, 40), x - 2, y - 1)
            frame = self.frames[(0, 1, 2, 1)[int(self.age * 14 + i) % 4]]
            r.draw_sprite(frame, x, y - z, Butterfly.ANCHOR)


class DewWeb(Effect):
    """A spider's web on the edge of a bush, strung with dew, glinting in
    the low morning sun until it dries."""

    def __init__(self, world):
        self.world = world
        rng = world.rng
        bush = rng.choice(world.terrain.bushes)
        side = rng.choice((-1, 1))
        self.cx = bush.x + side * (bush.rx + 2)
        self.cy = bush.y - bush.ry - 2
        pts = set()
        for k in range(7):
            a = k * math.tau / 7 + rng.uniform(-0.15, 0.15)
            for d in (1.5, 2.5, 3.5, 4.5, 5.5):
                pts.add((round(self.cx + math.cos(a) * d), round(self.cy + math.sin(a) * d * 0.8)))
        for ring in (2.5, 4.5):
            for k in range(18):
                a = k * math.tau / 18
                pts.add((round(self.cx + math.cos(a) * ring), round(self.cy + math.sin(a) * ring * 0.8)))
        self.points = [(x, y, rng.random() * 6.28) for x, y in sorted(pts)]
        self.age = 0.0

    def update(self, dt):
        self.age += dt
        env = self.world.env
        if env.sun > 0.85 or env.rain > 0.2 or self.age > 1800:
            self.alive = False

    def draw_glow(self, r):
        env = self.world.env
        fade = min(1.0, self.age / 20.0) * (1.0 - max(0.0, env.sun - 0.6) / 0.25)
        t = self.world.time
        for x, y, phase in self.points:
            tw = 0.5 + 0.5 * math.sin(t * 2.2 + phase)
            a = int((60 + 140 * tw ** 6) * fade)
            if a > 12:
                r.blit_px(r.dot((150, 160, 170), a, 1, 1), x, y, add=True)


# ==========================================================================
# Events

class Event:
    name = ""
    tier = "common"
    title = ""
    weight = 1.0
    cooldown = 600.0     # real seconds before it may happen again
    omen = 0.0           # seconds of hush before it happens

    def ready(self, world):
        return True

    def affinity(self, p):
        """How much Mochi's character draws this event (weight multiplier)."""
        return 1.0

    def timing(self, world):
        """How right the time of day is, 0..1: a smooth peak on the clock
        (from the settings) rather than a window that switches on and off."""
        spec = HOURS.get(self.name)
        return 1.0 if spec is None else peaks(world.env.clock.standard_hour, spec)

    def caption(self, world):
        return self.title

    def start(self, world, events):
        """Make it happen.  Return an Effect, True, or None if it could not
        happen after all."""
        return True


def _awake(cat):
    return cat.posture != "sleep" and cat.interruptible


def _dry_day(env):
    return env.sun > 0.55 and env.rain < 0.05 and not env.snowing


def _free_spot(world, away=90):
    t = world.terrain
    rng = world.rng
    for _ in range(30):
        x, y = rng.uniform(40, world.width - 40), rng.uniform(50, world.height - 20)
        if t.free_ground(x, y) and world.cat.distance_to(_P(x, y)) > away:
            return x, y
    return None


class _P:
    def __init__(self, x, y):
        self.x, self.y = x, y


# --- common ---------------------------------------------------------------

class TailChase(Event):
    name, tier = "tail chase", "common"

    def affinity(self, p):
        return p.lean("playful", 0.3, 2.0) * (1.4 if p.mood > 0.5 else 1.0)

    def ready(self, world):
        cat = world.cat
        return _awake(cat) and cat.needs.energy > 0.4 and world.env.rain < 0.1

    def start(self, world, events):
        cat = world.cat
        return True if cat.attend("tail_chase", cat.act_tail_chase()) else None


class DandelionSeeds(Event):
    name, tier = "dandelion seeds", "common"

    def ready(self, world):
        env = world.env
        return env.season in ("spring", "summer") and _dry_day(env) and env.wind.strength < 0.8

    def start(self, world, events):
        return Seeds(world)


class FallingFeather(Event):
    name, tier = "a feather", "common"

    def affinity(self, p):
        return p.lean("curious", 0.5, 1.6)

    def ready(self, world):
        return _dry_day(world.env)

    def start(self, world, events):
        return Feather(world)


class CrowVisit(Event):
    name, tier = "a crow", "common"

    def ready(self, world):
        env = world.env
        return env.sun > 0.4 and env.rain < 0.2 and world.count("crow") == 0

    def start(self, world, events):
        spot = _free_spot(world, away=80)
        if spot is None:
            return None
        world.entities.append(Crow(world, *spot))
        return True


class MousePeek(Event):
    name, tier = "a mouse peeking out", "common"

    def affinity(self, p):
        return p.lean("curious", 0.5, 1.6)

    def ready(self, world):
        return world.terrain.bushes and world.env.rain < 0.2 and world.count("mouse") == 0

    def start(self, world, events):
        bush = min(world.terrain.bushes, key=lambda b: abs(world.cat.distance_to(b) - 90))
        mouse = PeekingMouse(world, bush)
        world.entities.append(mouse)
        cat = world.cat
        if _awake(cat) and cat.distance_to(mouse) < 160:
            cat.attend("peek", cat.act_gaze(mouse.x, mouse.y, 4.0, "staring at a bush"))
        return True


class ShadowPounce(Event):
    name, tier = "pouncing on a shadow", "common"

    def affinity(self, p):
        return p.lean("playful", 0.3, 2.0)

    def ready(self, world):
        env = world.env
        cat = world.cat
        return env.sun > 0.6 and env.weather.cloud < 0.5 and env.rain < 0.05 and _awake(cat) \
            and cat.needs.play > 0.3

    def start(self, world, events):
        cat = world.cat
        flock = BirdFlock(world)
        flock.birds = flock.birds[:2]
        # Aim the flight straight over Mochi.
        bx, by, _ = flock.birds[0]
        t_cross = abs(cat.x - bx) / abs(flock.vx)
        flock.vy = (cat.y - by) / max(0.5, t_cross)
        if not cat.attend("shadow", cat.act_shadow(flock)):
            return None
        world.overhead.append(flock)
        return True


class LeafChase(Event):
    name, tier = "chasing a leaf", "common"

    def affinity(self, p):
        return p.lean("playful", 0.3, 2.0)

    def ready(self, world):
        env = world.env
        breezy = env.wind.strength > 0.3 or env.season == "autumn"
        return breezy and env.rain < 0.05 and not env.snowing and _awake(world.cat) and env.snow_cover < 0.3

    def start(self, world, events):
        return TumbleLeaf(world)


class GrasshopperVisit(Event):
    name, tier = "a grasshopper", "common"

    def ready(self, world):
        env = world.env
        return (env.season in ("summer", "spring", "autumn") and world.director.warmth > 16 and _dry_day(env)
                and world.count("grasshopper") == 0)

    def start(self, world, events):
        cat = world.cat
        rng = world.rng
        for _ in range(30):
            a = rng.uniform(0, math.tau)
            x, y = cat.x + math.cos(a) * rng.uniform(60, 110), cat.y + math.sin(a) * rng.uniform(30, 60)
            if world.terrain.free_ground(x, y) and 10 < x < world.width - 10 and 20 < y < world.height - 8:
                world.entities.append(Grasshopper(world, x, y))
                return True
        return None


class Moths(Event):
    name, tier = "moths", "common"

    def ready(self, world):
        env = world.env
        return (env.sun < 0.1 and world.director.warmth > 14 and env.rain < 0.05 and env.wind.strength < 0.6
                and world.count("moth") == 0)

    def start(self, world, events):
        for _ in range(count(world.rng, COUNTS["moths"])):
            m = Moth(world)
            m.x = world.rng.uniform(40, world.width - 40)
            world.entities.append(m)
        return True


class AfterRain(Event):
    name, tier = "puddles", "common"
    weight = 5.0       # only possible just after a downpour

    def ready(self, world):
        env = world.env
        heavy = world.time - world.events.last_shower < 300
        return heavy and env.rain < 0.08 and not env.snowing and not any(isinstance(e, Puddles) for e in world.effects)

    def start(self, world, events):
        fx = Puddles(world)
        if not fx.alive:
            return None
        rng = world.rng
        cat = world.cat
        puddle = rng.choice(fx.items)
        if rng.random() < 0.6 and world.count("sparrow") == 0:
            flock = [Sparrow(world, puddle.x + rng.uniform(-14, 14), puddle.y + rng.uniform(-6, 6),
                             delay=i * rng.uniform(0.2, 0.8)) for i in range(rng.randint(2, 4))]
            for b in flock:
                b.flock = flock
                world.entities.append(b)
        if cat.needs.thirst > 0.25 or rng.random() < 0.4:
            cat.attend("puddle", cat.act_drink_puddle(puddle))
        return fx


class TwoButterflies(Event):
    name, tier = "two butterflies dancing", "common"

    def ready(self, world):
        env = world.env
        return _dry_day(env) and world.director.warmth > 14 and env.wind.strength < 0.6

    def start(self, world, events):
        return ButterflyDance(world)


class DewyWeb(Event):
    name, tier = "a dewy spider web", "common"

    def ready(self, world):
        env = world.env
        return (self.timing(world) > 0.15 and env.season != "winter" and env.rain < 0.05 and env.sun > 0.2
                and env.temperature < 17 and world.terrain.bushes
                and not any(isinstance(e, DewWeb) for e in world.effects))

    def start(self, world, events):
        return DewWeb(world)


# --- uncommon -------------------------------------------------------------

class MorningMist(Event):
    name, tier, title = "morning mist", "uncommon", "Morning mist over the meadow"

    def ready(self, world):
        env = world.env
        return (self.timing(world) > 0.15 and env.wind.strength < 0.45 and env.rain < 0.1
                and env.temperature < 16 and not any(isinstance(e, Mist) for e in world.effects))

    def start(self, world, events):
        return Mist(world)


class RainbowEvent(Event):
    name, tier, title = "a rainbow", "uncommon", "A rainbow, mirrored in the pond"
    weight = 4.0   # its moment is brief: take it when it comes

    def ready(self, world):
        env = world.env
        events = world.events
        just_stopped = world.time - events.last_shower < FX["rainbow_after_rain"] and env.rain < 0.05
        return (just_stopped and world.terrain.pond is not None and 4 < env.sky.sun_alt < 40
                and env.weather.cloud < 0.85 and not env.snowing)

    def start(self, world, events):
        return Rainbow(world)


class ThunderstormEvent(Event):
    name, tier, title = "a thunderstorm", "uncommon", "Lightning flickers over the meadow"
    weight = 3.0   # it can only come in a downpour: take it when it does

    def ready(self, world):
        env = world.env
        return (env.rain > 0.7 and env.temperature > 10 and not env.snowing
                and getattr(world, "storm", None) is None)

    def start(self, world, events):
        return Thunderstorm(world)


class LeafWhirl(Event):
    name, tier, title = "a whirlwind", "uncommon", "A gust spins up the leaves"

    def ready(self, world):
        env = world.env
        windy = env.wind.strength > 0.45 or (env.season == "autumn" and env.wind.strength > 0.3)
        return windy and env.rain < 0.1 and not env.snowing and env.sun > 0.3

    def start(self, world, events):
        return Whirl(world)


class DuskBats(Event):
    name, tier, title = "bats", "uncommon", "Bats out hunting at dusk"

    def ready(self, world):
        env = world.env
        return (self.timing(world) > 0.15 and env.sun < 0.3 and env.rain < 0.05
                and world.director.warmth > 13 and world.count("bat") == 0)

    def start(self, world, events):
        for _ in range(count(world.rng, COUNTS["bats"])):
            world.entities.append(Bat(world))
        return True


# --- rare -------------------------------------------------------------------

class ShootingStarEvent(Event):
    name, tier, title = "a shooting star", "rare", "A shooting star"

    def ready(self, world):
        env = world.env
        return (env.sun < 0.02 and env.weather.cloud < 0.4 and world.terrain.pond is not None
                and not any(isinstance(e, MeteorShower) for e in world.effects))

    def start(self, world, events):
        cat = world.cat
        pond = world.terrain.pond
        if _awake(cat):
            cat.attend("star", cat.act_gaze(pond.cx, pond.cy, 3.0, "looking at the pond"))
        return ShootingStar(world)


class FoxVisit(Event):
    name, tier, title = "a fox", "rare", "A fox trots through the meadow"

    def ready(self, world):
        env = world.env
        return self.timing(world) > 0.15 and env.rain < 0.2 and world.count("fox") == 0

    def start(self, world, events):
        fox = Fox(world)
        if not fox.ok:
            return None
        world.entities.append(fox)
        return True


class HeronVisit(Event):
    name, tier, title = "a heron", "rare", "A heron comes fishing"

    def ready(self, world):
        env = world.env
        return (world.terrain.pond is not None and env.sun > 0.2 and env.rain < 0.3 and env.temperature > 1
                and world.count("heron") == 0)

    def start(self, world, events):
        heron = Heron(world)
        if not heron.ok:
            return None
        world.entities.append(heron)
        return True


class AGift(Event):
    name, tier = "a gift", "uncommon"

    def affinity(self, p):
        return p.lean("affectionate", 0.3, 2.0)

    def ready(self, world):
        env = world.env
        return (_awake(world.cat) and env.rain < 0.1 and env.sun > 0.2 and world.terrain.spots["bowl"]
                and world.count("gift") == 0)

    def caption(self, world):
        return ""      # she announces it herself when she drops it

    def start(self, world, events):
        cat = world.cat
        what = world.rng.choice(["leaf", "feather", "toy mouse"])
        return True if cat.attend("gift", cat.act_gift(what)) else None


class DuckFamily(Event):
    name, tier, title = "a duck and her ducklings", "rare", "A duck leads her ducklings to the pond"

    def ready(self, world):
        env = world.env
        p = env.sky.year_phase
        nesting = 0.30 <= p <= 0.55          # May to mid-July: ducklings about
        return (nesting and world.terrain.pond is not None and env.sun > 0.4 and env.rain < 0.2
                and world.count("duck") == 0)

    def start(self, world, events):
        duck = Duck(world, brood=count(world.rng, COUNTS["ducklings"]))
        if not duck.ok:
            return None
        world.entities.append(duck)
        world.entities.extend(duck.ducklings)
        return True


class GingerVisit(Event):
    name, tier = "the ginger cat", "rare"

    def affinity(self, p):
        return 1.0 + 0.2 * max(0, p.friendship("ginger"))

    def ready(self, world):
        env = world.env
        return env.sun > 0.15 and env.rain < 0.05 and world.count("visitor") == 0

    def caption(self, world):
        if world.events.journal_count(self.name) > 0:
            return "The ginger cat is back"
        return "A ginger cat has come to visit"

    def start(self, world, events):
        from .entities.visitor import VisitorCat
        visitor = VisitorCat(world)
        if visitor.entry is None:
            return None
        world.entities.append(visitor)
        return True


class FourthWall(Event):
    name, tier, title = "Mochi noticed you", "rare", "Mochi has noticed you"

    def affinity(self, p):
        return p.lean("affectionate", 0.3, 2.0)

    def caption(self, world):
        return f"{world.cat.name} has noticed you"

    def ready(self, world):
        cat = world.cat
        return _awake(cat) and world.env.rain < 0.1 and cat.needs.energy > 0.3

    def start(self, world, events):
        cat = world.cat
        return True if cat.attend("fourth_wall", cat.act_fourth_wall()) else None


# --- legendary --------------------------------------------------------------

class GoldenButterflyEvent(Event):
    name, tier, title = "the golden butterfly", "legendary", "A golden butterfly!"

    def ready(self, world):
        env = world.env
        return _dry_day(env) and env.sun > 0.7 and world.director.warmth > 15 and env.wind.strength < 0.6

    def start(self, world, events):
        bf = GoldenButterfly(world)
        world.entities.append(bf)
        cat = world.cat
        cat.attend("golden", cat.act_follow(bf), wake=True)
        return True


class DeerAtDawn(Event):
    name, tier, title = "a deer at dawn", "legendary", "A deer, at first light"

    def ready(self, world):
        env = world.env
        return (self.timing(world) > 0.15 and env.rain < 0.1 and env.wind.strength < 0.6
                and env.snow_cover < 0.7 and world.count("deer") == 0)

    def start(self, world, events):
        deer = Deer(world)
        if not deer.ok:
            return None
        world.entities.append(deer)
        env = world.env
        if env.temperature < 18 and not any(isinstance(e, Mist) for e in world.effects):
            world.effects.append(Mist(world))     # she steps out of the mist
        return True


# --- noticed, not rolled ----------------------------------------------------

class Notice(Event):
    """Happens when the world makes it true, once per ``key``.

    ``persist``: remember the key across runs (a full moon is announced once
    a night, however often the screensaver starts).  ``lasting``: if the
    meadow starts while it is still true, its effect resumes quietly."""

    persist = True
    lasting = False

    def key(self, world):
        return world.env.clock.date.isoformat()

    def triggered(self, world):
        return False


class Birthday(Notice):
    name, tier = "Mochi's birthday", "legendary"

    def triggered(self, world):
        return world.cat.birthday

    def key(self, world):
        return str(world.env.clock.date.year)

    def caption(self, world):
        return f"It's {world.cat.name}'s birthday!"


class FullMoon(Notice):
    name, tier, title = "a full moon", "rare", "A full moon over the meadow"

    def key(self, world):
        return night_key(world.env.clock.moment)

    def triggered(self, world):
        env = world.env
        return env.sky.full_moon and env.sky.moon_alt > 15 and env.sun < 0.05 and env.weather.cloud < 0.4


class LunarEclipse(Notice):
    name, tier, title = "a lunar eclipse", "legendary", "A lunar eclipse: the moon turns copper in the pond"

    def key(self, world):
        return night_key(world.env.clock.moment)

    def triggered(self, world):
        env = world.env
        sky = env.sky
        return (sky.eclipse > 0.4 and sky.moon_alt > 3 and env.sun < 0.05 and env.weather.cloud < 0.6
                and world.terrain.pond is not None)


class MeteorShowerNotice(Notice):
    name, tier = "a meteor shower", "legendary"
    lasting = True

    def key(self, world):
        return night_key(world.env.clock.moment)

    def caption(self, world):
        return f"The {shower_tonight(world.env.clock.moment)} are falling tonight"

    def triggered(self, world):
        env = world.env
        return (shower_tonight(env.clock.moment) is not None and env.sun < 0.02 and env.weather.cloud < 0.5
                and world.terrain.pond is not None)

    def start(self, world, events):
        return MeteorShower(world)


class FirstSnow(Notice):
    name, tier, title = "the first snow", "legendary", "The first snow of winter"

    def triggered(self, world):
        env = world.env
        journal = world.events.journal
        if env.snow_cover < 0.12 or not env.snowing:
            return False
        last = journal.notes.get("last_snow") if journal else None
        if last is None:
            return True
        gap = (env.clock.date - datetime.date.fromisoformat(last)).days
        return gap > 60

    def key(self, world):
        return f"snow-{world.env.clock.date.year}-{world.env.clock.date.month // 7}"


class NewYear(Notice):
    name, tier, title = "New Year fireworks", "legendary", "Happy New Year!"
    lasting = True

    def triggered(self, world):
        c = world.env.clock
        return c.date.month == 1 and c.date.day == 1 and c.hour < 0.3

    def start(self, world, events):
        fx = Fireworks(world)
        events.noisy_until = world.time + fx.duration + 5
        cat = world.cat
        cat.attend("fireworks", cat.act_flee_noise(), wake=True)
        return fx


class Halloween(Notice):
    name, tier, title = "a carved pumpkin", "uncommon", "A carved pumpkin by the bowl"
    persist = False      # the pumpkin is there every run of the season

    def triggered(self, world):
        return (halloween(world.env.clock.date) and world.terrain.bowl is not None
                and world.count("pumpkin") == 0)

    def key(self, world):
        return str(world.env.clock.date.year)

    def start(self, world, events):
        t = world.terrain
        bx, by = t.bowl
        for dx, dy in ((-16, 2), (16, 2), (-14, 8), (14, 8), (0, 12)):
            if t.free_ground(bx + dx, by + dy):
                world.entities.append(Pumpkin(world, bx + dx, by + dy))
                return True
        return None

    def caption(self, world):
        # Seen every day of the season; the caption only on the first.
        return self.title if world.events.journal_count(self.name) == 0 else ""


ROLLED = [TailChase(), DandelionSeeds(), FallingFeather(), CrowVisit(), MousePeek(), ShadowPounce(), LeafChase(),
          GrasshopperVisit(), Moths(), AfterRain(), TwoButterflies(), DewyWeb(),
          MorningMist(), RainbowEvent(), ThunderstormEvent(), LeafWhirl(), DuskBats(), AGift(),
          ShootingStarEvent(), FourthWall(), GingerVisit(), FoxVisit(), HeronVisit(), DuckFamily(),
          GoldenButterflyEvent(), DeerAtDawn()]
NOTICES = [Birthday(), FullMoon(), LunarEclipse(), MeteorShowerNotice(), FirstSnow(), NewYear(), Halloween()]
ALL = {e.name: e for e in ROLLED + NOTICES}
# Cooldowns and omens come from the settings.
for _event in ALL.values():
    _event.cooldown = 60.0 * _EVENTS["cooldown_minutes"].get(_event.name, _event.cooldown / 60.0)
    _event.omen = float(_EVENTS["omen_seconds"].get(_event.name, 0.0))


# How a recap says each event ("While you were away, Mochi saw ...").
RECAP = {"Mochi noticed you": "came to the screen looking for you", "the ginger cat": "had a visit from the ginger cat",
         "a carved pumpkin": None, "New Year fireworks": "hid from the New Year fireworks"}


def recap(summary, name, now):
    """One line about the last session, or None if there's nothing to say
    (or it was too long ago to matter)."""
    if not summary:
        return None
    try:
        import datetime
        ended = datetime.datetime.fromisoformat(summary["ended"])
    except (KeyError, ValueError):
        return None
    if not datetime.timedelta(0) <= now - ended <= datetime.timedelta(days=3):
        return None
    rank = {t: i for i, t in enumerate(TIERS)}
    events = [e for e in summary.get("events", []) if RECAP.get(e[1], "") is not None]
    if events:
        when, what, tier = max(events, key=lambda e: (rank.get(e[2], 0), e[0]))
        verb = RECAP.get(what) or f"saw {what}"
        return f"While you were away, {name} {verb} at {when}", tier
    naps = summary.get("naps", 0)
    if naps:
        return f"While you were away, {name} napped {naps} time{'s' if naps != 1 else ''}", "uncommon"
    return None


class Caption:
    __slots__ = ("text", "tier", "age")

    def __init__(self, text, tier):
        self.text, self.tier, self.age = text, tier, 0.0


class Events:
    """Decides when something happens, and keeps track of it."""

    def __init__(self, world, journal=None):
        self.world = world
        self.journal = journal
        rng = world.rng
        # Start part-way into each tier's wait, so the first hour isn't empty.
        self.since = {t: rng.uniform(0.3, 0.8) * MEAN[t] for t in TIERS}
        self.ready_at = {}
        self.active = []          # (event, effect or None, ends_at)
        self.pending = None       # (event, starts_at): a legendary event's omen
        self.timer = rng.uniform(1.0, CHECK)
        self.noisy_until = 0.0
        self.last_shower = -1e9
        self.done = set(journal.notes.get("done", [])) if journal else set()   # notice keys already seen
        self.history = []         # (world.time, name) this session
        self.log = []             # (clock moment, name, tier) of uncommon-or-rarer events this session

    # --- queries ----------------------------------------------------------

    @property
    def noisy(self):
        return self.world.time < self.noisy_until

    @property
    def hushed(self):
        return self.pending is not None

    def journal_count(self, name):
        return self.journal.count(name) if self.journal else sum(1 for _, n in self.history if n == name)

    def chance(self, tier):
        """Odds of a ``tier`` event at one check: the base rate, growing once
        the tier is overdue (twice its mean wait: 2.5 times as likely)."""
        mean = MEAN[tier]
        overdue = max(0.0, self.since[tier] / mean - 1.0)
        return CHECK / mean * (1.0 + OVERDUE_BOOST * overdue)

    def big_running(self):
        now = self.world.time
        return any(ev.tier in BIG and (fx is not None and getattr(fx, "alive", False) or now < ends)
                   for ev, fx, ends in self.active)

    # --- the clock ----------------------------------------------------------

    def update(self, dt):
        world = self.world
        env = world.env
        if env.rain > 0.3 and not env.snowing:
            self.last_shower = world.time
        for t in TIERS:
            self.since[t] += dt
        now = world.time
        self.active = [(ev, fx, ends) for ev, fx, ends in self.active
                       if (fx is not None and getattr(fx, "alive", False)) or now < ends]
        if self.pending is not None:
            event, at = self.pending
            if now >= at:
                self.pending = None
                self.happen(event)
            return
        self.timer -= dt
        if self.timer > 0:
            return
        self.timer = CHECK
        for event in NOTICES:
            key = f"{event.name}:{event.key(world)}"
            if not event.triggered(world):
                continue
            if key not in self.done:
                if self.happen(event):
                    self._mark(key, event.persist)
            elif event.lasting and not self._running(event):
                self.happen(event, quiet=True)
        if env.snow_cover > 0.12 and self.journal is not None:
            today = env.clock.date.isoformat()
            if self.journal.notes.get("last_snow") != today:
                self.journal.note("last_snow", today)
        for tier in reversed(TIERS):
            if world.rng.random() >= self.chance(tier):
                continue
            if tier in BIG and self.big_running():
                continue
            options = [e for e in ROLLED if e.tier == tier and now >= self.ready_at.get(e.name, 0.0)
                       and e.ready(world)]
            if not options:
                continue
            event = self._pick(options)
            if world.rng.random() > event.timing(world):
                continue        # the hour is only half right: maybe another time
            if event.omen:
                self._hush()
                wobble = 1.0 + world.rng.gauss(0.0, _EVENTS["omen_spread"])
                self.pending = (event, now + event.omen * max(0.4, wobble))
                self.since[tier] = 0.0
                return
            if self.happen(event):
                return

    def _pick(self, options):
        p = self.world.cat.p
        world = self.world
        weights = [e.weight * e.affinity(p) * e.timing(world) for e in options]
        r = self.world.rng.uniform(0, sum(weights))
        for e, w in zip(options, weights):
            r -= w
            if r <= 0:
                return e
        return options[-1]

    def _hush(self):
        """Before something legendary the birds fall quiet and go."""
        for e in self.world.entities:
            if isinstance(e, Bird) and e.state == "ground":
                e._take_off()

    def _mark(self, key, persist=True):
        self.done.add(key)
        if persist and self.journal is not None:
            kept = [k for k in self.journal.notes.get("done", []) if k != key] + [key]
            self.journal.note("done", kept[-60:])

    def _running(self, event):
        return any(ev is event and fx is not None and fx.alive for ev, fx, _ in self.active)

    # --- making things happen -------------------------------------------------

    def happen(self, event, quiet=False):
        world = self.world
        result = event.start(world, self)
        if not result:
            return False
        effect = result if isinstance(result, Effect) else None
        if effect is not None:
            world.effects.append(effect)
        now = world.time
        self.ready_at[event.name] = now + lognormal(world.rng, event.cooldown, _EVENTS["cooldown_spread"])
        self.since[event.tier] = 0.0
        self.active.append((event, effect, now + 60.0))
        if quiet:
            return True
        text = event.caption(world) if event.tier != "common" else ""
        self.history.append((now, event.name))
        if event.tier != "common":
            self.log.append((world.env.clock.moment, event.name, event.tier))
        if text:
            world.say(text, event.tier)
        if self.journal is not None:
            self.journal.record(event.name, world.env.clock.moment)
        return True

    def force(self, name):
        """Make an event happen now, whatever the odds (``--event``)."""
        event = ALL[name]
        return self.happen(event)
