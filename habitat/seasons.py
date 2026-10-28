"""The meadow through the year: fresh green in spring, a dry tint in late
summer, gold and rust in autumn, dun winter grass, flowers that open and
fade, frost, and snow that settles and melts.

The ground and props are drawn once, without a season.  ``Scenery`` makes
a graded copy for the current week, snow depth and frost, and only redoes
it when one of those changes, so seasons cost nothing frame to frame.
"""

import math
import random

import numpy as np
import pygame

from .util import dither_mask, value_noise


def _ramp(p, points):
    """Piecewise-linear value over the year phase (0..1, wrapping)."""
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return float(np.interp(p % 1.0, xs, ys, period=1.0))


def season_weights(p):
    """How strongly each look applies at year phase ``p`` (0 = 1 January in
    the north)."""
    winter = _ramp(p, [(0.0, 1.0), (0.12, 1.0), (0.22, 0.0), (0.90, 0.0), (0.96, 1.0)])
    turn = _ramp(p, [(0.0, 1.0), (0.2, 1.0), (0.24, 0.0), (0.70, 0.0), (0.78, 0.5), (0.85, 1.0)])
    return {
        "spring": _ramp(p, [(0.16, 0.0), (0.25, 1.0), (0.38, 1.0), (0.45, 0.0)]),
        "summer": _ramp(p, [(0.5, 0.0), (0.6, 1.0), (0.7, 0.6), (0.78, 0.0)]),
        "autumn": turn * (1.0 - winter),
        "winter": winter,
        "bloom": _ramp(p, [(0.17, 0.0), (0.30, 1.0), (0.70, 1.0), (0.80, 0.2), (0.86, 0.0)]),
        "litter": turn * (1.0 - 0.7 * winter),
    }


AUTUMN_GRASS = [(40, (58, 54, 32)), (90, (128, 110, 52)), (140, (186, 154, 68))]
AUTUMN_LEAVES = [  # three kinds of shrub: rust, amber, gold
    [(40, (92, 36, 26)), (90, (172, 72, 36)), (150, (226, 132, 58))],
    [(40, (88, 52, 24)), (90, (180, 112, 40)), (150, (232, 172, 70))],
    [(40, (76, 66, 26)), (90, (160, 138, 46)), (150, (220, 196, 84))],
]
WINTER_GRASS = [(40, (56, 60, 54)), (90, (104, 104, 86)), (140, (146, 140, 112))]
SNOW = [(40, (168, 180, 206)), (80, (204, 212, 230)), (125, (230, 236, 246)), (170, (242, 245, 250))]
FROST = np.array([196, 210, 222], dtype=np.float32)
ICE = np.array([150, 176, 196], dtype=np.float32)        # grey-blue: water seen through ice
ICE_CRACK = np.array([226, 236, 244], dtype=np.float32)
LITTER = np.array([(176, 82, 40), (200, 132, 52), (150, 58, 36), (214, 170, 70), (120, 84, 44)], dtype=np.float32)


def _gradient(lum, stops):
    out = np.empty(lum.shape + (3,), dtype=np.float32)
    xs = [x for x, _ in stops]
    for c in range(3):
        out[..., c] = np.interp(lum, xs, [col[c] for _, col in stops])
    return out


def _greenness(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return np.clip((g - np.maximum(r, b)) / 10.0, 0.0, 1.0)


def _lum(rgb):
    return rgb.mean(axis=-1)


def grade_plants(rgb, w, patch, leaves=None):
    """Seasonal colour for green pixels.  ``patch`` (0.6..1.3) varies the
    strength from place to place; ``leaves`` picks an autumn palette for
    shrubs instead of grass."""
    green = _greenness(rgb)[..., None]
    lum = _lum(rgb)
    out = rgb.copy()
    k = patch[..., None] if np.ndim(patch) else patch
    if w["spring"] > 0:
        fresh = rgb * np.array([0.92, 1.1, 0.9], dtype=np.float32) + np.array([0, 6, 0], dtype=np.float32)
        out += (fresh - out) * (0.8 * w["spring"] * green)
    if w["summer"] > 0:
        dry = rgb * np.array([1.15, 1.02, 0.8], dtype=np.float32) + np.array([10, 0, 0], dtype=np.float32)
        out += (dry - out) * np.clip(0.45 * w["summer"] * green * k, 0, 1)
    if w["autumn"] > 0:
        target = _gradient(lum, leaves if leaves is not None else AUTUMN_GRASS)
        strength = 0.9 if leaves is not None else 0.5
        out += (target - out) * np.clip(strength * w["autumn"] * green * k, 0, 1)
    if w["winter"] > 0:
        target = _gradient(lum, WINTER_GRASS)
        strength = 0.45 if leaves is not None else 0.85
        out += (target - out) * np.clip(strength * w["winter"] * green * k, 0, 1)
    return out


def _surface_rgba(surf):
    rgb = pygame.surfarray.array3d(surf).swapaxes(0, 1).astype(np.float32)
    alpha = pygame.surfarray.array_alpha(surf).swapaxes(0, 1)
    return rgb, alpha


def _to_surface(rgb, alpha):
    h, w = alpha.shape
    out = pygame.Surface((w, h), pygame.SRCALPHA, 32)
    pygame.surfarray.pixels3d(out)[...] = np.clip(rgb, 0, 255).astype(np.uint8).swapaxes(0, 1)
    pygame.surfarray.pixels_alpha(out)[...] = alpha.swapaxes(0, 1)
    return out


def snow_caps(rgb, alpha, cover, seed):
    """Snow along the top edges of a sprite: one row once it has settled,
    two in deep snow."""
    if cover < 0.2:
        return rgb
    solid = alpha > 0
    top = solid.copy()
    top[1:] &= ~solid[:-1]
    rng = np.random.default_rng(seed)
    chance = min(1.0, (cover - 0.2) / 0.3)
    cap = top & (rng.random(top.shape) < chance)
    if cover > 0.6:
        second = np.zeros_like(cap)
        second[1:] = cap[:-1] & solid[1:]
        cap |= second & (rng.random(top.shape) < (cover - 0.6) / 0.4)
    out = rgb.copy()
    lum = _lum(rgb)
    snow = _gradient(lum + 50, SNOW)
    out[cap] = snow[cap]
    return out


def snow_on_crown(rgb, alpha, cover, seed):
    """Snow resting on the upper, sunlit side of each clump of leaves."""
    lum = _lum(rgb)
    solid = alpha > 0
    if not solid.any():
        return rgb
    cut = np.quantile(lum[solid], 1.0 - min(0.55, cover * 0.6))
    rng = np.random.default_rng(seed)
    lying = solid & (lum >= cut) & (rng.random(lum.shape) < 0.35 + 0.6 * cover)
    out = rgb.copy()
    out[lying] = _gradient(lum[lying] + 60, SNOW)
    return out


class Scenery:
    """Seasonal versions of the ground and props for a terrain."""

    def __init__(self, terrain):
        self.terrain = terrain
        h, w = terrain.ground_base.shape[:2]
        nrng = np.random.default_rng(terrain.seed + 404)
        # Where the season shows first, and where snow settles first:
        # fixed for this meadow, so changes grow rather than flicker.
        self.patch = 0.6 + 0.7 * value_noise(w, h, 30, nrng)
        # Snow first dusts the grass blade by blade, then fills in, lying
        # deepest in broad drifts.
        drift = value_noise(w, h, 26, nrng) * 0.45 + value_noise(w, h, 7, nrng) * 0.2 + nrng.random((h, w)) * 0.35
        order = np.argsort(drift, axis=None)
        rank = np.empty(drift.size, dtype=np.float32)
        rank[order] = np.linspace(0.0, 1.0, drift.size, dtype=np.float32)
        self.snow_rank = rank.reshape(h, w)
        self.dither = dither_mask(h, w)
        self.frost_rank = nrng.random((h, w)).astype(np.float32)
        self.base = terrain.ground_base.astype(np.float32)
        self.litter = self._litter(nrng)
        self.roof = np.zeros((h, w), dtype=bool)
        tree = terrain.tree
        if tree is not None:
            yy, xx = np.mgrid[0:h, 0:w]
            self.roof = ((xx - tree.roof_cx) / tree.roof_rx) ** 2 + ((yy - tree.roof_cy) / tree.roof_ry) ** 2 < 1.0
        self.cracks = self._ice_cracks()
        self.key = None

    def _ice_cracks(self):
        """Where the ice will crack: a few thin, jagged lines wandering
        across the pond, numbered so more of them show as the ice
        thickens (a rank per pixel; 2.0 where there's no crack).  Their
        own random numbers, so the meadow's other seasonal patterns stay as
        they were."""
        t = self.terrain
        h, w = t.water.shape
        rank = np.full((h, w), 2.0, dtype=np.float32)
        cells = np.argwhere(t.water)
        if not len(cells):
            return rank
        rng = random.Random(t.seed + 505)
        lines = 7
        for i in range(lines):
            y, x = (float(v) for v in cells[rng.randrange(len(cells))])
            angle = rng.uniform(0, 2 * math.pi)
            for _ in range(rng.randint(14, 40)):
                angle += rng.uniform(-0.7, 0.7)
                x += math.cos(angle)
                y += math.sin(angle) * 0.6
                xi, yi = int(x), int(y)
                if not (0 <= xi < w and 0 <= yi < h and t.water[yi, xi]):
                    break
                rank[yi, xi] = min(rank[yi, xi], i / lines)
        return rank

    def _litter(self, nrng):
        """Fallen-leaf pixels, thicker under the shrubs: (ys, xs, colours,
        thresholds)."""
        t = self.terrain
        h, w = self.base.shape[:2]
        count = w * h // 160
        xs = nrng.integers(0, w, count * 3)
        ys = nrng.integers(0, h, count * 3)
        near = np.zeros(xs.shape, dtype=np.float32)
        for b in t.bushes:
            d = ((xs - b.x) / (b.rx * 2.2 + 4)) ** 2 + ((ys - b.y) / (b.ry * 2.2 + 3)) ** 2
            near = np.maximum(near, np.clip(1.0 - d, 0.0, 1.0))
        keep = nrng.random(xs.shape) < 0.25 + 0.75 * near
        xs, ys = xs[keep][:count * 2], ys[keep][:count * 2]
        dry = ~t.water[ys, xs]
        xs, ys = xs[dry], ys[dry]
        colors = LITTER[nrng.integers(0, len(LITTER), xs.shape)]
        return ys, xs, colors, nrng.random(xs.shape)

    @staticmethod
    def key_for(env):
        p = env.sky.year_phase
        snow = int(round(env.snow_cover * 6)) if env.snow_cover > 0.04 else 0
        frost = int(round(env.frost * 3))
        ice = int(round(env.ice * 3))
        return (int(p * 52) % 52, snow, frost, ice)

    def apply(self, key):
        """Build the ground surface and prop frames for ``key``."""
        if key == self.key:
            return False
        self.key = key
        week, snow_level, frost_level, ice_level = key
        p = (week + 0.5) / 52
        w = season_weights(p)
        cover = snow_level / 6
        frost = frost_level / 3
        t = self.terrain
        rgb = grade_plants(self.base, w, self.patch)
        ys, xs, colors, thresholds = self.litter
        show = thresholds < w["litter"] * 0.8
        rgb[ys[show], xs[show]] = colors[show]
        if frost > 0:
            # A pale bloom over the grass, with a sparkle of white blades
            # (but not under the tree, where the frost doesn't form).
            green = np.clip(_greenness(self.base) + 0.4, 0.0, 1.0)[..., None] * ~self.roof[..., None]
            rgb += (FROST - rgb) * (0.42 * frost * green)
            rime = (self.frost_rank < 0.08 * frost) & (green[..., 0] > 0.5) & ~self.roof
            rgb[rime] = FROST + 20
        if ice_level:
            # Ice from the edges in, the water still showing through it, with
            # a few pale cracks (and, frozen right over, a dusting of snow).
            water = t.water
            k = 0.3 + 0.1 * ice_level
            rgb[water] += (ICE - rgb[water]) * k
            cracks = self.cracks < (ice_level - 1) / 2.0
            rgb[cracks] = ICE_CRACK
            if cover > 0 and ice_level == 3:
                dusted = water & (self.snow_rank < cover * 0.6)
                rgb[dusted] = _gradient(_lum(self.base) + 60, SNOW)[dusted]
        if cover > 0:
            snowy = self.snow_rank < cover
            if cover >= 0.99:
                snowy[:] = True
            snowy &= ~t.water & ~self.roof     # a dry ring under the tree
            snow = _gradient(_lum(self.base) + 30, SNOW)
            rgb[snowy] = snow[snowy]
        h, wd = rgb.shape[:2]
        ground = pygame.Surface((wd, h), pygame.SRCALPHA, 32)
        ground.fill((0, 0, 0, 255))
        pygame.surfarray.pixels3d(ground)[...] = np.clip(rgb, 0, 255).astype(np.uint8).swapaxes(0, 1)
        if cover < 0.5:
            for sprite, x, y, bloom in t.flower_decals:
                if bloom < w["bloom"]:
                    ground.blit(sprite, (x, y))
        t.ground = ground
        for i, prop in enumerate(t.props):
            if prop.kind != "bowl":       # the bowl's frames follow how full it is
                self._grade_prop(prop, w, cover, i)
        evergreen = dict(w, autumn=0.0, winter=w["winter"] * 0.3)
        for i, canopy in enumerate(t.canopies):
            self._grade_prop(canopy, evergreen, cover, 100 + i)
        return True

    def _grade_prop(self, prop, w, cover, index):
        kind = prop.kind
        if kind == "flower":
            prop.hidden = prop.bloom >= w["bloom"] or cover > 0.5
            if prop.hidden:
                return
        frames = []
        for frame in prop.base_frames:
            rgb, alpha = _surface_rgba(frame)
            if kind in ("bush", "grass", "reeds", "flower"):
                leaves = AUTUMN_LEAVES[index % 3] if kind == "bush" else None
                patch = 0.7 + 0.6 * ((index * 0.618) % 1.0)
                rgb = grade_plants(rgb, w, patch, leaves)
            rgb = snow_caps(rgb, alpha, cover, index * 7)  # same caps on every sway frame
            if kind == "canopy" and cover > 0.15:
                rgb = snow_on_crown(rgb, alpha, cover, index * 7)
            frames.append(_to_surface(rgb, alpha))
        prop.frames = frames
