"""Procedurally drawn pixel art.

Everything is built at native art resolution with a small, fixed palette so
it sits next to the hand-drawn assets without looking foreign.  Shapes that
need to look hand-made (critters) are written out as ASCII; organic ones
(rocks, reeds, bushes) are generated and then shaded by rule.
"""

import math

import pygame

from .util import clamp

OUTLINE = (24, 20, 28)


def blank(w, h):
    s = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA, 32)
    s.fill((0, 0, 0, 0))
    return s


def from_ascii(rows, palette):
    width = max(len(r) for r in rows)
    surf = blank(width, len(rows))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            color = palette.get(ch)
            if color is not None:
                surf.set_at((x, y), color)
    return surf


def sway_frames(sprite, max_shift=2, count=5):
    """Lean a plant left/right by shearing rows: the base stays rooted and
    the tips move most.  Returns ``count`` frames from full-left to
    full-right, each ``2 * max_shift`` px wider than the input."""
    w, h = sprite.get_size()
    box = sprite.get_bounding_rect()
    span = max(1, box.height - 1)
    frames = []
    for i in range(count):
        lean = -1.0 + 2.0 * i / (count - 1)
        out = blank(w + 2 * max_shift, h)
        for y in range(box.top, box.bottom):
            height_frac = clamp((box.bottom - 1 - y) / span, 0.0, 1.0) ** 1.3
            dx = round(lean * max_shift * height_frac)
            out.blit(sprite, (max_shift + dx, y), pygame.Rect(0, y, w, 1))
        frames.append(out)
    return frames


# --------------------------------------------------------------------------
# Rocks

ROCK_TONES = [(54, 52, 62), (86, 86, 96), (114, 112, 118), (146, 144, 146), (182, 180, 174)]
MOSS = [(70, 112, 60), (96, 146, 68)]


def rock(rng, w, h, mossy=False):
    """A shaded boulder lit from the upper left."""
    surf = blank(w, h)
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0 + 0.4
    bumps = [rng.uniform(0.82, 1.04) for _ in range(9)]

    def radius(angle):
        f = (angle % (2 * math.pi)) / (2 * math.pi) * 8
        i = int(f)
        t = f - i
        return bumps[i] + (bumps[i + 1] - bumps[i]) * t

    inside = set()
    for y in range(h):
        for x in range(w):
            dx = (x - cx) / (w / 2.0)
            dy = (y - cy) / (h / 2.0)
            r = radius(math.atan2(dy, dx))
            if dy > 0.3:
                r *= 1.12  # flatter, heavier base
            if dx * dx + dy * dy <= r * r:
                inside.add((x, y))
    for (x, y) in inside:
        edge = any((x + ox, y + oy) not in inside for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        dx = (x - cx) / (w / 2.0)
        dy = (y - cy) / (h / 2.0)
        light = -(dx * 0.62 + dy * 0.78)  # lit from upper left
        if edge:
            tone = 0
        elif light > 0.55:
            tone = 4
        elif light > 0.15:
            tone = 3
        elif light > -0.35:
            tone = 2
        else:
            tone = 1
        color = ROCK_TONES[tone]
        if mossy and dy < -0.15 and not edge and rng.random() < 0.55:
            color = MOSS[1] if light > 0.3 else MOSS[0]
        surf.set_at((x, y), color)
    return surf


# --------------------------------------------------------------------------
# Flowers

STEM = (106, 190, 48)
STEM_DARK = (99, 171, 63)
FLOWER_BLOOMS = {
    "daisy": (["-w-", "wyw", "-w-"], {"w": (236, 234, 222), "y": (240, 196, 64)}),
    "buttercup": (["yy", "yd"], {"y": (246, 208, 60), "d": (204, 158, 40)}),
    "clover": (["-p-", "plp"], {"p": (196, 106, 162), "l": (232, 156, 204)}),
    "bluebell": (["b", "B"], {"b": (150, 182, 244), "B": (104, 138, 222)}),
    "poppy": (["rr", "rd"], {"r": (214, 64, 52), "d": (130, 30, 40)}),
}


def flower(kind, stem_height, rng):
    rows, palette = FLOWER_BLOOMS[kind]
    bloom_w = max(len(r) for r in rows)
    width = max(3, bloom_w)
    height = len(rows) + stem_height
    surf = blank(width, height)
    stem_x = width // 2
    for i in range(stem_height):
        y = height - 1 - i
        surf.set_at((stem_x, y), STEM_DARK if i == 0 else STEM)
    if stem_height >= 3 and rng.random() < 0.7:
        side = stem_x + (1 if rng.random() < 0.5 else -1)
        if 0 <= side < width:
            surf.set_at((side, height - 2), STEM)
    ox = (width - bloom_w) // 2
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in palette:
                surf.set_at((ox + x, y), palette[ch])
    return surf


# --------------------------------------------------------------------------
# Pond plants

def lily_pad(rng, w, h, bloom=False):
    surf = blank(w, h)
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    notch = rng.uniform(0, 2 * math.pi)
    pts = set()
    for y in range(h):
        for x in range(w):
            dx = (x - cx) / (w / 2.0)
            dy = (y - cy) / (h / 2.0)
            if dx * dx + dy * dy > 1.0:
                continue
            a = math.atan2(dy, dx)
            diff = abs((a - notch + math.pi) % (2 * math.pi) - math.pi)
            if diff < 0.32 and dx * dx + dy * dy > 0.05:
                continue
            pts.add((x, y))
    for (x, y) in pts:
        edge = any((x + ox, y + oy) not in pts for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        dy = (y - cy) / (h / 2.0)
        if edge and dy > -0.2:
            c = (36, 90, 60)
        elif dy < -0.3:
            c = (96, 160, 88)
        else:
            c = (62, 132, 74)
        surf.set_at((x, y), c)
    if bloom:
        bx, by = int(cx), max(0, int(cy) - 1)
        surf.set_at((bx, by), (246, 214, 230))
        surf.set_at((bx + 1 if bx + 1 < w else bx - 1, by), (226, 160, 196))
        surf.set_at((bx, by + 1 if by + 1 < h else by), (250, 222, 120))
    return surf


REED_GREENS = [(52, 98, 60), (84, 138, 62), (112, 166, 74)]
CATTAIL = [(88, 58, 42), (118, 78, 52), (146, 102, 66)]


def reeds(rng, w=11, h=20):
    """A clump of reeds with a few cattail heads."""
    surf = blank(w, h)
    stalks = rng.randint(7, 11)
    for _ in range(stalks):
        x = rng.randint(1, w - 2)
        top = rng.randint(1, h // 2)
        lean = rng.choice((-1, 0, 0, 1))
        color = rng.choice(REED_GREENS)
        for y in range(h - 1, top - 1, -1):
            t = (h - 1 - y) / max(1, h - 1 - top)
            px = int(round(x + lean * t * 2))
            if 0 <= px < w:
                surf.set_at((px, y), color)
        if rng.random() < 0.45 and top + 4 < h - 3:
            px = int(round(x + lean * 2))
            for i in range(4):
                for j in (0, 1):
                    qx = px + j - (1 if j and px + 1 >= w else 0)
                    tone = CATTAIL[2] if (i == 0 and j == 0) else CATTAIL[1] if j == 0 else CATTAIL[0]
                    if 0 <= qx < w:
                        surf.set_at((qx, top + 1 + i), tone)
    return surf


# --------------------------------------------------------------------------
# The food bowl (3/4 view: rim, opening, front of the bowl)

BOWL_ROWS = [
    "...ooooooo...",
    "..oRRRRRRRo..",
    ".oRiiiiiiiRo.",
    ".oRiiiiiiiRo.",
    ".oRRRRRRRRRo.",
    ".oBBBBBBBBBo.",
    "..oDDDDDDDo..",
    "...ooooooo...",
]
BOWL_PALETTE = {
    "o": (38, 44, 70),
    "R": (226, 236, 244),
    "i": (164, 182, 204),
    "B": (98, 144, 206),
    "D": (66, 98, 156),
}
KIBBLE = [(150, 96, 58), (118, 72, 44), (182, 128, 80)]


def bowl(fill, rng):
    """``fill`` in [0, 1]: how much of the opening shows kibble."""
    surf = from_ascii(BOWL_ROWS, BOWL_PALETTE)
    cells = [(x, y) for y, row in enumerate(BOWL_ROWS) for x, ch in enumerate(row) if ch == "i"]
    rng.shuffle(cells)
    for (x, y) in cells[:int(round(len(cells) * clamp(fill, 0.0, 1.0)))]:
        surf.set_at((x, y), rng.choice(KIBBLE))
    return surf


# --------------------------------------------------------------------------
# The old tree: an evergreen crown, and the trunk that shows beneath it

CANOPY = [(22, 46, 34), (32, 64, 44), (44, 86, 54), (60, 110, 62), (82, 136, 72), (110, 160, 84)]
BARK = [(52, 38, 30), (78, 58, 42), (104, 80, 58)]


def tree_canopy(rng, rx, ry):
    """A broad, dense crown seen from above at an angle: clumps of leaves,
    lit from the upper left, darker underneath, with a ragged edge."""
    import numpy as np
    w, h = int(rx * 2 + 6), int(ry * 2 + 8)
    cx, cy = w / 2, h / 2 - 1
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    inside = np.zeros((h, w), dtype=bool)
    light = np.full((h, w), -9.0, dtype=np.float32)
    clumps = [(cx, cy, rx * 0.62, ry * 0.62)]
    for _ in range(int(rx * ry / 55)):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0.2, 0.78)
        r = rng.uniform(0.22, 0.36) * rx
        clumps.append((cx + math.cos(a) * rx * d, cy + math.sin(a) * ry * d, r, r * 0.8))
    # Back clumps first, so the front ones (lower on screen) sit over them.
    for x0, y0, a, b in sorted(clumps, key=lambda c: c[1]):
        q = ((xx - x0) / a) ** 2 + ((yy - y0) / b) ** 2
        disc = q < 1.0
        # Each clump is a little dome: lit at its upper left.
        shade = -((xx - x0) / a * 0.55 + (yy - y0) / b * 0.85) - q * 0.35
        light = np.where(disc, shade + (y0 - cy) / ry * -0.25, light)
        inside |= disc
    # Ragged leafy edge.
    noise = np.array([[rng.random() for _ in range(w)] for _ in range(h)], dtype=np.float32)
    edge = inside & ~(np.roll(inside, 1, 0) & np.roll(inside, -1, 0) & np.roll(inside, 1, 1) & np.roll(inside, -1, 1))
    inside &= ~(edge & (noise < 0.35))
    tone = np.digitize(light + (noise - 0.5) * 0.25, [-0.75, -0.35, 0.0, 0.32, 0.62]).astype(np.int32)
    surf = blank(w, h)
    rgb = pygame.surfarray.pixels3d(surf)
    alpha = pygame.surfarray.pixels_alpha(surf)
    pal = np.array(CANOPY, dtype=np.uint8)
    rgb[...] = pal[tone].swapaxes(0, 1)
    alpha[...] = np.where(inside, 255, 0).astype(np.uint8).T
    outline = np.zeros_like(inside)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        outline |= np.roll(np.roll(inside, dy, 0), dx, 1)
    outline &= ~inside
    rgb[outline.T] = (14, 30, 22)
    alpha[outline.T] = 255
    del rgb, alpha
    return surf


def tree_trunk(rng, height=30, girth=1.0):
    """The part of the trunk that shows under the crown, with a root flare."""
    w = int(14 * girth) + 1
    surf = blank(w, height)
    for y in range(height):
        f = y / (height - 1)
        half = (3.6 + (3.0 * max(0.0, f - 0.65) / 0.35) ** 1.5) * girth      # flaring at the foot
        for x in range(w):
            d = (x - (w - 1) / 2) / half
            if abs(d) <= 1.0:
                tone = 2 if d < -0.35 else 1 if d < 0.4 else 0
                if rng.random() < 0.18:
                    tone = max(0, tone - 1)                      # bark furrows
                edge = abs(d) > 0.82
                surf.set_at((x, y), OUTLINE if edge else BARK[tone])
    return surf
