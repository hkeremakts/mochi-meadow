"""Signs of what has happened: paw prints and worn paths.

Prints are left in snow (they fill in as more falls, and go with the
thaw) and, for a few steps after a puddle, in mud (it dries).  The deer
and the fox leave theirs in the snow too.  Where Mochi walks often the
grass wears thin, and grows back over a couple of days when she stops;
the wear is kept in the journal, so paths build up across runs.

Nothing here is drawn every frame: the renderer paints the marks into
the ground image when they change (a few times a second at most while
she's walking in snow, every few seconds as they fade).
"""

import base64
import datetime
import math
import zlib

import numpy as np
import pygame

from .settings import SETTINGS
from .util import dither_mask

MARKS = SETTINGS["marks"]
CELL = 2                     # art pixels per cell of the wear grid
MAX_PRINTS = 600
REFRESH = 8.0                # seconds between repaints while prints fade
SNOW_SHADE = np.array([0.70, 0.76, 0.90], dtype=np.float32)   # a print in snow: a blue-grey dip
MUD = np.array([84, 64, 46], dtype=np.float32)
DIRT = np.array([132, 118, 80], dtype=np.float32)            # trampled grass and bare earth
# Stride between footfalls (art pixels) and the pixels of one print.
FEET = {"cat": (5.5, ((0, 0), (1, 0))), "fox": (6.5, ((0, 0), (1, 0))), "deer": (10.0, ((0, 0), (0, 1)))}


class Print:
    __slots__ = ("x", "y", "kind", "foot", "strength")

    def __init__(self, x, y, kind, foot, strength):
        self.x, self.y, self.kind, self.foot, self.strength = x, y, kind, foot, strength


class Marks:
    def __init__(self, world, journal=None):
        self.world = world
        self.journal = journal
        self.prints = []
        gw, gh = (world.width + CELL - 1) // CELL, (world.height + CELL - 1) // CELL
        self.wear = np.zeros((gh, gw), dtype=np.float32)
        self.version = 0
        self._feet = {}          # id(entity) -> [x, y, travelled, side, muddy]
        self._since = 0.0        # seconds since the last fade step
        self._wear_shown = 0.0   # wear total when last painted
        self.load()

    # --- simulation -------------------------------------------------------

    def update(self, dt):
        world = self.world
        env = world.env
        terrain = world.terrain
        snowy = env.snow_cover > 0.3
        seen = set()
        for e in world.entities:
            kind = getattr(e, "TRACK", None)
            if kind is None or not e.alive or e.z > 0.5 or getattr(e, "hidden", False):
                continue
            key = e.serial if hasattr(e, "serial") else ("id", id(e))
            seen.add(key)
            feet = self._feet.get(key)
            if feet is None:
                self._feet[key] = [e.x, e.y, 0.0, 1, 0]
                continue
            dx, dy = e.x - feet[0], e.y - feet[1]
            feet[0], feet[1] = e.x, e.y
            step = math.hypot(dx, dy)
            if step <= 0.0 or step > 30.0:        # standing still, or put somewhere new
                continue
            if kind == "cat" and self._in_puddle(e.x, e.y):
                feet[4] = MARKS["muddy_steps"]
            feet[2] += step
            stride, foot = FEET[kind]
            if feet[2] < stride:
                continue
            feet[2] -= stride
            feet[3] = -feet[3]
            # Left and right feet a little either side of the line of travel.
            x = e.x - dy / step * 1.2 * feet[3]
            y = e.y + dx / step * 0.8 * feet[3]
            if not terrain.walkable(x, y):
                continue
            if kind == "cat":
                self._tread(x, y)
            if snowy and not terrain.under_roof(x, y):
                self._add(Print(x, y, "snow", foot, 1.0))
            elif feet[4] > 0:
                self._add(Print(x, y, "mud", foot, 0.3 + 0.7 * feet[4] / MARKS["muddy_steps"]))
                feet[4] -= 1
        for key in [k for k in self._feet if k not in seen]:
            del self._feet[key]
        self._since += dt
        if self._since >= REFRESH:
            self._fade(self._since * env.clock.speed)
            self._since = 0.0

    def _in_puddle(self, x, y):
        for fx in self.world.effects:
            for p in getattr(fx, "items", ()):
                if getattr(fx, "PUDDLES", False) and ((x - p.x) / (p.rx + 3)) ** 2 + ((y - p.y) / (p.ry + 2)) ** 2 < 1.0:
                    return True
        return False

    def _add(self, p):
        self.prints.append(p)
        if len(self.prints) > MAX_PRINTS:
            del self.prints[:len(self.prints) - MAX_PRINTS]
        self.version += 1

    def _tread(self, x, y):
        """One footfall wears the grass a little, under and around the paw."""
        gx, gy = int(x) // CELL, int(y) // CELL
        h, w = self.wear.shape
        step = MARKS["wear_step"]
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                cx, cy = gx + ox, gy + oy
                if 0 <= cx < w and 0 <= cy < h:
                    k = step if ox == 0 and oy == 0 else step * 0.4
                    self.wear[cy, cx] += k * (1.0 - self.wear[cy, cx])

    def _fade(self, sim):
        """Prints fill in, dry and melt; worn grass grows back."""
        env = self.world.env
        if self.prints:
            for p in self.prints:
                if p.kind == "snow":
                    if env.snowing:
                        p.strength -= sim * env.rain / MARKS["snow_fills_seconds"]
                    elif env.snow_cover < 0.3:
                        p.strength -= sim / 30.0
                    else:
                        p.strength -= sim * (1.0 + max(0.0, env.temperature)) / MARKS["snow_print_seconds"]
                else:
                    dry = 1.0 + 2.0 * env.sun * (1.0 - env.weather.cloud)
                    p.strength -= sim * (dry / MARKS["mud_dries_seconds"] + env.rain / 20.0)
            self.prints = [p for p in self.prints if p.strength > 0.05]
            self.version += 1
        self.wear *= math.exp(-sim / (MARKS["grass_recovers_hours"] * 3600.0))
        total = float(self.wear.sum())
        if abs(total - self._wear_shown) > 2.0:
            self._wear_shown = total
            self.version += 1

    # --- painting -----------------------------------------------------------

    def paint(self, ground):
        """The ground surface with the marks on it (``ground`` itself if
        there's nothing to show)."""
        env = self.world.env
        worn = env.snow_cover < 0.3 and float(self.wear.max()) > MARKS["wear_shows"]
        if not worn and not self.prints:
            return ground
        rgb = pygame.surfarray.array3d(ground).swapaxes(0, 1).astype(np.float32)
        h, w = rgb.shape[:2]
        if worn:
            g = self.wear
            soft = g.copy()                                   # a path is a little wider than the paws
            soft[1:] += g[:-1] * 0.5
            soft[:-1] += g[1:] * 0.5
            soft[:, 1:] += g[:, :-1] * 0.5
            soft[:, :-1] += g[:, 1:] * 0.5
            soft /= 1.6
            wear = np.repeat(np.repeat(soft, CELL, axis=0), CELL, axis=1)[:h, :w]
            v = np.clip((wear - MARKS["wear_shows"]) / (1.0 - MARKS["wear_shows"]), 0.0, 1.0)
            d = dither_mask(h, w)
            trodden = (d < v * 1.5)[..., None]               # flattened grass, paler
            bare = (d < v * 1.5 - 0.6)[..., None]            # worn through to earth
            rgb = np.where(trodden, rgb * 0.62 + DIRT * 0.38, rgb)
            rgb = np.where(bare, rgb * 0.45 + DIRT * 0.55, rgb)
        for p in self.prints:
            for ox, oy in p.foot:
                x, y = int(p.x) + ox, int(p.y) + oy
                if 0 <= x < w and 0 <= y < h:
                    if p.kind == "snow":
                        rgb[y, x] *= 1.0 - p.strength * (1.0 - SNOW_SHADE)
                    else:
                        k = 0.85 * p.strength
                        rgb[y, x] = rgb[y, x] * (1 - k) + MUD * k
        out = np.clip(rgb, 0, 255).astype(np.uint8)
        return pygame.surfarray.make_surface(np.ascontiguousarray(out.swapaxes(0, 1)))

    # --- remembering paths --------------------------------------------------

    def save(self):
        if self.journal is None:
            return
        h, w = self.wear.shape
        packed = base64.b64encode(zlib.compress((self.wear * 255).astype(np.uint8).tobytes(), 9)).decode("ascii")
        self.journal.notes["paths"] = {"seed": self.world.seed, "size": [w, h], "wear": packed,
                                       "saved": self.world.env.clock.moment.isoformat(timespec="minutes")}

    def load(self):
        data = self.journal.notes.get("paths") if self.journal is not None else None
        if not isinstance(data, dict):
            return
        h, w = self.wear.shape
        if data.get("seed") != self.world.seed or data.get("size") != [w, h]:
            return              # a different meadow, or a different screen
        try:
            raw = zlib.decompress(base64.b64decode(data["wear"]))
            wear = np.frombuffer(raw, dtype=np.uint8).reshape(h, w).astype(np.float32) / 255.0
            saved = datetime.datetime.fromisoformat(data["saved"])
        except (KeyError, ValueError, TypeError, zlib.error):
            return
        away = max(0.0, (self.world.env.clock.moment - saved).total_seconds())
        self.wear = wear * math.exp(-away / (MARKS["grass_recovers_hours"] * 3600.0))
        self._wear_shown = float(self.wear.sum())
