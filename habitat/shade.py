"""The old tree's shadow, cast by the real sun (or a bright moon).

The meadow is seen from above and a little to the south, so north is up
and a height of ``h`` pixels stands ``h`` pixels tall on screen, while
ground running north-south is foreshortened by ``SQUASH``.  The crown is
a ball of leaves ``CROWN_HEIGHT`` above the ground; its shadow is an
ellipse thrown away from the light, stretched as the light gets low, with
a few sun-flecks where light slips through the leaves.  The trunk's
shadow joins it to the tree's foot.

The shadow fades when the light isn't direct (cloud, rain, a cloud
passing over the sun) and is redrawn only when it has moved a pixel or
changed in strength, so it costs one small blit a frame.
"""

import math

import numpy as np
import pygame

from .settings import SETTINGS
from .util import clamp, dither_mask, smoothstep

SQUASH = 0.6
CROWN_HEIGHT = 42.0
MAX_LENGTH = 150.0         # the longest shadow worth drawing (art pixels)
TINT = (164, 172, 196)     # multiply colour of full shade: a cool blue-grey
LEVELS = 12                # strengths the shadow is redrawn at
SHADE = SETTINGS["shade"]


def cast(alt, az, height):
    """Where the shadow of a point ``height`` above the ground falls,
    relative to its foot: (dx, dy) on screen.  ``az`` runs from north
    through east, in degrees."""
    length = min(MAX_LENGTH, height / math.tan(math.radians(max(alt, 1.0))))
    a = math.radians(az)
    return -math.sin(a) * length, math.cos(a) * length * SQUASH


class TreeShade:
    def __init__(self, world):
        self.world = world
        self.tree = world.terrain.tree
        self.strength = 0.0      # 0..1 how dark the shade is now
        self.ellipse = None      # (cx, cy, ux, uy, major, minor): centre, light direction, radii (ground units)
        self._key = None
        self.surface = None
        self.origin = (0, 0)
        if self.tree is not None:
            rng = np.random.default_rng(world.terrain.seed * 13 + 5)
            self._flecks = rng.uniform(-0.75, 0.75, size=(9, 2))
            self._lit = self._tree_pixels()

    def _tree_pixels(self):
        """Where the crown and trunk themselves are on screen: they stand in
        the light, so their own shadow never darkens them."""
        w, h = self.world.width, self.world.height
        mask = np.zeros((h, w), dtype=bool)
        for prop in (self.tree.canopy, self.tree.trunk):
            img = prop.frames[0]
            alpha = pygame.surfarray.array_alpha(img).swapaxes(0, 1) > 0
            x0 = int(round(prop.x - prop.anchor[0]))
            y0 = int(round(prop.y - prop.anchor[1]))
            ih, iw = alpha.shape
            sx0, sy0 = max(0, -x0), max(0, -y0)
            dx0, dy0 = max(0, x0), max(0, y0)
            dx1, dy1 = min(w, x0 + iw), min(h, y0 + ih)
            if dx0 < dx1 and dy0 < dy1:
                mask[dy0:dy1, dx0:dx1] |= alpha[sy0:sy0 + dy1 - dy0, sx0:sx0 + dx1 - dx0]
        return mask

    # --- where the light comes from -------------------------------------

    def _light(self):
        """(alt, az, how direct and bright the light is 0..1)."""
        env = self.world.env
        sky = env.sky
        weather = env.weather
        overcast = clamp(1.0 - 1.25 * weather.cloud, 0.0, 1.0) * clamp(1.0 - 4.0 * weather.rain, 0.0, 1.0)
        if sky.sun_alt > -1.0:
            return sky.sun_alt, sky.sun_az, smoothstep(clamp((sky.sun_alt - 2.0) / 12.0, 0.0, 1.0)) * overcast
        moon = env.moonlight * SHADE["moon_shadow"]
        return sky.moon_alt, sky.moon_az, smoothstep(clamp((sky.moon_alt - 4.0) / 14.0, 0.0, 1.0)) * moon * overcast

    def _cloud_over(self, x, y):
        """0..1: a cloud's shadow at (x, y) (the sun is behind a cloud)."""
        darkest = 255
        for cx, cy, shape, _ in self.world.env.clouds.clouds:
            ix, iy = int(x - cx), int(y - cy)
            if 0 <= ix < shape.get_width() and 0 <= iy < shape.get_height():
                darkest = min(darkest, shape.get_at((ix, iy))[0])
        return clamp((255 - darkest) / 40.0, 0.0, 1.0)

    def update(self, dt):
        tree = self.tree
        if tree is None:
            return
        alt, az, direct = self._light()
        if direct <= 0.0:
            self.strength = max(0.0, self.strength - dt / 4.0)
            if self.strength == 0.0:
                self.ellipse = None
            return
        dx, dy = cast(alt, az, CROWN_HEIGHT)
        cx, cy = tree.x + dx, tree.y + dy
        direct *= 1.0 - 0.85 * self._cloud_over(cx, cy)
        # Light fades over a few seconds as a cloud's edge slides across the sun.
        rate = dt / 3.0
        self.strength += clamp(direct - self.strength, -rate, rate)
        a = math.radians(az)
        ux, uy = -math.sin(a), math.cos(a)                       # away from the light, ground units (north up = -y)
        minor = tree.rx * 0.8
        major = min(minor / math.sin(math.radians(max(alt, 4.0))), minor * 3.0)
        self.ellipse = (cx, cy, ux, uy, major, minor)

    # --- questions Mochi asks ---------------------------------------------

    def covers(self, x, y, margin=0.0):
        """Is (x, y) in the tree's shade (``margin`` > 0 asks for well inside)?"""
        if self.ellipse is None or self.strength < 0.25:
            return False
        return self._q(x, y) < (1.0 - margin) ** 2

    def _q(self, x, y):
        cx, cy, ux, uy, major, minor = self.ellipse
        gx, gn = x - cx, -(y - cy) / SQUASH                      # ground: east, north
        along, across = gx * ux - gn * uy, gx * uy + gn * ux     # (ux, -uy) is away from the light
        return (along / major) ** 2 + (across / minor) ** 2

    def sunlit(self, x, y):
        """0..1: direct sunshine at (x, y), out of the tree's and the clouds' shade."""
        env = self.world.env
        sky = env.sky
        if sky.sun_alt < 3.0:
            return 0.0
        _, _, direct = self._light()
        if self.covers(x, y):
            return 0.0
        return direct * (1.0 - self._cloud_over(x, y))

    # --- drawing ----------------------------------------------------------

    def draw(self, light):
        """Multiply the shadow into the light map."""
        if self.ellipse is None or self.strength < 0.03:
            return
        cx, cy, ux, uy, major, minor = self.ellipse
        level = int(round(self.strength * LEVELS))
        key = (round(cx), round(cy), round(ux * 40), round(uy * 40), round(major), level)
        if key != self._key:
            self._key = key
            self._redraw(level / LEVELS)
        if self.surface is not None:
            light.blit(self.surface, self.origin, special_flags=pygame.BLEND_MULT)

    def _redraw(self, strength):
        tree = self.tree
        cx, cy, ux, uy, major, minor = self.ellipse
        reach_x = abs(ux) * major + abs(uy) * minor
        reach_y = (abs(uy) * major + abs(ux) * minor) * SQUASH
        x0 = int(min(cx - reach_x, tree.x) - 3)
        x1 = int(max(cx + reach_x, tree.x) + 4)
        y0 = int(min(cy - reach_y, tree.y) - 3)
        y1 = int(max(cy + reach_y, tree.y) + 4)
        w, h = self.world.width, self.world.height
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
        if x0 >= x1 or y0 >= y1:
            self.surface = None
            return
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        gx, gn = xx - cx, -(yy - cy) / SQUASH
        along, across = gx * ux - gn * uy, gx * uy + gn * ux
        q = (along / major) ** 2 + (across / minor) ** 2
        # Sun-flecks: a few gaps in the leaves.
        for fa, fc in self._flecks:
            fq = ((along - fa * major) / (minor * 0.16)) ** 2 + ((across - fc * minor) / (minor * 0.12)) ** 2
            q = np.where((fq < 1.0) & (q < 0.7), 0.8, q)
        # The trunk's shadow, from the foot of the tree to the crown's.
        tx, ty = cx - tree.x, cy - tree.y
        tl = max(1.0, math.hypot(tx, ty))
        px, py = xx - tree.x, yy - tree.y
        t = np.clip((px * tx + py * ty) / (tl * tl), 0.0, 1.0)
        off = np.hypot(px - t * tx, py - t * ty)
        trunk = (off < 1.6) & (t < 0.85)
        d = dither_mask(h, w)[y0:y1, x0:x1]
        dark = (q < 0.62) | trunk
        rim = (q >= 0.62) & (q < 1.0) & (d < 0.5)
        k = np.ones(q.shape, dtype=np.float32)
        k[rim] = 0.5
        k[dark] = 1.0
        k[~(dark | rim)] = 0.0
        k[self._lit[y0:y1, x0:x1]] = 0.0
        k *= strength * SHADE["darkness"]
        rgb = np.empty(q.shape + (3,), dtype=np.uint8)
        for i, c in enumerate(TINT):
            rgb[..., i] = (255 - (255 - c) * k).astype(np.uint8)
        self.surface = pygame.surfarray.make_surface(np.ascontiguousarray(rgb.swapaxes(0, 1)))
        self.origin = (x0, y0)
