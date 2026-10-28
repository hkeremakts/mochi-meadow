"""A neighbour's cat: a ginger tom who drops by now and then.

He is Mochi's own puppet in a different coat (her frames recoloured on
first use), with a short script instead of a mind: walk in, find Mochi,
touch noses, and then whatever the mood brings (a sit together in the sun,
a game of chase, or a hiss), and wander off again.
"""

import math

import numpy as np
import pygame

from .. import cat_art
from ..chance import sample
from ..personality import BEST_FRIENDS
from ..settings import SETTINGS
from .cat import UNREACHABLE, Cat, cat_library

# Mochi's palette index -> the visitor's colour.
GINGER = {
    cat_art.OUT: (66, 34, 24),
    cat_art.DEEP: (128, 64, 34),
    cat_art.DARK: (168, 90, 42),
    cat_art.BASE: (212, 126, 58),
    cat_art.LIGHT: (236, 164, 90),
    cat_art.CREAM: (242, 228, 206),
    cat_art.CREAM_SH: (210, 188, 160),
    cat_art.PINK: (226, 146, 136),
    cat_art.IRIS: (222, 172, 62),
    cat_art.MARK: (212, 126, 58),     # Mochi's blaze and tail tip are hers: on him, plain coat
}


STAYS = SETTINGS["effects"]["stays"]


class Recoloured(dict):
    """A view of a frame library in another palette, made frame by frame
    as frames are first asked for (no pause when he arrives)."""

    def __init__(self, source, mapping):
        super().__init__()
        self.source = source
        self.lut = {cat_art.PALETTE[i]: c for i, c in mapping.items()}

    def __contains__(self, key):
        return key in self.source

    def get(self, key, default=None):
        return self[key] if key in self.source else default

    def __missing__(self, key):
        frames = [self._recolour(f) for f in self.source[key]]
        self[key] = frames
        return frames

    def _recolour(self, frame):
        out = frame.copy()
        rgb = pygame.surfarray.pixels3d(out)     # a view: writes go to the surface
        keys = (rgb[..., 0].astype(np.int32) << 16) | (rgb[..., 1].astype(np.int32) << 8) | rgb[..., 2]
        for src, dst in self.lut.items():
            rgb[keys == ((src[0] << 16) | (src[1] << 8) | src[2])] = dst
        del rgb
        return out


_GINGER = []


def ginger_library():
    if not _GINGER:
        _GINGER.append(Recoloured(cat_library(), GINGER))
    return _GINGER[0]


class VisitorCat(Cat):
    kind = "visitor"

    def __init__(self, world, side=None):
        rng = world.rng
        t = world.terrain
        side = side or rng.choice((-1, 1))
        # The first open ground in from the chosen edge, on a row joined
        # to wherever Mochi is.
        self.entry = None
        for _ in range(40):
            cand = rng.uniform(world.height * 0.3, world.height * 0.9)
            xs = range(2, world.width // 3) if side < 0 else range(world.width - 3, world.width * 2 // 3, -1)
            x = next((x for x in xs if t.walkable(x, cand)), None)
            if x is not None and t.regions.connected((x, cand), (world.cat.x, world.cat.y)):
                self.entry = (float(x), cand)
                break
        edge_x, y = self.entry if self.entry else (0.0, world.height / 2)
        start_x = -26.0 if side < 0 else world.width + 26.0
        super().__init__(world, start_x, y if y is not None else world.height / 2, name="the ginger cat")
        self.lib = ginger_library()
        self.side = side
        self.phase = "arriving"
        self.outcome = None
        self.posture = "stand"
        self.facing = "right" if side < 0 else "left"
        self.pace = rng.uniform(0.95, 1.1)
        self.idle_pose()
        self._start("visit", self.act_visit(), interruptible=False)

    # He has his own script: no needs-driven choices, no hunting.
    def _perceive(self):
        pass

    def _choose(self):
        return "visit", self.act_visit()

    def _update_needs(self, dt):
        pass

    def act_visit(self):
        world = self.world
        mochi = world.cat
        rng = self.rng
        if self.entry is None:
            self.alive = False
            return
        self.label = "padding in"
        # The first steps are off-screen, where there is no ground to plan on.
        yield from self.step_to(*self.entry, speed=24.0)
        # Head for Mochi, wherever she wanders; she turns to meet him once
        # she notices him coming.
        called = False
        for _ in range(40):
            d = self.distance_to(mochi)
            if not called and d < 110:
                called = mochi.attend("visitor", mochi.act_greet(self), wake=rng.random() < 0.7)
            if d < 36:
                break
            dx = 29 if self.x < mochi.x else -29
            goal = (mochi.x - dx, mochi.y)
            if not world.terrain.walkable(*goal):
                goal = (mochi.x + dx, mochi.y)
            status = yield from self.go(*goal, gait="walk", max_time=2.0, stop=False)
            if status == UNREACHABLE:
                yield from self.wait(0.5)
        else:
            yield from self.act_leave()
            return
        yield from self.settle()
        if not called:
            mochi.attend("visitor", mochi.act_greet(self), wake=rng.random() < 0.7)
        yield from self.face("right" if mochi.x > self.x else "left")
        self.phase = "greeting"
        self.label = "touching noses with Mochi"
        yield from self.once("sniff_start", fps=8)
        self.show("sniff", fps=5)
        yield from self.wait(rng.uniform(2.0, 3.5))
        self.idle_pose()
        # How it goes depends on Mochi's temper and on how past visits went.
        p = mochi.p
        level = p.friendship("ginger")
        spat = max(0.3, 2.0 - 0.5 * level) * (0.5 + p["bold"]) * (1.5 if p.mood < -0.25 else 1.0)
        weights = (5.0 + 1.5 * max(0, level), 3.0 * p.lean("playful", 0.5, 1.5), spat)
        mood = rng.choices(("friendly", "play", "spat"), weights=weights)[0]
        self.outcome = mood
        self.phase = mood
        if mood == "spat":
            self.label = "backing off"
            yield from self.wait(1.4)          # Mochi hisses
            p.visit("ginger", "spat")
            yield from self.act_leave(gait="trot")
            return
        if mood == "play":
            self.label = "playing chase"
            for _ in range(rng.randint(2, 3)):
                angle = rng.uniform(0, 2 * math.pi)
                gx = self.x + math.cos(angle) * rng.uniform(50, 100)
                gy = self.y + math.sin(angle) * rng.uniform(30, 60)
                if world.terrain.walkable(gx, gy) and world.terrain.regions.connected((self.x, self.y), (gx, gy)):
                    yield from self.go(gx, gy, gait="run")
                    yield from self.face("right" if mochi.x > self.x else "left")
                    yield from self.wait(rng.uniform(0.8, 1.6))
            self.phase = "friendly"
        if p.friendship("ginger") >= BEST_FRIENDS and rng.random() < 0.6:
            # Old friends: a nap side by side.
            self.phase = "snuggle"
            self.label = "napping beside Mochi"
            yield from self.to_posture("sleep", style="curl")
            yield from self.wait(rng.uniform(60, 120))
            yield from self.to_posture("stand")
            self.phase = "friendly"
        self.label = "sitting with Mochi"
        yield from self.to_posture("sit")
        end = world.time + sample(rng, STAYS["ginger_sits"], world.day.spread)
        while world.time < end:
            if rng.random() < self.dt * 0.08:
                yield from self.once("groom", fps=6)
                self.idle_pose()
            yield
        p.visit("ginger", self.outcome)
        self.phase = "leaving"
        yield from self.act_leave()

    def act_leave(self, gait="walk"):
        self.phase = "leaving"
        self.label = "heading home"
        world = self.world
        status = yield from self.go(*self.entry, gait=gait, stop=False)
        if status == UNREACHABLE:
            pass   # strike out straight for the edge from wherever he is
        off = -30 if self.entry[0] < world.width / 2 else world.width + 30
        yield from self.step_to(off, self.y, speed=24.0)
        self.alive = False
