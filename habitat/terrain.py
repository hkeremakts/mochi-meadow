"""Procedural meadow: grass, a pond, bushes, rocks, flowers, and the bowl.

The ground is generated at art resolution into a numpy RGB array and baked
into one surface.  Anything tall enough to overlap a walking animal (bushes,
rocks, reeds, tall grass, flowers) becomes a ``Prop`` instead, so the
renderer can depth-sort it against the creatures.

Besides pixels, the terrain answers the questions the animals ask: where is
water, what is solid, where can the cat walk, and where does it go to eat,
drink, shelter and nap.
"""

import math
import os
import random

import numpy as np
import pygame

from . import art
from .assets import ASSET_ROOT, load_image, natural_key
from .config import EDGE_MARGIN_BOTTOM, EDGE_MARGIN_TOP, EDGE_MARGIN_X
from .cat_anims import MOUTH_REACH
from .paths import Regions, find_path, widen
from .util import clamp, dither_mask, fbm, value_noise

# Greens taken from the environment sprites, with in-between tones added.
GRASS = [(42, 79, 74), (49, 96, 80), (55, 111, 80), (61, 125, 78), (71, 139, 73), (84, 154, 68)]
SOIL = [(78, 92, 62), (96, 96, 64), (112, 104, 72)]
WATER = [(25, 52, 70), (31, 68, 86), (40, 89, 102), (56, 113, 112)]
MUD = [(62, 53, 44), (82, 69, 54), (101, 86, 64)]
BANK = [(46, 38, 34), (64, 54, 44)]
STONE = [(70, 70, 78), (122, 120, 120), (146, 144, 140), (170, 168, 160)]

class Prop:
    """A static object drawn depth-sorted with the animals."""

    __slots__ = ("kind", "frames", "x", "y", "anchor", "sway", "phase", "base_frames", "hidden", "bloom", "fade")

    def __init__(self, kind, frames, x, y, anchor, sway=0.0, phase=0.0):
        self.kind = kind
        self.frames = frames
        self.base_frames = frames     # as drawn; ``frames`` may be a seasonal version
        self.hidden = False
        self.bloom = 0.0              # flowers: how far into the season they open
        self.fade = 1.0               # a tree crown turns see-through over the cat
        self.x = x
        self.y = y
        self.anchor = anchor
        self.sway = sway
        self.phase = phase


class Spot:
    """Where the cat stands to do something, and the walkable point it
    approaches from (the last step may enter a blocked margin, e.g. to lean
    over the water or tuck under a bush)."""

    __slots__ = ("x", "y", "facing", "approach", "owner")

    def __init__(self, x, y, facing, approach, owner=None):
        self.x = x
        self.y = y
        self.facing = facing
        self.approach = approach
        self.owner = owner


class Bush:
    __slots__ = ("x", "y", "rx", "ry", "prop")

    def __init__(self, x, y, rx, ry, prop):
        self.x, self.y, self.rx, self.ry, self.prop = x, y, rx, ry, prop


# The old tree.  A real tree stands many times a cat's height; the first
# one read too small, so everything about it is scaled by TREE_SIZE.
TREE_SIZE = 1.35
TRUNK = round(30 * TREE_SIZE)      # how much trunk shows under the crown, art pixels
CROWN_LIFT = 42.0 * TREE_SIZE      # the crown's centre above the trunk's foot


class Tree:
    """The old tree.  Its crown is drawn over everything beneath it; under
    it (the ``roof``, an ellipse on the ground) rain and snow don't reach."""

    __slots__ = ("x", "y", "trunk", "canopy", "rx", "ry", "roof_cx", "roof_cy", "roof_rx", "roof_ry")

    def __init__(self, x, y, trunk, canopy, rx, ry):
        self.x, self.y, self.trunk, self.canopy, self.rx, self.ry = x, y, trunk, canopy, rx, ry
        self.roof_cx, self.roof_cy = x, y - 8 * TREE_SIZE
        self.roof_rx, self.roof_ry = rx * 0.88, ry * 0.62

    def covers(self, x, y):
        dx = (x - self.roof_cx) / self.roof_rx
        dy = (y - self.roof_cy) / self.roof_ry
        return dx * dx + dy * dy < 1.0


class Pond:
    __slots__ = ("cx", "cy", "rx", "ry", "open_cells", "top", "bottom")

    def __init__(self, cx, cy, rx, ry, open_cells, top, bottom):
        self.cx, self.cy, self.rx, self.ry = cx, cy, rx, ry
        self.open_cells = open_cells
        self.top, self.bottom = top, bottom


class Terrain:
    def __init__(self, width, height, seed):
        self.width = width
        self.height = height
        self.seed = seed
        self.ground = None
        self.water = np.zeros((height, width), dtype=bool)
        self.solid = np.zeros((height, width), dtype=bool)
        self.blocked = np.zeros((height, width), dtype=bool)
        self.props = []
        self.bushes = []
        self.rocks = []
        self.perches = []      # (x, base_y, height) of flowers butterflies settle on
        self.pond = None
        self.bowl = None       # (x, y) of the bowl's base
        self.bowl_prop = None
        self.spots = {"bowl": [], "drink": [], "shelter": [], "nap": [], "watch": [], "roof": []}
        self.spawn = (width / 2, height / 2)
        self.ground_base = None     # RGB array of the ground as generated (no seasons, no small flowers)
        self.flower_decals = []     # (sprite, x, y, bloom): small flowers, drawn while in season
        self.tree = None
        self.canopies = []          # crowns: drawn after everything on the ground

    def under_roof(self, x, y):
        """Under the tree's crown, where rain doesn't fall."""
        return self.tree is not None and self.tree.covers(x, y)

    def is_water(self, x, y):
        xi, yi = int(x), int(y)
        return 0 <= xi < self.width and 0 <= yi < self.height and bool(self.water[yi, xi])

    def walkable(self, x, y):
        xi, yi = int(x), int(y)
        return 0 <= xi < self.width and 0 <= yi < self.height and not self.blocked[yi, xi]

    def free_ground(self, x, y):
        xi, yi = int(x), int(y)
        return 0 <= xi < self.width and 0 <= yi < self.height and not self.solid[yi, xi]


# --------------------------------------------------------------------------
# Asset cache

_ASSETS = {}


def _assets():
    if not _ASSETS:
        env = os.path.join(ASSET_ROOT, "environment")
        tufts = []
        for name in sorted(os.listdir(env), key=natural_key):
            if name.startswith("grassandflowers") and name.endswith(".png"):
                tufts.append(load_image(os.path.join(env, name)))
        tall, short = [], []
        for t in tufts:
            (tall if t.get_bounding_rect().height >= 9 else short).append(t)
        long_grass = load_image(os.path.join(env, "long_grass.png"))
        tall.append(long_grass)
        bush_dir = os.path.join(env, "bush")
        pieces = [load_image(os.path.join(bush_dir, f"bush{i}.png")) for i in (1, 2, 3)]
        _ASSETS.update(tall=tall, short=short, bush=pieces)
        _ASSETS["tall_sway"] = [art.sway_frames(t, max_shift=2) for t in tall]
    return _ASSETS


# --------------------------------------------------------------------------
# Generation

def generate_terrain(width, height, seed):
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    assets = _assets()
    t = Terrain(width, height, seed)
    footprints = np.zeros((height, width), dtype=bool)
    features = []  # (cx, cy, rx, ry) ellipses already claimed
    decals = []    # (surface, x, y) baked onto the ground after the base

    tone = _grass_tones(width, height, nrng)
    _texture_blades(tone, nrng)
    img = np.array(GRASS, dtype=np.uint8)[tone]
    _bare_patches(img, width, height, nrng)

    _make_pond(t, img, rng, decals, features)
    _make_bowl(t, img, rng, features, footprints)
    _make_bushes(t, img, rng, assets, features, footprints)
    _make_rocks(t, img, rng, features, footprints, decals)
    _make_flowers(t, rng, features)
    _make_tufts(t, rng, nrng, assets, features, decals)
    # The tree comes last, from its own random numbers, so adding it left
    # every other feature of an existing meadow where it was.
    _make_tree(t, img, random.Random(seed * 31 + 7), features, footprints)

    t.solid = t.water | footprints
    _build_walk_grid(t, footprints)
    _choose_spawn(t)
    _find_spots(t, rng)

    surface = pygame.surfarray.make_surface(np.ascontiguousarray(img.swapaxes(0, 1)))
    ground = art.blank(width, height)
    ground.blit(surface, (0, 0))
    for sprite, x, y in decals:
        ground.blit(sprite, (x, y))
    t.ground_base = pygame.surfarray.array3d(ground).swapaxes(0, 1).copy()
    for sprite, x, y, _ in t.flower_decals:
        ground.blit(sprite, (x, y))
    t.ground = ground
    t.props.sort(key=lambda p: p.y)
    return t


def _grass_tones(w, h, nrng):
    broad = fbm(w, h, 80, nrng, octaves=2)
    medium = value_noise(w, h, 22, nrng)
    fine = value_noise(w, h, 6, nrng)
    v = broad * 0.55 + medium * 0.3 + fine * 0.15
    # Rank-normalise so every map has the same mix of tones.
    order = np.argsort(v, axis=None)
    u = np.empty(v.size, dtype=np.float32)
    u[order] = np.linspace(0.0, 1.0, v.size, dtype=np.float32)
    u = u.reshape(h, w)
    level = np.interp(u, [0.0, 0.015, 0.09, 0.40, 0.84, 0.98, 1.0],
                      [0.6, 1.1, 1.8, 2.7, 3.4, 4.2, 4.7])
    # Sharpen transitions so dithering is a seam, not a wash.
    frac = level - np.floor(level)
    frac = np.clip((frac - 0.5) * 2.6 + 0.5, 0.0, 1.0)
    level = np.floor(level) + frac
    tone = np.floor(level + dither_mask(h, w) - 0.5 + 0.5).astype(np.int32)
    return np.clip(tone, 0, len(GRASS) - 1)


def _texture_blades(tone, nrng):
    """Scatter tiny blade marks one shade darker, some with a lit tip."""
    h, w = tone.shape
    count = w * h // 34
    xs = nrng.integers(1, w - 3, count)
    ys = nrng.integers(2, h - 2, count)
    kinds = nrng.integers(0, 4, count)
    glyphs = [((0, 0), (2, 0), (1, 1)), ((0, 0), (0, 1)), ((1, 0), (0, 1), (2, 1)), ((0, 0),)]
    for k, glyph in enumerate(glyphs):
        sel = kinds == k
        gx, gy = xs[sel], ys[sel]
        for dx, dy in glyph:
            tone[gy + dy, gx + dx] = np.maximum(tone[gy + dy, gx + dx] - 1, 0)
    tips = nrng.random(count) < 0.35
    tx, ty = xs[tips], ys[tips] - 1
    tone[ty, tx] = np.minimum(tone[ty, tx] + 2, len(GRASS) - 1)


def _bare_patches(img, w, h, nrng):
    """A few worn spots where the grass has thinned."""
    n = value_noise(w, h, 13, nrng) * 0.75 + value_noise(w, h, 5, nrng) * 0.25
    cutoff = np.quantile(n, 0.991)
    d = dither_mask(h, w)
    core = n > cutoff + 0.02
    fringe = (n > cutoff) & ~core & (d < 0.4)
    img[fringe] = np.array(SOIL[0], dtype=np.uint8)
    img[core] = np.array(SOIL[1], dtype=np.uint8)
    img[core & (d > 0.8)] = np.array(SOIL[2], dtype=np.uint8)


def _claim_ok(features, x, y, rx, ry, pad=0.0):
    for (cx, cy, frx, fry) in features:
        nx = (x - cx) / (rx + frx + pad)
        ny = (y - cy) / (ry + fry + pad)
        if nx * nx + ny * ny < 1.0:
            return False
    return True


def _bake_shadow(img, cx, cy, rx, ry, strength=0.62):
    """Darken an ellipse of ground, with a dithered soft rim."""
    h, w = img.shape[:2]
    x0, x1 = max(0, int(cx - rx - 2)), min(w, int(cx + rx + 3))
    y0, y1 = max(0, int(cy - ry - 2)), min(h, int(cy + ry + 3))
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    q = ((xx - cx) / max(rx, 0.5)) ** 2 + ((yy - cy) / max(ry, 0.5)) ** 2
    d = dither_mask(h, w)[y0:y1, x0:x1]
    region = img[y0:y1, x0:x1].astype(np.float32)
    inner = q < 0.62
    rim = (q >= 0.62) & (q < 1.0) & (d < 0.5)
    region[inner] *= strength
    region[rim] *= (strength + 1.0) / 2.0
    img[y0:y1, x0:x1] = region.astype(np.uint8)


# --- pond -----------------------------------------------------------------

def _make_pond(t, img, rng, decals, features):
    w, h = t.width, t.height
    if w < 260 or h < 170:
        return
    rx = clamp(w * 0.115, 30.0, 76.0)
    ry = rx * 0.6
    cx = cy = None
    for _ in range(60):
        x = rng.uniform(rx + 30, w - rx - 30)
        y = rng.uniform(ry + EDGE_MARGIN_TOP + 14, h - ry - 26)
        if abs(x - w / 2) < rx + 34 and abs(y - h / 2) < ry + 30:
            continue  # leave the middle open for the cat
        cx, cy = x, y
        break
    if cx is None:
        return
    waves = [(k, rng.uniform(0.03, 0.09) / (k * 0.6), rng.uniform(0, 2 * math.pi)) for k in (2, 3, 4, 5)]

    yy, xx = np.mgrid[0:h, 0:w]
    dx = (xx - cx) / rx
    dy = (yy - cy) / ry
    angle = np.arctan2(dy, dx)
    radius = np.ones_like(dx)
    for k, amp, phase in waves:
        radius += amp * np.sin(k * angle + phase)
    q = np.sqrt(dx * dx + dy * dy) / radius
    water = q < 1.0
    d = dither_mask(h, w)

    # Depth tones, dithered across their boundaries.
    depth = np.interp(q, [0.0, 0.42, 0.72, 0.9, 1.0], [0.0, 0.5, 1.5, 2.5, 3.0])
    depth_idx = np.clip(np.floor(depth + d - 0.5 + 0.5), 0, 3).astype(np.int32)
    img[water] = np.array(WATER, dtype=np.uint8)[depth_idx[water]]

    shore = (q >= 1.0) & (q < 1.09)
    img[shore] = np.array(MUD[1], dtype=np.uint8)
    img[shore & (d > 0.7)] = np.array(MUD[2], dtype=np.uint8)
    speckle = value_noise(w, h, 3, np.random.default_rng(int(cx * 7 + cy)))
    fringe = (q >= 1.09) & (q < 1.17) & (speckle > 0.45)
    img[fringe] = np.array(MUD[0], dtype=np.uint8)

    # The far bank's earth wall: water pixels just below non-water.
    above1 = np.zeros_like(water)
    above1[1:] = ~water[:-1]
    above2 = np.zeros_like(water)
    above2[2:] = ~water[:-2]
    wall0 = water & above1
    wall1 = water & above2 & ~wall0
    img[wall0] = np.array(BANK[0], dtype=np.uint8)
    img[wall1] = np.array(BANK[1], dtype=np.uint8)

    t.water = water
    open_water = water & ~wall0 & ~wall1

    # Lily pads, baked flat onto the water.
    pads = rng.randint(3, 6)
    placed = []
    for _ in range(pads * 8):
        if len(placed) >= pads:
            break
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.25, 0.72)
        px, py = cx + math.cos(a) * r * rx, cy + math.sin(a) * r * ry
        if any(abs(px - qx) < 9 and abs(py - qy) < 6 for qx, qy in placed):
            continue
        pw = rng.choice((5, 6, 7, 8))
        ph = max(3, pw // 2 + rng.choice((0, 1)))
        pad = art.lily_pad(rng, pw, ph, bloom=rng.random() < 0.35)
        x0, y0 = int(px - pw / 2), int(py - ph / 2)
        decals.append((pad, x0, y0))
        open_water[max(0, y0):y0 + ph, max(0, x0):x0 + pw] = False
        placed.append((px, py))

    ys, xs = np.nonzero(open_water)
    rows = np.nonzero(water.any(axis=1))[0]
    t.pond = Pond(cx, cy, rx, ry, np.stack([xs, ys], axis=1), int(rows[0]), int(rows[-1]))
    features.append((cx, cy, rx * 1.25 + 8, ry * 1.25 + 8))

    # Reeds along the far (north) and side banks.
    clumps = rng.randint(3, 5)
    for i in range(clumps):
        a = rng.uniform(math.pi * 1.05, math.pi * 1.95) if i < 2 else rng.choice(
            (rng.uniform(-0.5, 0.4), rng.uniform(math.pi - 0.4, math.pi + 0.5)))
        rr = 1.02
        for k, amp, phase in waves:
            rr += amp * math.sin(k * a + phase)
        bx = cx + math.cos(a) * rx * rr
        by = cy + math.sin(a) * ry * rr + 2
        rw, rh = rng.choice(((13, 24), (15, 26), (11, 20)))
        frames = art.sway_frames(art.reeds(rng, rw, rh), max_shift=2)
        t.props.append(Prop("reeds", frames, bx, by, (rw / 2 + 2, rh - 1), sway=0.9, phase=rng.random()))


# --- bowl & patio -----------------------------------------------------------

def _stone_slab(img, x0, y0, sw, sh, rng):
    h, w = img.shape[:2]
    for y in range(sh):
        for x in range(sw):
            corner = (x in (0, sw - 1)) and (y in (0, sh - 1))
            if corner:
                continue
            px, py = int(x0 + x), int(y0 + y)
            if not (0 <= px < w and 0 <= py < h):
                continue
            edge = x in (0, sw - 1) or y in (0, sh - 1) or \
                ((x in (1, sw - 2)) and (y in (1, sh - 2)) and False)
            if edge:
                c = STONE[0] if (y == sh - 1 or x == sw - 1) else STONE[1]
            elif y == 1 or x == 1:
                c = STONE[3]
            else:
                c = STONE[2] if rng.random() > 0.12 else STONE[1]
            img[py, px] = c


def _make_bowl(t, img, rng, features, footprints):
    w, h = t.width, t.height
    if t.pond is not None:
        right = t.pond.cx < w / 2
    else:
        right = rng.random() < 0.5
    for _ in range(40):
        x = (w * rng.uniform(0.74, 0.86)) if right else (w * rng.uniform(0.14, 0.26))
        y = h * rng.uniform(0.66, 0.8)
        y = min(y, h - EDGE_MARGIN_BOTTOM - 12)
        if _claim_ok(features, x, y, 26, 14):
            break
    else:
        return
    # Flagstones the bowl sits on.
    _stone_slab(img, x - 9, y - 6, 18, 9, rng)
    side = -1 if right else 1
    _stone_slab(img, x + side * 14 - 6, y - 3, 12, 8, rng)
    _stone_slab(img, x - side * 4 - 5, y + 4, 10, 6, rng)
    _bake_shadow(img, x, y + 1, 7, 2.5, 0.7)
    t.bowl = (x, y)
    sprite = art.bowl(1.0, rng)
    t.bowl_prop = Prop("bowl", [sprite], x, y + 1, (sprite.get_width() / 2, sprite.get_height() - 1))
    t.props.append(t.bowl_prop)
    features.append((x, y, 22, 12))
    _fill_ellipse(footprints, x, y - 1, 6, 2.5)


# --- bushes -----------------------------------------------------------------

def _make_bush_sprite(rng, pieces, rx, ry):
    w = int(rx * 2 + 18)
    h = int(ry * 2.4 + 22)
    canvas = art.blank(w, h)
    cx = w / 2.0
    base = h - 5
    dome_cy = base - ry * 1.15
    stamps = []
    count = int(rx * ry / 11) + 6
    for _ in range(count):
        a = rng.uniform(0, 2 * math.pi)
        r = math.sqrt(rng.random())
        px = cx + math.cos(a) * r * rx
        py = dome_cy + math.sin(a) * r * ry * 1.05
        piece = pieces[0] if r < 0.5 else pieces[1] if r < 0.82 else pieces[2]
        if rng.random() < 0.5:
            piece = pygame.transform.flip(piece, True, False)
        stamps.append((py, px, piece))
    stamps.sort(key=lambda s: s[0])
    for py, px, piece in stamps:
        canvas.blit(piece, (round(px - 8), round(py - 8)))
    # Shade the underside so the bush sits on the ground.
    box = canvas.get_bounding_rect()
    for y in range(box.bottom - 5, box.bottom):
        k = 0.82 - 0.06 * (y - (box.bottom - 5))
        for x in range(box.left, box.right):
            c = canvas.get_at((x, y))
            if c.a:
                canvas.set_at((x, y), (int(c.r * k), int(c.g * k), int(c.b * k), c.a))
    if rng.random() < 0.45:  # berries or blossoms on some bushes
        color = rng.choice(((196, 52, 60), (236, 230, 240), (240, 196, 90)))
        for _ in range(rng.randint(4, 9)):
            x = rng.randint(box.left + 2, box.right - 3)
            y = rng.randint(box.top + 2, box.bottom - 6)
            if canvas.get_at((x, y)).a:
                canvas.set_at((x, y), color)
    anchor_y = box.bottom - 2
    return canvas, (cx, anchor_y), box


def _make_bushes(t, img, rng, assets, features, footprints):
    w, h = t.width, t.height
    target = int(clamp(round(w * h / 38000), 2, 7))
    for _ in range(target * 25):
        if len(t.bushes) >= target:
            break
        rx = rng.uniform(13, 21)
        ry = rx * rng.uniform(0.5, 0.62)
        x = rng.uniform(EDGE_MARGIN_X + 4, w - EDGE_MARGIN_X - 4)
        y = rng.uniform(EDGE_MARGIN_TOP + 18, h - EDGE_MARGIN_BOTTOM - 8)
        if abs(x - w / 2) < rx + 40 and abs(y - h / 2) < ry + 34:
            continue
        if not _claim_ok(features, x, y, rx + 26, ry + 14):
            continue
        sprite, anchor, box = _make_bush_sprite(rng, assets["bush"], rx, ry)
        prop = Prop("bush", [sprite], x, y, anchor)
        t.props.append(prop)
        t.bushes.append(Bush(x, y, rx, ry, prop))
        features.append((x, y, rx + 6, ry + 6))
        _bake_shadow(img, x + 2, y - 1, rx + 3, ry * 0.55 + 2, 0.6)
        _fill_ellipse(footprints, x, y - 3, rx * 0.8, max(3.0, ry * 0.45))


# --- the old tree ---------------------------------------------------------

def _make_tree(t, img, rng, features, footprints):
    w, h = t.width, t.height
    if w < 300 or h < 190:
        return
    rx = clamp(w * 0.1, 34.0, 52.0) * TREE_SIZE
    ry = rx * 0.62
    girth = TREE_SIZE ** 0.5
    for _ in range(80):
        x = rng.uniform(EDGE_MARGIN_X + rx * 0.6, w - EDGE_MARGIN_X - rx * 0.6)
        y = rng.uniform(EDGE_MARGIN_TOP + 46 * TREE_SIZE, h - EDGE_MARGIN_BOTTOM - 24)
        if abs(x - w / 2) < 50 and abs(y - h * 0.55) < 40:
            continue                     # leave the middle (where the cat starts) open
        if not _claim_ok(features, x, y - 8, rx * 0.9, ry * 0.7):
            continue
        break
    else:
        return
    canopy_img = art.tree_canopy(rng, rx, ry)
    cw, ch = canopy_img.get_size()
    trunk_img = art.tree_trunk(rng, TRUNK, girth)
    trunk = Prop("trunk", [trunk_img], x, y, (trunk_img.get_width() / 2, trunk_img.get_height() - 1))
    canopy = Prop("canopy", [canopy_img], x, y - CROWN_LIFT, (cw / 2, ch / 2), sway=0.5, phase=rng.random())
    t.props.append(trunk)
    t.canopies.append(canopy)
    t.tree = Tree(x, y, trunk, canopy, rx, ry)
    features.append((x, y - 8, rx * 0.9, ry * 0.7))
    # Only the soft shade a crown gives in any light: the sun's shadow moves (shade.py).
    _bake_shadow(img, x + 1, y - 6 * TREE_SIZE, rx * 0.8, ry * 0.5, 0.86)
    _bake_shadow(img, x, y, 5.0 * girth, 2.0 * girth, 0.7)
    _fill_ellipse(footprints, x, y - 1, 4.0 * girth, 2.0 * girth)


# --- rocks ------------------------------------------------------------------

def _make_rocks(t, img, rng, features, footprints, decals):
    w, h = t.width, t.height
    target = int(clamp(round(w * h / 70000), 1, 4))
    for _ in range(target * 30):
        if len(t.rocks) >= target:
            break
        rw = rng.randint(14, 22)
        rh = rng.randint(9, 12)
        x = rng.uniform(EDGE_MARGIN_X + 6, w - EDGE_MARGIN_X - 6)
        y = rng.uniform(EDGE_MARGIN_TOP + 10, h - EDGE_MARGIN_BOTTOM - 6)
        if abs(x - w / 2) < 40 and abs(y - h / 2) < 30:
            continue
        if not _claim_ok(features, x, y, rw / 2 + 22, rh / 2 + 10):
            continue
        sprite = art.rock(rng, rw, rh, mossy=rng.random() < 0.6)
        prop = Prop("rock", [sprite], x, y, (rw / 2.0, rh - 2))
        t.props.append(prop)
        t.rocks.append(prop)
        features.append((x, y, rw / 2 + 4, rh / 2 + 3))
        _bake_shadow(img, x + 2, y, rw * 0.55, rh * 0.28 + 1, 0.62)
        _fill_ellipse(footprints, x, y - 2, rw * 0.42, rh * 0.3)
    # Pebbles, baked flat.
    for _ in range(int(w * h / 9000)):
        pw, ph = rng.randint(3, 6), rng.randint(2, 4)
        x, y = rng.uniform(4, w - 8), rng.uniform(4, h - 6)
        if t.is_water(x, y) or not _claim_ok(features, x, y, 2, 2):
            continue
        _bake_shadow(img, x + pw / 2 + 0.5, y + ph - 0.5, pw * 0.55, 1.0, 0.7)
        decals.append((art.rock(rng, pw, ph), int(x), int(y)))


# --- flowers & grass -----------------------------------------------------

FLOWER_WEIGHTS = [("daisy", 5), ("buttercup", 4), ("clover", 3), ("bluebell", 2), ("poppy", 1)]


def _pick_flower(rng):
    total = sum(w for _, w in FLOWER_WEIGHTS)
    r = rng.uniform(0, total)
    for kind, wgt in FLOWER_WEIGHTS:
        r -= wgt
        if r <= 0:
            return kind
    return "daisy"


def _make_flowers(t, rng, features):
    w, h = t.width, t.height
    patches = int(clamp(round(w * h / 26000), 3, 10))
    for _ in range(patches):
        for _ in range(20):
            px = rng.uniform(20, w - 20)
            py = rng.uniform(EDGE_MARGIN_TOP, h - 12)
            if not t.is_water(px, py) and _claim_ok(features, px, py, 6, 4):
                break
        else:
            continue
        kinds = [_pick_flower(rng) for _ in range(rng.choice((1, 1, 2)))]
        spread = rng.uniform(9, 22)
        for _ in range(rng.randint(6, 15)):
            fx = px + rng.gauss(0, spread)
            fy = py + rng.gauss(0, spread * 0.6)
            if not (6 <= fx < w - 6 and 8 <= fy < h - 4):
                continue
            if t.is_water(fx, fy) or t.is_water(fx, fy + 3) or not _claim_ok(features, fx, fy, 1, 1):
                continue
            kind = rng.choice(kinds)
            stem = rng.choice((1, 2, 2, 3, 4, 5))
            sprite = art.flower(kind, stem, rng)
            sw, sh = sprite.get_size()
            # Each flower opens at its own point in the season.
            bloom = rng.random()
            if stem <= 2:
                t.flower_decals.append((sprite, int(fx - sw // 2), int(fy - sh + 1), bloom))
            else:
                frames = art.sway_frames(sprite, max_shift=1, count=5)
                prop = Prop("flower", frames, fx, fy, (sw / 2 + 1, sh - 1), sway=0.6, phase=rng.random())
                prop.bloom = bloom
                t.props.append(prop)
            t.perches.append((fx, fy, sh - 1))  # base point and bloom height


def _make_tufts(t, rng, nrng, assets, features, decals):
    w, h = t.width, t.height
    density = value_noise(w, h, 40, nrng)
    edge_boost = np.zeros((h, w), dtype=np.float32)
    band = 22
    yy, xx = np.mgrid[0:h, 0:w]
    edge_dist = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy))
    edge_boost[edge_dist < band] = 1.0 - edge_dist[edge_dist < band] / band

    def accept(x, y):
        xi, yi = int(x), int(y)
        if t.is_water(x, y) or t.is_water(x, y + 2):
            return False
        p = 0.2 + 0.8 * density[yi, xi] + 0.6 * edge_boost[yi, xi]
        return rng.random() < p and _claim_ok(features, x, y, 1, 1)

    for _ in range(w * h // 900):
        x, y = rng.uniform(2, w - 2), rng.uniform(2, h - 2)
        if accept(x, y):
            sprite = rng.choice(assets["short"] + assets["tall"])
            if rng.random() < 0.5:
                sprite = pygame.transform.flip(sprite, True, False)
            box = sprite.get_bounding_rect()
            decals.append((sprite, int(x - 8), int(y - box.bottom + 1)))

    tall = assets["tall_sway"]
    for _ in range(w * h // 4200):
        x, y = rng.uniform(4, w - 4), rng.uniform(10, h - 2)
        if accept(x, y):
            frames = rng.choice(tall)
            box = frames[2].get_bounding_rect()
            t.props.append(Prop("grass", frames, x, y, (frames[2].get_width() / 2, box.bottom - 1),
                                sway=1.0, phase=rng.random()))


# --- walkability ------------------------------------------------------------

def _fill_ellipse(mask, cx, cy, rx, ry):
    h, w = mask.shape
    x0, x1 = max(0, int(cx - rx - 1)), min(w, int(cx + rx + 2))
    y0, y1 = max(0, int(cy - ry - 1)), min(h, int(cy + ry + 2))
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    inside = ((xx - cx) / max(rx, 0.5)) ** 2 + ((yy - cy) / max(ry, 0.5)) ** 2 <= 1.0
    mask[y0:y1, x0:x1] |= inside


def dilate(mask, rx, ry):
    """Grow a boolean mask by an elliptical radius (rx, ry)."""
    h, w = mask.shape
    out = np.zeros_like(mask)
    pad_x = int(rx) + 1
    padded = np.zeros((h, w + 2 * pad_x), dtype=np.int32)
    padded[:, pad_x:pad_x + w] = mask
    csum = np.concatenate((np.zeros((h, 1), dtype=np.int32), np.cumsum(padded, axis=1)), axis=1)
    ry_i = int(ry)
    for dy in range(-ry_i, ry_i + 1):
        half = int(rx * math.sqrt(max(0.0, 1.0 - (dy / (ry + 0.5)) ** 2)))
        lo = np.arange(w) + pad_x - half
        hi = np.arange(w) + pad_x + half + 1
        row_hit = (csum[:, hi] - csum[:, lo]) > 0
        if dy >= 0:
            out[dy:, :] |= row_hit[:h - dy, :]
        else:
            out[:dy, :] |= row_hit[-dy:, :]
    return out


def _build_walk_grid(t, footprints):
    blocked = dilate(t.water, 14, 7) | dilate(footprints, 9, 4)
    blocked[:, :EDGE_MARGIN_X] = True
    blocked[:, t.width - EDGE_MARGIN_X:] = True
    blocked[:EDGE_MARGIN_TOP, :] = True
    blocked[t.height - EDGE_MARGIN_BOTTOM:, :] = True
    t.blocked = blocked
    t.blocked_wide = widen(blocked, 2)   # plan with a margin; see paths.find_path
    t.regions = Regions(blocked)


def _choose_spawn(t):
    cx, cy = t.width // 2, int(t.height * 0.55)
    for r in range(0, max(t.width, t.height)):
        for dx in range(-r, r + 1, max(1, r)):
            for dy in range(-r, r + 1, max(1, r)):
                x, y = cx + dx, cy + dy
                if 0 <= x < t.width and 0 <= y < t.height and not t.blocked[y, x]:
                    t.spawn = (float(x), float(y))
                    return


# --- interaction spots ------------------------------------------------------

def _step_ok(t, spot):
    (ax, ay), sx, sy = spot.approach, int(spot.x), int(spot.y)
    if not (0 <= ax < t.width and 0 <= ay < t.height) or t.blocked[ay, ax]:
        return False
    if ay == sy:
        cells = t.solid[sy, min(ax, sx):max(ax, sx) + 1]
    elif ax == sx:
        cells = t.solid[min(ay, sy):max(ay, sy) + 1, sx]
    else:
        return False
    return not cells.any()


def _find_spots(t, rng):
    start = (int(t.spawn[0]), int(t.spawn[1]))

    def add(kind, x, y, facing, approach, owner=None):
        spot = Spot(int(round(x)), int(round(y)), facing, (int(round(approach[0])), int(round(approach[1]))), owner)
        if not (0 <= spot.x < t.width and 0 <= spot.y < t.height):
            return
        if not _step_ok(t, spot):
            return
        if find_path(t.blocked, start, spot.approach) is None:
            return
        t.spots[kind].append(spot)

    if t.bowl is not None:
        bx, by = t.bowl
        add("bowl", bx - MOUTH_REACH, by + 1, "right", (bx - MOUTH_REACH - 14, by + 1), "bowl")
        add("bowl", bx + MOUTH_REACH, by + 1, "left", (bx + MOUTH_REACH + 14, by + 1), "bowl")

    if t.pond is not None:
        p = t.pond
        rows = range(int(p.cy - p.ry * 0.35), int(p.cy + p.ry * 0.35) + 1, 3)
        for y in rows:
            cols = np.nonzero(t.water[y])[0]
            if not len(cols):
                continue
            west, east = int(cols[0]), int(cols[-1])
            for x, facing, sign in ((west - MOUTH_REACH + 1, "right", -1), (east + MOUTH_REACH - 1, "left", 1)):
                # Mouth over the water, paws on dry ground.
                if not t.water[y, max(0, x - 12):min(t.width, x + 12)].any():
                    add("drink", x, y, facing, (x + sign * 16, y), "pond")
        # Sit on the near bank and watch the water.
        bottom = p.bottom
        add("watch", p.cx, bottom + 12, "up", (p.cx, bottom + 24), "pond")

    for bush in t.bushes:
        reach = bush.rx * 0.82
        add("shelter", bush.x - reach, bush.y - 1, "left", (bush.x - reach - 16, bush.y - 1), bush)
        add("shelter", bush.x + reach, bush.y - 1, "right", (bush.x + reach + 16, bush.y - 1), bush)

    tree = t.tree
    if tree is not None:
        # Around the trunk, under the crown.
        for dx, dy, facing in ((-15, -4, "right"), (15, -4, "left"), (-9, -13, "right"), (9, -13, "left"),
                               (-22, -9, "right"), (22, -9, "left")):
            x, y = tree.x + dx, tree.y + dy
            if tree.covers(x, y) and t.walkable(x, y):
                add("roof", x, y, facing, (x, y), tree)

    t.spots["nap"].extend(t.spots["shelter"])
    for _ in range(40):
        if len(t.spots["nap"]) >= len(t.spots["shelter"]) + 3:
            break
        x = rng.uniform(EDGE_MARGIN_X + 20, t.width - EDGE_MARGIN_X - 20)
        y = rng.uniform(EDGE_MARGIN_TOP + 20, t.height - EDGE_MARGIN_BOTTOM - 10)
        if t.walkable(x, y) and t.walkable(x - 18, y) and t.walkable(x + 18, y):
            facing = rng.choice(("left", "right"))
            add("nap", x, y, facing, (x, y))
