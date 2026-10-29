"""The meadow's seasonal stories: things that unfold over weeks of the real
calendar, a little differently every year.

    the nest    early April: a pair of blackbirds builds in the old tree.
                The hen lays an egg each morning and sits tight for a
                fortnight; both parents carry food to the chicks for
                another; then the speckled fledglings spend a few weeks
                about the bushes, fed by their parents, who scold Mochi
                whenever she comes near.
    the frogs   a mild night in March leaves frogspawn in the shallows; a
                fortnight or so later it hatches, tadpoles wriggle in the
                warm edges all spring, and for a few days in early summer
                tiny frogs leave the pond.
    storks      late August: white storks on their way south over the
                Bosphorus circle in the midday thermals (and a smaller
                passage comes back north in spring).
    geese       autumn: skeins of geese heading south, mornings and
                evenings (and north again at the end of winter).

``Almanac`` decides when each happens, per meadow and year, from the
distributions in the settings: the same however often the meadow restarts,
and shifting a little from one year to the next.  ``Stories`` (one per
world) reads the clock and keeps what is on screen in step with it.  The
birds high overhead only reach the meadow as their shadows and their
reflections in the pond.

Everything here draws its own random numbers, so the rest of the meadow
plays out exactly as it would without the stories.
"""

import math
import random

import numpy as np
import pygame

from . import story_art
from .chance import count, peaks, sample
from .settings import SETTINGS
from .util import clamp

STORY = SETTINGS["stories"]
NEST = STORY["nest"]
FROGS = STORY["frogs"]
STORKS = STORY["storks"]
GEESE = STORY["geese"]
RATE_CAP = float(STORY["rate_cap"])
DAYS = 365
# Where the pond shows the sky: a patch of it a little north of the pond,
# made smaller (it's high up).
MIRROR_NORTH = 60.0
MIRROR_SCALE = 0.45
# The way migrants go, on screen (north is up): storks over the Bosphorus
# head south-east into Anatolia, geese south-south-west.
HEADINGS = {"storks": 1.05, "geese": 1.9}


def story_day(moment, lat):
    """(story year, day of it): days since 1 January in the north and, so
    that the same day means the same season, since early July in the south
    (as ``sky.year_phase`` counts).  The day carries the time as a
    fraction."""
    date = moment.date()
    doy = date.timetuple().tm_yday - 1
    hour = (moment.hour + moment.minute / 60 + moment.second / 3600) / 24
    if lat >= 0:
        return date.year, min(doy, DAYS - 1) + hour
    shifted = doy + 182
    if shifted >= DAYS:
        return date.year, min(shifted - DAYS, DAYS - 1) + hour
    return date.year - 1, shifted + hour


class Stage:
    """One step of a story: ``name`` from ``start`` to ``end`` (days)."""

    __slots__ = ("name", "start", "end")

    def __init__(self, name, start, end):
        self.name, self.start, self.end = name, start, end

    def progress(self, day):
        return clamp((day - self.start) / max(1e-6, self.end - self.start), 0.0, 1.0)


class Nesting:
    """One year's nest: when it is built, the eggs, the chicks, the
    fledglings."""

    def __init__(self, rng):
        n = NEST
        self.build = math.floor(sample(rng, n["building_starts"])) + 0.30     # they start in the morning
        self.lay = math.ceil(self.build + sample(rng, n["building_days"])) + 0.25   # then an egg each morning
        self.eggs = count(rng, n["eggs"])
        self.sit = self.lay + self.eggs - 1                                     # she sits from the last one
        self.hatch = self.sit + sample(rng, n["sitting_days"])
        self.fledge = math.floor(self.hatch + sample(rng, n["nestling_days"])) + 0.30   # they leave in the morning
        self.free = self.fledge + sample(rng, n["fledgling_days"])
        self.gone = self.fledge + sample(rng, n["empty_days"])
        self.stages = [Stage("building", self.build, self.lay), Stage("laying", self.lay, self.sit),
                       Stage("sitting", self.sit, self.hatch), Stage("chicks", self.hatch, self.fledge),
                       Stage("fledglings", self.fledge, self.free)]

    def stage(self, day):
        for s in self.stages:
            if s.start <= day < s.end:
                return s
        return None

    def present(self, day):
        """The nest is in the tree (built, in use, or left empty)."""
        return self.build <= day < self.gone

    def eggs_laid(self, day):
        return int(clamp(math.floor(day - self.lay) + 1, 0, self.eggs))


class Spawning:
    """One year's frogs: the night of the spawn, the tadpoles, the
    froglets leaving."""

    def __init__(self, rng):
        f = FROGS
        self.spawn = math.floor(sample(rng, f["spawn_night"])) + 0.9       # after dark
        self.hatch = self.spawn + sample(rng, f["spawn_days"])
        self.out = self.hatch + sample(rng, f["tadpole_days"])
        self.gone = self.out + sample(rng, f["froglet_days"])
        self.clumps = count(rng, f["clumps"])
        self.stages = [Stage("spawn", self.spawn, self.hatch), Stage("tadpoles", self.hatch, self.out),
                       Stage("froglets", self.out, self.gone)]

    def stage(self, day):
        for s in self.stages:
            if s.start <= day < s.end:
                return s
        return None


class Passage:
    """Migrants going over: how strong the passage is on a day, and which
    way they're heading."""

    def __init__(self, rng, spec, kind, seed, year):
        self.kind = kind
        self.spec = spec
        self.key = f"meadow {seed} {kind} {year}"
        self.waves = [(sample(rng, spec["autumn_peak"]), spec["autumn_days"], 1.0, "south"),
                      (sample(rng, spec["spring_peak"]), spec["spring_days"], spec["spring_strength"], "north")]
        self._luck = {}

    def luck(self, day):
        """Each day's own luck: a good day for it, or hardly any (the wind
        in the wrong quarter)."""
        d = int(day)
        hit = self._luck.get(d)
        if hit is None:
            hit = sample(random.Random(f"{self.key} {d}"), self.spec["daily_luck"])
            self._luck[d] = hit
        return hit

    def strength(self, day):
        """(how strong, "south" or "north"): 1 at the height of the autumn
        passage on an ordinary day."""
        best, way = 0.0, None
        for peak, width, strength, heading in self.waves:
            d = day - peak
            if abs(d) > 3 * width:
                continue
            k = strength * math.exp(-0.5 * (d / width) ** 2)
            if k > best:
                best, way = k, heading
        if not best:
            return 0.0, None
        return best * self.luck(day), way

    def stages(self):
        return [Stage(f"{self.kind} going {way}", peak - 2 * width, peak + 2 * width)
                for peak, width, _, way in self.waves]


class Almanac:
    """This meadow's dates for every story in one (story) year.  Each story
    draws from its own random numbers, so changing one story's settings
    leaves the others' dates alone."""

    def __init__(self, seed, year):
        self.seed, self.year = seed, year
        rng = random.Random(f"meadow {seed} nest {year}")
        self.nest = Nesting(rng) if rng.random() < NEST["chance"] else None
        self.frogs = Spawning(random.Random(f"meadow {seed} frogs {year}"))
        self.storks = Passage(random.Random(f"meadow {seed} storks {year}"), STORKS, "storks", seed, year)
        self.geese = Passage(random.Random(f"meadow {seed} geese {year}"), GEESE, "geese", seed, year)

    def changes(self):
        """Every stage start this year: [(day, story, stage name)]."""
        out = []
        if self.nest is not None:
            out += [(s.start, "nest", s.name) for s in self.nest.stages]
        out += [(s.start, "frogs", s.name) for s in self.frogs.stages]
        for passage in (self.storks, self.geese):
            out += [(s.start, passage.kind, s.name) for s in passage.stages()]
        return sorted(out)


# ==========================================================================
# The nest in the crown

class NestSite:
    """Where the blackbirds nest: a spot in the old tree's crown with leaves
    all round it, low on its front, where you can see into the cup.  It is
    drawn over the crown, fading and swaying with it."""

    def __init__(self, world):
        self.world = world
        tree = world.terrain.tree
        self.canopy = canopy = tree.canopy
        frame = canopy.base_frames[0]
        fw, fh = frame.get_size()
        solid = pygame.surfarray.array_alpha(frame).swapaxes(0, 1) > 0
        nw, nh = story_art.NEST_SIZE
        rng = random.Random(world.terrain.seed + 717)
        spots = []
        for y in range(int(fh * 0.42), int(fh * 0.72)):
            for x in range(int(fw * 0.22), int(fw * 0.78) - nw):
                if solid[y - 2:y + nh + 2, x - 2:x + nw + 2].all():
                    spots.append((x, y))
        ax, ay = canopy.anchor
        if spots:
            px, py = rng.choice(spots)
        else:
            px, py = int(ax - nw / 2), int(ay)
        cx, cy = story_art.NEST_ANCHOR
        self.x = canopy.x - ax + px + cx          # the middle of the cup, on screen
        self.y = canopy.y - ay + py + cy
        self.foot = (self.x, tree.y - 2.0)        # the ground beneath it
        self.height = self.foot[1] - self.y
        self.frames = nest_frames()
        self.look = None          # which drawing: None (no nest), "build2", "hen", "gape4_1", ...
        self.hen_on = False       # the hen is sitting
        self.hen_until = 0.0      # world time her sitting (or her break) ends
        self.feeding = 0.0        # seconds left of a parent at the nest with food: the chicks gape
        self.t = 0.0
        self.dirty = False        # something changed (a parent arrived, the hen left): redress now
        self._fringe_of = self._fringe_img = None

    def rim(self, side):
        """Where a parent perches to feed: (x, y on the ground, height)."""
        return self.x + side * 6.0, self.foot[1], self.height + 1.0

    def update(self, dt):
        self.t += dt
        if self.feeding > 0:
            self.feeding = max(0.0, self.feeding - dt)
            self.dirty = self.dirty or self.feeding == 0.0

    def layers(self):
        """[(surface, top-left x, top-left y)]: the nest, and the leaves of
        the crown in front of its rim, so it sits in the foliage rather
        than on it."""
        if self.look is None:
            return []
        frames = self.frames[self.look]
        frame = frames[int(self.t * (5.0 if self.look.startswith("gape") else 0.4)) % len(frames)]
        ax, ay = story_art.NEST_ANCHOR
        return [(frame, self.x - ax, self.y - ay), (self._fringe(), self.x - ax, self.y - ay)]

    def _fringe(self):
        crown = self.canopy.frames[0]          # (regraded with the seasons)
        if self._fringe_of is not crown:
            self._fringe_of = crown
            w, h = story_art.NEST_SIZE
            ax, ay = self.canopy.anchor
            nx, ny = story_art.NEST_ANCHOR
            left = int(round(self.x - nx - (self.canopy.x - ax)))
            top = int(round(self.y - ny - (self.canopy.y - ay)))
            rng = random.Random(self.world.terrain.seed + 719)
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            cw, ch = crown.get_size()
            for x in range(w):
                depth = rng.choice((1, 2, 2, 3)) if 3 <= x < w - 3 else rng.choice((2, 3, 4))
                for y in range(h - depth, h):
                    if 0 <= left + x < cw and 0 <= top + y < ch:
                        colour = crown.get_at((left + x, top + y))
                        if colour.a:
                            surf.set_at((x, y), colour)
            self._fringe_img = surf
        return self._fringe_img

    @property
    def showing(self):
        return self.look is not None and self.canopy.fade > 0.6


_NEST_FRAMES = {}


def nest_frames():
    if not _NEST_FRAMES:
        _NEST_FRAMES.update(story_art.nest_frames())
    return _NEST_FRAMES


# ==========================================================================
# Life in the pond

class PondLife:
    """Frogspawn in the shallows, and the tadpoles that hatch from it,
    drawn on the water like the fish."""

    def __init__(self, world, rng):
        self.world = world
        self.rng = rng
        t = world.terrain
        water = t.water
        # Shallows: water within a few pixels of the bank.
        near = np.zeros_like(water)
        for dy in range(-3, 4):
            for dx in range(-4, 5):
                near |= ~np.roll(np.roll(water, dy, 0), dx, 1)
        self.shallows = [(int(x), int(y)) for y, x in zip(*np.nonzero(water & near))]
        self.clumps = []          # (x, y, seed)
        self.stage = None
        self.progress = 0.0
        self.tadpoles = []        # [x, y, heading, wiggle phase, speed]
        self.school = None        # where the shoal is heading
        self._year = None
        self.spawn_frames = {}
        self.tadpole_frames = story_art.tadpole_frames()
        self._since = 0.0         # tadpoles move ten times a second: slow, and they're specks

    def place(self, almanac):
        """The spawn's clumps for this year, among the shallows."""
        if self._year == almanac.year:
            return
        self._year = almanac.year
        rng = random.Random(f"{almanac.seed} spawn {almanac.year}")
        self.clumps = []
        cells = self.shallows
        t = self.world.terrain
        for _ in range(almanac.frogs.clumps):
            for _ in range(40):
                x, y = cells[rng.randrange(len(cells))] if cells else (0, 0)
                if all(t.is_water(x + dx, y + dy) for dx, dy in ((-6, 0), (6, 0), (0, -3), (0, 3))) and \
                        all(abs(x - a) > 12 or abs(y - b) > 6 for a, b, _ in self.clumps):
                    self.clumps.append((x, y, rng.randrange(1 << 20)))
                    break

    def set_stage(self, stage, progress):
        self.stage, self.progress = stage, progress
        want = 0
        if stage == "tadpoles":
            want = FROGS["tadpoles"]
        elif stage == "froglets":
            want = int(FROGS["tadpoles"] * (1.0 - progress))         # leaving, a few more each day
        while len(self.tadpoles) > want:
            self.tadpoles.pop()
        while len(self.tadpoles) < want and self.clumps:
            x, y, _ = self.rng.choice(self.clumps)
            self.tadpoles.append([x + self.rng.uniform(-4, 4), y + self.rng.uniform(-2, 2),
                                  self.rng.uniform(0, 2 * math.pi), self.rng.random() * 6.28, self.rng.uniform(2, 5)])

    @property
    def spawn_look(self):
        """0 dots, 1 commas, 2 hatching, or None (no spawn to see)."""
        if self.stage == "spawn":
            return 0 if self.progress < 0.45 else 1 if self.progress < 0.85 else 2
        if self.stage == "tadpoles" and self.progress < 0.04:
            return 2
        return None

    def update(self, dt):
        if not self.tadpoles:
            return
        env = self.world.env
        self._since += dt
        if env.frozen or env.sun < 0.08 or self._since < 0.1:
            return
        dt, self._since = self._since, 0.0
        rng = self.rng
        t = self.world.terrain
        # The shoal drifts along the shallows, toward the warm side on a
        # sunny day; each tadpole wriggles after it, never quite in step.
        if self.school is None or rng.random() < dt * 0.05:
            self.school = rng.choice(self.shallows) if self.shallows else None
        if self.school is None:
            return
        sx, sy = self.school
        for tp in self.tadpoles:
            x, y, h, ph, sp = tp
            want = math.atan2(sy - y, sx - x) if math.hypot(sx - x, sy - y) > 6 else h
            h += clamp(math.atan2(math.sin(want - h), math.cos(want - h)), -2.5 * dt, 2.5 * dt)
            h += rng.uniform(-1.5, 1.5) * dt * 3
            ph += dt * (12.0 + sp * 2)
            nx, ny = x + math.cos(h) * sp * dt, y + math.sin(h) * sp * dt * 0.6
            if t.is_water(nx, ny) and t.is_water(nx + math.cos(h) * 2, ny):
                x, y = nx, ny
            else:
                h += math.pi * rng.uniform(0.6, 1.4)
            tp[0], tp[1], tp[2], tp[3] = x, y, h, ph

    def draw(self, r):
        env = self.world.env
        if env.frozen:
            return
        look = self.spawn_look
        if look is not None:
            for x, y, seed in self.clumps:
                key = (seed, look)
                frame = self.spawn_frames.get(key)
                if frame is None:
                    frame = story_art.spawn_frame(seed, look)
                    self.spawn_frames[key] = frame
                img, ox, oy = r.sprite(frame)
                w, h = frame.get_size()
                r.blit_px(img, x - w // 2 + ox, y - h // 2 + oy)
        if not self.tadpoles or env.sun < 0.08:
            return
        big = self.stage == "froglets" or (self.stage == "tadpoles" and self.progress > 0.45)
        wiggle = self.world.time * 7.0
        for x, y, h, ph, _ in self.tadpoles:
            frame = self.tadpole_frames[(big, math.cos(h) < 0, math.sin(ph + wiggle) > 0.3)]
            img, ox, oy = r.sprite(frame)
            r.blit_px(img, x - 2 + ox, y + oy)


# ==========================================================================
# Birds high overhead

def reflect(world, x, y):
    """Where something high in the sky over (x, y) shows in the pond, or
    None if it doesn't: the pond mirrors a patch of sky a little north of
    it, smaller."""
    pond = world.terrain.pond
    if pond is None or world.env.frozen:
        return None
    rx = pond.cx + (x - pond.cx) * MIRROR_SCALE
    ry = pond.cy + (y - (pond.cy - MIRROR_NORTH)) * MIRROR_SCALE
    return rx, ry


def _on_open_water(world, x, y, reach):
    t = world.terrain
    return (all(t.is_water(x + dx, y + dy) for dx, dy in ((-reach, 0), (reach, 0), (0, -reach * 0.5),
                                                           (0, reach * 0.5)))
            and not t.behind_crown(x, y))


class _Overhead:
    """What storks and geese share: shadows on the grass while the sun is
    out, reflections in the pond, and whether they're over the meadow."""

    kind = ""
    SHADOW_ABOVE = 0.45
    fast = True                # moving enough that the calm frame rate would show

    def __init__(self, world, rng):
        self.world = world
        self.rng = rng
        self.sprites = story_art.sky_sprites(self.kind)
        self.birds = []           # [x, y, heading, far, phase]
        self.alive = True
        self.t = 0.0

    @property
    def over_meadow(self):
        w, h = self.world.width, self.world.height
        return any(0 < b[0] < w and 0 < b[1] < h for b in self.birds)

    def _frame(self, which, bird):
        x, y, heading, far, phase = bird
        frames = self.sprites["far" if (which == "reflection" and far) else which][story_art.heading_index(heading)]
        return frames[int(phase) % len(frames)]

    def draw_shadow(self, light):
        env = self.world.env
        if env.sun < self.SHADOW_ABOVE or env.rain > 0.1 or env.weather.cloud > 0.75:
            return
        for bird in self.birds:
            frame = self._frame("shadow", bird)
            w, h = frame.get_size()
            light.blit(frame, (round(bird[0] - w / 2), round(bird[1] - h / 2)), special_flags=pygame.BLEND_MULT)

    def draw_reflection(self, r):
        world = self.world
        if world.env.weather.cloud > 0.8:
            return
        for bird in self.birds:
            spot = reflect(world, bird[0], bird[1])
            if spot is None:
                continue
            frame = self._frame("reflection", bird)
            w, h = frame.get_size()
            if not _on_open_water(world, spot[0], spot[1], w * 0.4):
                continue
            img, ox, oy = r.sprite(frame)
            r.blit_px(img, spot[0] - w / 2 + ox, spot[1] - h / 2 + oy)

    def reflected(self):
        """Is any of them in the pond just now?"""
        world = self.world
        for bird in self.birds:
            spot = reflect(world, bird[0], bird[1])
            if spot is not None and _on_open_water(world, spot[0], spot[1], 3):
                return True
        return False


def _track(world, heading, through, margin=30.0):
    """A way across the meadow along ``heading`` through ``through``: (where
    it comes in, just beyond the edge, and the direction)."""
    ux, uy = math.cos(heading), math.sin(heading)
    back = []
    for p, u, lo, hi in ((through[0], ux, -margin, world.width + margin),
                         (through[1], uy, -margin, world.height + margin)):
        if u > 1e-6:
            back.append((p - lo) / u)
        elif u < -1e-6:
            back.append((p - hi) / u)
    t = max(0.0, min(back)) if back else 0.0
    return (through[0] - ux * t, through[1] - uy * t), (ux, uy)


def _aim(world, rng):
    """Where a flock's way across should pass: often where its reflection
    crosses the pond, otherwise anywhere over the meadow."""
    pond = world.terrain.pond
    if pond is not None and rng.random() < 0.6:
        return (pond.cx + rng.uniform(-30, 30), pond.cy - MIRROR_NORTH + rng.uniform(-20, 20))
    return (rng.uniform(world.width * 0.2, world.width * 0.8), rng.uniform(world.height * 0.2, world.height * 0.8))


class StorkKettle(_Overhead):
    """White storks soaring on a thermal: they stream in, circle up on it
    together for a minute or two (the column drifting with the wind), then
    peel off one after another and glide on south."""

    kind = "stork"

    def __init__(self, world, rng, n, heading, circling):
        super().__init__(world, rng)
        self.heading = heading
        centre = _aim(world, rng)
        self.centre = list(centre)
        (sx, sy), (ux, uy) = _track(world, heading, centre)
        self.dir = (ux, uy)
        self.circling = circling
        self.turn = rng.choice((-1, 1))          # storks in one thermal mostly turn the same way
        for i in range(n):
            lag = i * rng.uniform(5, 12)          # strung out along the way in
            self.birds.append([sx - ux * lag + rng.uniform(-14, 14), sy - uy * lag + rng.uniform(-14, 14),
                               heading, rng.random() < 0.45, 0.0])
        # Each bird's own circle: radius, where on it, how fast round.
        self.orbit = [(rng.uniform(16, 62), rng.uniform(0, 2 * math.pi), rng.uniform(0.32, 0.5)) for _ in range(n)]
        self.state = ["in"] * n
        self.leave_at = [circling + rng.uniform(0, circling * 0.6) for _ in range(n)]

    def update(self, dt):
        self.t += dt
        world = self.world
        wind = world.env.wind.drift * 0.06
        self.centre[0] += (wind + self.dir[0] * 1.6) * dt
        self.centre[1] += self.dir[1] * 1.6 * dt
        cx, cy = self.centre
        speed = 34.0
        w, h = world.width, world.height
        out = 0
        for i, bird in enumerate(self.birds):
            x, y = bird[0], bird[1]
            state = self.state[i]
            radius, angle, rate = self.orbit[i]
            if state == "in":
                tx, ty = cx + math.cos(angle) * radius, cy + math.sin(angle) * radius * 0.8
                d = math.hypot(tx - x, ty - y)
                if d < 6:
                    self.state[i] = "circle"
                else:
                    bird[2] = math.atan2(ty - y, tx - x)
                    x += (tx - x) / d * speed * dt
                    y += (ty - y) / d * speed * dt
            elif state == "circle":
                angle += self.turn * rate * dt
                self.orbit[i] = (radius, angle, rate)
                tx, ty = cx + math.cos(angle) * radius, cy + math.sin(angle) * radius * 0.8
                bird[2] = math.atan2(ty - y, tx - x) if math.hypot(tx - x, ty - y) > 0.2 else bird[2]
                x += (tx - x) * min(1.0, dt * 3.0)
                y += (ty - y) * min(1.0, dt * 3.0)
                if self.t > self.leave_at[i]:
                    self.state[i] = "out"
            else:
                bird[2] += clamp(math.atan2(math.sin(self.heading - bird[2]), math.cos(self.heading - bird[2])),
                                 -0.8 * dt, 0.8 * dt)
                x += math.cos(bird[2]) * speed * 1.3 * dt
                y += math.sin(bird[2]) * speed * 1.3 * dt
                if not (-60 < x < w + 60 and -60 < y < h + 60):
                    out += 1
            bird[0], bird[1] = x, y
        if out == len(self.birds) or self.t > 900:
            self.alive = False


class GooseSkein(_Overhead):
    """A skein of geese in a V (or one long slanting line), crossing the
    meadow at a steady wingbeat, each bird in the slipstream of the one
    ahead and the shape always shifting a little."""

    kind = "goose"

    def __init__(self, world, rng, n, heading):
        super().__init__(world, rng)
        self.heading = heading
        (sx, sy), (ux, uy) = _track(world, heading, _aim(world, rng))
        self.pos = [sx, sy]
        self.dir = (ux, uy)
        self.speed = rng.uniform(40, 56)
        self.entered = False
        px, py = -uy, ux                           # to the right of the way
        line = rng.random() < 0.2                  # sometimes not a V but an echelon
        gap = rng.uniform(7.5, 10.0)
        self.slots = []
        for i in range(n):
            rank = (i + 1) // 2
            side = 1 if line else (1 if i % 2 else -1)
            if line:
                rank = i
            back = rank * gap * 0.85 + rng.uniform(-1.5, 1.5)
            across = side * rank * gap * 0.62 + rng.uniform(-1.0, 1.0)
            self.slots.append((-ux * back + px * across, -uy * back + py * across, rng.random() * 6.28))
            self.birds.append([sx, sy, heading, rng.random() < 0.3, rng.random() * 4])

    def update(self, dt):
        self.t += dt
        ux, uy = self.dir
        self.pos[0] += ux * self.speed * dt
        self.pos[1] += uy * self.speed * dt
        w, h = self.world.width, self.world.height
        inside = False
        for (ox, oy, wob), bird in zip(self.slots, self.birds):
            sway = math.sin(self.t * 0.7 + wob) * 1.4
            bird[0] = self.pos[0] + ox + -uy * sway
            bird[1] = self.pos[1] + oy + ux * sway
            bird[4] += dt * 7.0                    # wingbeats
            if -80 < bird[0] < w + 80 and -80 < bird[1] < h + 80:
                inside = True
        self.entered = self.entered or inside
        if (self.entered and not inside) or self.t > 120:
            self.alive = False


# ==========================================================================
# Keeping it all in step with the calendar

class Stories:
    """The stories in one meadow: what stage each is at, and the creatures
    and things that go with it."""

    def __init__(self, world):
        self.world = world
        self.rng = random.Random(world.seed * 31 + 8087)
        self._almanacs = {}
        t = world.terrain
        self.nest = NestSite(world) if t.tree is not None else None
        self.pond = PondLife(world, self.rng) if t.pond is not None and len(t.pond.open_cells) else None
        self.timer = 0.0
        self.year = self.day = None
        self.nest_stage = self.frog_stage = None
        self.passage = {}          # storks and geese: (how strong their passage is today, which way)
        self.sightings = set()     # stories on screen just now (for the notices)
        self.heading = {}          # the way the migrants are going just now: "south" or "north"
        self.scolded = 0.0         # world time a parent last came to scold Mochi
        self._watch = []           # (flock, what she'd be doing, world time): something to look up at
        self._review()

    def almanac(self, year=None):
        year = self.year if year is None else year
        hit = self._almanacs.get(year)
        if hit is None:
            if len(self._almanacs) > 4:
                self._almanacs.clear()
            hit = Almanac(self.world.seed, year)
            self._almanacs[year] = hit
        return hit

    # --- the calendar -------------------------------------------------------

    def _review(self):
        """Once a second: where each story is, and what should be about."""
        world = self.world
        env = world.env
        self.year, self.day = story_day(env.clock.moment, env.sky.lat)
        almanac = self.almanac()
        nesting = almanac.nest
        self.nest_stage = nesting.stage(self.day) if nesting is not None else None
        self.frog_stage = almanac.frogs.stage(self.day)
        self.passage = {"storks": almanac.storks.strength(self.day), "geese": almanac.geese.strength(self.day)}
        if self.nest is not None:
            self._dress_nest(nesting)
        if self.pond is not None:
            self.pond.place(almanac)
            stage = self.frog_stage
            self.pond.set_stage(stage.name if stage else None, stage.progress(self.day) if stage else 0.0)
        self._tidy()
        self._update_sightings()

    def stage_of(self, story):
        """(stage name, progress) of "nest" or "frogs" now, or (None, 0)."""
        stage = self.nest_stage if story == "nest" else self.frog_stage
        return (stage.name, stage.progress(self.day)) if stage is not None else (None, 0.0)

    def _dress_nest(self, nesting):
        """What the nest looks like now."""
        nest = self.nest
        day = self.day
        if nesting is None or not nesting.present(day):
            nest.look = None
            nest.hen_on = False
            return
        stage = self.nest_stage
        name = stage.name if stage else "empty"
        if name == "building":
            nest.look = f"build{1 + min(2, int(stage.progress(day) * 3))}"
            return
        if name in ("laying", "sitting"):
            eggs = max(1, nesting.eggs_laid(day))
            nest.look = "hen" if nest.hen_on else f"eggs{eggs}"
            return
        if name == "chicks":
            age_days = day - nesting.hatch
            age = 0 if age_days < 4 else 1 if age_days < 8.5 else 2
            n = nesting.eggs
            if nest.hen_on:
                nest.look = "hen"
            elif nest.feeding > 0:
                nest.look = f"gape{n}_{age}"
            else:
                nest.look = f"chicks{n}_{age}"
            return
        nest.look = "empty"
        nest.hen_on = False

    def _tidy(self):
        """Send off whatever no longer fits the stage (after a jump in time,
        or the end of the fledglings' weeks)."""
        world = self.world
        stage = self.nest_stage.name if self.nest_stage else None
        for e in world.entities:
            if e.kind == "fledgling" and stage != "fledglings":
                e.go_to_roost()
            elif e.kind == "froglet" and (self.frog_stage is None or self.frog_stage.name != "froglets"):
                e.leave()

    def _update_sightings(self):
        """What a notice could name now: only things you can actually see."""
        world = self.world
        env = world.env
        seen = set()
        light = env.sun > 0.3
        nest = self.nest
        stage = self.nest_stage.name if self.nest_stage else None
        if nest is not None and nest.showing and light:
            if stage == "building" and any(e.kind == "blackbird" for e in world.entities):
                seen.add("building")
            if stage in ("laying", "sitting") and nest.hen_on:
                seen.add("sitting")
            if stage == "chicks" and nest.look and nest.look.startswith("gape"):
                seen.add("chicks")
        if light and any(e.kind == "fledgling" and not e.hidden for e in world.entities):
            seen.add("fledglings")
        pond = self.pond
        if pond is not None and light and not env.frozen:
            if pond.spawn_look is not None and pond.clumps:
                seen.add("frogspawn")
            if pond.stage == "tadpoles" and pond.tadpoles and pond.progress > 0.03:
                seen.add("tadpoles")
        if light and any(e.kind == "froglet" and not e.hidden for e in world.entities):
            seen.add("froglets")
        for flock in world.overhead:
            if isinstance(flock, StorkKettle) and flock.over_meadow:
                seen.add("storks")
            elif isinstance(flock, GooseSkein) and flock.over_meadow:
                seen.add("geese")
        self.sightings = seen

    # --- what comes and goes ------------------------------------------------

    def rate(self, per_hour):
        """Chance in a second of something that comes ``per_hour`` times an
        hour of meadow time: in a time-lapse the stories keep pace with the
        clock, up to a point."""
        speed = clamp(self.world.env.clock.speed, 1.0, RATE_CAP)
        return per_hour / 3600.0 * speed

    def update(self, dt):
        world = self.world
        self.timer -= dt
        if self.timer <= 0:
            self.timer = 1.0
            self._review()
        if self.nest is not None:
            self.nest.update(dt)
            if self.nest.dirty:
                self.nest.dirty = False
                self._dress_nest(self.almanac().nest)
        if self.pond is not None:
            self.pond.update(dt)
        self._watch_the_sky()
        if world.events.hushed:
            return             # something legendary is coming: everything holds its breath
        self._nest_life(dt)
        self._froglets(dt)
        self._migrants(dt)

    def _daylight(self):
        """0..1: how much of a working day it is for a bird."""
        env = self.world.env
        return clamp((env.sun - 0.12) / 0.3, 0.0, 1.0) * (1.0 - clamp((env.rain - 0.3) / 0.4, 0.0, 1.0))

    def _nest_life(self, dt):
        from .entities.seasonal import Blackbird, Fledgling
        nest = self.nest
        stage = self.nest_stage
        if nest is None or stage is None:
            return
        world = self.world
        rng = self.rng
        name = stage.name
        day = self.day
        nesting = self.almanac().nest
        light = self._daylight()
        parents = [e for e in world.entities if e.kind == "blackbird"]
        busy = {e.hen for e in parents}
        # The hen sits through the night on her eggs and her young chicks,
        # and in the day in spells with breaks between.
        brood_night = name in ("laying", "sitting") or (name == "chicks" and day - nesting.hatch < 7)
        if light < 0.2:
            if brood_night and not any(e.hen for e in parents):
                nest.hen_on = True
            for e in parents:
                e.go_home()
            for e in world.entities:
                if e.kind == "fledgling":
                    e.go_to_roost()             # tucked into a bush for the night
            return
        if name == "laying" and nest.hen_on and world.time > nest.hen_until:
            nest.hen_on = False             # laid this morning's egg: off she goes
            self._spawn_hen_off(Blackbird)
        if name == "sitting":
            if nest.hen_on and world.time > nest.hen_until:
                self._spawn_hen_off(Blackbird)
            elif not nest.hen_on and True not in busy and world.time > nest.hen_until:
                world.entities.append(Blackbird(world, self, True, "return", rng))
                nest.hen_until = world.time + 600.0          # (until she's back on)
        if name == "chicks" and nest.hen_on and world.time > nest.hen_until:
            self._spawn_hen_off(Blackbird, then="feed")
        if name == "building" and len(parents) < 2 and rng.random() < self.rate(NEST["building_trips"]) * light * dt:
            hen = rng.random() < 0.75 and True not in busy
            world.entities.append(Blackbird(world, self, hen, "build", rng))
        if name == "chicks" and not nest.hen_on and len(parents) < 2:
            lo, hi = NEST["feeding_visits"]
            per_hour = lo + (hi - lo) * stage.progress(day)
            if rng.random() < self.rate(per_hour) * light * dt:
                hen = (True not in busy) if (True in busy) != (False in busy) else rng.random() < 0.5
                world.entities.append(Blackbird(world, self, hen, "feed", rng))
        if name == "fledglings":
            self._fledglings(Fledgling, stage.progress(day), light, dt)
            young = [e for e in world.entities if e.kind == "fledgling" and not e.hidden]
            if young and len(parents) < 2 and rng.random() < self.rate(NEST["fledgling_feeds"]) * light * dt:
                hen = rng.random() < 0.4
                world.entities.append(Blackbird(world, self, hen, "feed_young", rng, young=rng.choice(young)))
        self._scolding(parents, name, Blackbird)

    def _spawn_hen_off(self, cls, then="break"):
        world = self.world
        nest = self.nest
        nest.hen_on = False
        nest.dirty = True
        nest.hen_until = world.time + sample(self.rng, NEST["hen_break"]) * 60.0
        world.entities.append(cls(world, self, True, then, self.rng, at_nest=True))

    def hen_settles(self):
        """She's back on the nest: sitting until her next break."""
        nest = self.nest
        nest.hen_on = True
        nest.dirty = True
        stage = self.nest_stage.name if self.nest_stage else None
        if stage == "laying":
            nest.hen_until = self.world.time + self.rng.uniform(600, 1500)     # she lays, and sits a while
        elif stage == "chicks":
            nest.hen_until = self.world.time + self.rng.uniform(240, 600)      # brooding the little ones
        else:
            nest.hen_until = self.world.time + sample(self.rng, NEST["hen_sits"]) * 60.0

    def _fledglings(self, cls, progress, light, dt):
        """The young out and about by day (fewer as they grow independent
        and wander off), tucked away at night."""
        world = self.world
        nest = self.nest
        nesting = self.almanac().nest
        young = [e for e in world.entities if e.kind == "fledgling"]
        want = 0 if light < 0.3 else max(1, round(min(3, nesting.eggs) * (1.0 - 0.6 * progress)))
        if len(young) < want and self.rng.random() < self.rate(40) * dt:
            first_day = self.day - nesting.fledge < 0.4
            world.entities.append(cls(world, self, self.rng, from_nest=first_day and nest is not None))
        elif len(young) > want:
            young[-1].go_to_roost()

    def _scolding(self, parents, stage, cls):
        """A cat near the nest or the young gets told off: a parent comes
        and scolds her from a safe distance, tail flicking."""
        world = self.world
        cat = world.cat
        if cat.posture == "sleep" or world.time - self.scolded < 8.0:
            return
        reach = NEST["scold_distance"]
        near = False
        if stage in ("sitting", "chicks") and self.nest is not None:
            fx, fy = self.nest.foot
            near = math.hypot(cat.x - fx, cat.y - fy) < reach * 0.8
        if stage == "fledglings":       # (the parents know where their young are hiding, too)
            near = any(e.kind == "fledgling" and e.state != "roost" and cat.distance_to(e) < reach
                       for e in world.entities)
        if not near:
            return
        if any(getattr(e, "scolding", None) is cat for e in parents):
            return
        self.scolded = world.time
        free = [e for e in parents if e.can_scold]
        if free:
            free[0].scold(cat)
        elif self.rng.random() < 0.6:
            hen = not (stage == "sitting" and self.nest.hen_on) and self.rng.random() < 0.5
            world.entities.append(cls(world, self, hen, "scold", self.rng))

    def _froglets(self, dt):
        from .entities.seasonal import Froglet
        stage = self.frog_stage
        if stage is None or stage.name != "froglets" or self.pond is None:
            return
        world = self.world
        env = world.env
        if env.temperature < 8 or env.frozen:
            return
        p = stage.progress(self.day)
        busy = math.sin(math.pi * p) ** 0.7                        # a few days building to the height of it
        evening = peaks(env.clock.standard_hour, {"peak": 20.0, "width": 2.5})
        boost = 0.35 + 0.65 * max(evening, clamp(env.rain * 3, 0, 1), world.director.wet)
        have = sum(1 for e in world.entities if e.kind == "froglet")
        if have < FROGS["froglets_at_once"] and self.rng.random() < self.rate(FROGS["froglets_per_hour"]) * busy * boost * dt:
            world.entities.append(Froglet(world, self.rng))

    def _migrants(self, dt):
        world = self.world
        env = world.env
        storks, geese = self.passage["storks"], self.passage["geese"]
        if not storks[0] and not geese[0]:
            return
        hour = env.clock.standard_hour
        flocks = [f for f in world.overhead if isinstance(f, (StorkKettle, GooseSkein))]
        if len(flocks) >= 2:
            return
        # Storks need thermals: sun, little cloud, no rain, not much wind.
        strength, way = storks
        if strength > 0.02 and env.sun > 0.5 and env.rain < 0.05 and env.weather.cloud < 0.7 \
                and env.wind.strength < 0.75:
            per_hour = STORKS["kettles_per_hour"] * min(1.0, strength) * peaks(hour, STORKS["hours"])
            if not any(isinstance(f, StorkKettle) for f in flocks) and self.rng.random() < self.rate(per_hour) * dt:
                n = max(4, int(count(self.rng, STORKS["kettle"]) * min(1.4, 0.4 + strength)))
                heading = HEADINGS["storks"] + (0.0 if way == "south" else math.pi) + self.rng.uniform(-0.3, 0.3)
                flock = StorkKettle(world, self.rng, n, heading, sample(self.rng, STORKS["circling"]))
                world.overhead.append(flock)
                self.heading["storks"] = way
                self._look_up(flock, "watching storks circling high overhead")
        strength, way = geese
        if strength > 0.02 and env.rain < 0.4:
            per_hour = GEESE["skeins_per_hour"] * min(1.0, strength) * peaks(hour, GEESE["hours"])
            if self.rng.random() < self.rate(per_hour) * dt:
                n = max(3, int(count(self.rng, GEESE["skein"]) * min(1.3, 0.5 + strength)))
                heading = HEADINGS["geese"] + (0.0 if way == "south" else math.pi) + self.rng.uniform(-0.25, 0.25)
                flock = GooseSkein(world, self.rng, n, heading)
                world.overhead.append(flock)
                self.heading["geese"] = way
                self._look_up(flock, "watching geese fly over")

    def _look_up(self, flock, label):
        """Mochi may stop and look up after them, once they're over her."""
        if self.rng.random() < 0.55:
            self._watch.append((flock, label, self.world.time + self.rng.uniform(2.0, 6.0)))

    def _watch_the_sky(self):
        world = self.world
        for item in list(self._watch):
            flock, label, at = item
            if not flock.alive:
                self._watch.remove(item)
            elif world.time >= at and flock.over_meadow:
                self._watch.remove(item)
                cat = world.cat
                if cat.posture != "sleep" and cat._cooldown_ok("look_up"):
                    cat.attend("look_up", cat.act_look_up(flock, label))

    def nest_watchable(self):
        """Something going on up at the nest that a curious cat might sit and
        watch."""
        nest = self.nest
        stage = self.nest_stage.name if self.nest_stage else None
        return (nest is not None and nest.look is not None and stage in ("building", "sitting", "chicks")
                and self._daylight() > 0.5)

    # --- for the info panel and the testing badge -------------------------------

    def describe(self):
        """What the stories are doing, in a few words each."""
        out = []
        nesting = self.almanac().nest
        stage = self.nest_stage
        if stage is not None and self.nest is not None:
            day = self.day
            if stage.name == "building":
                out.append("blackbirds building a nest")
            elif stage.name == "laying":
                n = nesting.eggs_laid(day)
                out.append(f"{n} blackbird egg{'s' if n != 1 else ''} in the nest")
            elif stage.name == "sitting":
                out.append(f"the blackbird sitting, day {int(day - nesting.sit) + 1}")
            elif stage.name == "chicks":
                out.append(f"blackbird chicks, {int(day - nesting.hatch) + 1} days old")
            elif stage.name == "fledglings":
                out.append("young blackbirds about")
        stage = self.frog_stage
        if stage is not None and self.pond is not None:
            out.append({"spawn": "frogspawn in the pond", "tadpoles": "tadpoles in the pond",
                        "froglets": "tiny frogs leaving the pond"}[stage.name])
        for passage in (self.almanac().storks, self.almanac().geese):
            strength, way = passage.strength(self.day)
            if strength > 0.15:
                out.append(f"{passage.kind} heading {way}")
        return out

    def next_change(self):
        """(days from now, story, stage) of the next stage to begin, or None."""
        for year in (self.year, self.year + 1):
            for day, story, stage in self.almanac(year).changes():
                ahead = day - self.day + (DAYS if year > self.year else 0)
                if ahead > 0.01:
                    return ahead, story, stage
        return None

