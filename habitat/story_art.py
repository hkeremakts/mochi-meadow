"""Drawings for the seasonal stories (see stories.py).

    the nest        the blackbirds' nest in the old tree, seen from above at
                    the meadow's angle: going up straw by straw, the eggs, the
                    hen sitting tight, and the chicks, asleep in a heap or all
                    mouth when a parent comes
    frogspawn       a clump of jelly in the shallows, its black dots turning
                    to commas, then hatching away
    froglets        the tiny frogs that leave the pond in early summer
    storks, geese   birds high overhead, which only reach the meadow as their
                    reflections in the pond and their shadows on the grass

Everything is drawn with the same rig as the creatures (supersampled
shapes, a limited palette, plum outlines, form shading), except the
overhead birds' shadows, which are soft multiply sprites for the light map.
"""

import math
import random

import pygame
from PIL import Image, ImageDraw

from .pixelrig import Canvas, despeckle, glint_eye, outline, shade, to_surface

# --------------------------------------------------------------------------
# The nest (16 x 11, its cup centred on (8, 6))

NEST = [None, (46, 30, 40), (64, 44, 38), (116, 86, 56), (166, 134, 86), (40, 28, 30),   # outline, twig shade, twig, straw, hollow
        (126, 186, 174), (88, 140, 134),                  # egg, egg shade (blue-green, freckled)
        (168, 132, 126), (122, 102, 92), (240, 176, 56), (252, 220, 104),   # bare chick, downy chick, gape, gape light
        (106, 78, 56), (144, 110, 74), (74, 54, 52), (18, 14, 16), (236, 240, 240), (158, 124, 62)]   # hen, her light, her shade, eye, glint, bill
(N_OUT, N_DARK, N_TWIG, N_STRAW, N_HOLLOW, N_EGG, N_EGG_D, N_BARE, N_DOWN, N_GAPE, N_GAPE_L,
 N_HEN, N_HEN_L, N_HEN_D, N_EYE, N_SHINE, N_BILL) = range(1, 18)
NEST_SIZE = (16, 11)
NEST_ANCHOR = (8, 6)          # the middle of the cup
_CUP = (8.0, 6.2, 6.4, 3.7)   # outer cup: centre and radii
_HOLLOW = (8.0, 5.6, 4.3, 2.1)


def _nest_canvas():
    return Canvas(*NEST_SIZE)


def _twigs(c, rng, n, ring=1.0):
    """Short twigs and straws woven round the cup, some poking out."""
    cx, cy, rx, ry = _CUP
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        length = rng.uniform(1.6, 3.4)
        r0 = ring * rng.uniform(0.75, 1.05)
        x0, y0 = cx + math.cos(a) * rx * r0, cy + math.sin(a) * ry * r0
        t = a + math.pi / 2 + rng.uniform(-0.5, 0.5)
        x1, y1 = x0 + math.cos(t) * length, y0 + math.sin(t) * length * 0.6
        c.paint(c.capsule(x0, y0, x1, y1, 0.45), rng.choice((N_TWIG, N_STRAW, N_DARK)))


def _finish_nest(c, features=(), keep=()):
    grid = c.resolve(len(NEST))
    grid = shade(grid, {N_TWIG: (N_STRAW, N_DARK), N_HEN: (N_HEN_L, N_HEN_D), N_EGG: (None, N_EGG_D)})
    for x, y, col in features:
        xi, yi = int(math.floor(x)), int(math.floor(y))
        if 0 <= xi < c.w and 0 <= yi < c.h:
            grid[yi, xi] = col
    grid = outline(grid, N_OUT)
    grid = despeckle(grid, keep=(N_OUT, N_STRAW, N_DARK, N_EYE, N_SHINE, N_BILL, N_GAPE, N_GAPE_L, N_EGG_D))
    return to_surface(grid, NEST)


def _cup(c, rng, level=3):
    """The cup: ``level`` 1 a few twigs laid across a fork, 2 a rough ring,
    3 the finished nest with its dark hollow."""
    cx, cy, rx, ry = _CUP
    if level >= 2:
        k = 0.8 if level == 2 else 1.0
        c.paint(c.ellipse(cx, cy, rx * k, ry * k), N_TWIG)
        hx, hy, hrx, hry = _HOLLOW
        c.paint(c.ellipse(hx, hy + (0.4 if level == 2 else 0.0), hrx * k, hry * k), N_HOLLOW)
    _twigs(c, rng, (10, 9, 12)[level - 1], ring=1.0 if level > 1 else 0.55)
    if level >= 2:
        hx, hy, hrx, hry = _HOLLOW
        # the rim in front of the hollow, so it reads as a cup seen from above
        rim = c.ellipse(cx, cy + 0.9, rx * 0.92, ry * 0.75) & ~c.ellipse(hx, hy, hrx, hry)
        c.paint(rim & c.below(hy + 0.6), N_TWIG)


def nest_frame(level=3, seed=0):
    c = _nest_canvas()
    _cup(c, random.Random(seed), level)
    return _finish_nest(c)


EGG_SPOTS = [(6.4, 5.4), (9.4, 5.2), (7.9, 6.2), (5.9, 6.3), (10.0, 6.3)]


def eggs_frame(n, seed=0):
    c = _nest_canvas()
    _cup(c, random.Random(seed), 3)
    features = []
    for x, y in EGG_SPOTS[:n]:
        c.paint(c.ellipse(x, y, 1.15, 0.8), N_EGG)
        features.append((x + 0.3, y + 0.2, N_EGG_D))        # a freckle
    return _finish_nest(c, features)


def hen_frame(look=0.0, seed=0):
    """The hen sitting tight: her back fills the cup, her tail cocked up
    over one rim and her head up over the other, watching."""
    c = _nest_canvas()
    _cup(c, random.Random(seed), 3)
    c.paint(c.polygon([(5.0, 4.4), (0.8, 1.2 + look * 0.3), (0.3, 2.5), (4.6, 5.6)]), N_HEN_D)    # tail
    c.paint(c.ellipse(7.8, 4.5, 4.2, 2.3), N_HEN)                                                 # back
    c.paint(c.capsule(4.8, 4.1, 9.4, 3.7, 0.6), N_HEN_D)                                          # wing edge
    hx, hy = 11.7 + look * 0.4, 2.7 - abs(look) * 0.2
    c.paint(c.capsule(10.4, 4.4, hx, hy + 0.6, 1.5, 1.3), N_HEN)                                  # neck
    c.paint(c.ellipse(hx, hy, 1.8, 1.5), N_HEN)                                                   # head
    features = [(hx + 1.9, hy + 0.3, N_BILL), (hx + 2.7 + look * 0.3, hy + 0.4, N_BILL), (hx + 0.7, hy + 1.3, N_HEN_L)]
    glint_eye(c, features, hx - 0.1, hy - 0.8, 1.0, N_EYE, N_SHINE)
    return _finish_nest(c, features)


CHICK_SPOTS = [(6.2, 5.2), (9.6, 5.0), (7.9, 5.9), (5.6, 6.2), (10.3, 6.1)]


def chicks_frame(n, age, gaping=0, seed=0):
    """``n`` chicks, ``age`` 0 bare and pink, 1 downy, 2 feathered.  Asleep
    they are a heap in the hollow; gaping (1 or 2, two frames of it) they
    stretch up, all yellow mouth."""
    c = _nest_canvas()
    _cup(c, random.Random(seed), 3)
    skin = N_BARE if age == 0 else N_DOWN if age == 1 else N_HEN
    features = []
    spots = CHICK_SPOTS[:n]
    if not gaping:
        for x, y in spots:
            c.paint(c.ellipse(x, y + 0.3, 1.5 + age * 0.2, 0.9 + age * 0.15), skin)
        if age:
            features += [(x - 0.4, y - 0.1, N_GAPE) for x, y in spots[:2]]     # the yellow flange shows even asleep
        return _finish_nest(c, features)
    for i, (x, y) in enumerate(spots):
        sway = (1 if (i + gaping) % 2 else -1) * 0.5
        top = y - 2.2 - age * 0.5 + (0.4 if (i + gaping) % 3 == 0 else 0.0)
        c.paint(c.capsule(x, y + 0.4, x + sway, top + 0.8, 0.9 + age * 0.15, 0.8 + age * 0.15), skin)   # neck stretched up
        c.paint(c.polygon([(x + sway - 1.3, top + 0.6), (x + sway + 1.3, top + 0.6), (x + sway, top - 1.4)]), N_GAPE)
        features.append((x + sway, top, N_GAPE_L))                  # the inside of the mouth, bright
    return _finish_nest(c, features)


def nest_frames():
    """Every look the nest has: {name: [frames]}."""
    out = {f"build{level}": [nest_frame(level)] for level in (1, 2, 3)}
    out["empty"] = [nest_frame(3)]
    for n in range(1, 6):
        out[f"eggs{n}"] = [eggs_frame(n)]
        for age in (0, 1, 2):
            out[f"chicks{n}_{age}"] = [chicks_frame(n, age)]
            out[f"gape{n}_{age}"] = [chicks_frame(n, age, 1), chicks_frame(n, age, 2)]
    out["hen"] = [hen_frame(0.0), hen_frame(1.0), hen_frame(0.0), hen_frame(-1.0)]
    return out


# --------------------------------------------------------------------------
# Frogspawn: a clump of jelly in the shallows (top-down)

SPAWN_JELLY = (182, 200, 176, 150)
SPAWN_JELLY_OLD = (150, 176, 132, 140)      # a few weeks on, greening with algae
SPAWN_RIM = (222, 232, 214, 180)
SPAWN_DOT = (22, 24, 22, 255)


def spawn_frame(seed, stage, eggs=16):
    """``stage`` 0 round black dots, 1 commas, 2 hatching: the clump
    loosening, half its eggs empty, tadpoles wriggling free."""
    rng = random.Random(seed)
    w, h = 13, 8
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    centres = []
    for _ in range(eggs):
        for _ in range(20):
            x, y = rng.uniform(2.0, w - 2.5), rng.uniform(1.6, h - 1.8)
            if ((x - w / 2) / (w / 2 - 1.2)) ** 2 + ((y - h / 2) / (h / 2 - 0.9)) ** 2 > 1.0:
                continue
            if all(abs(x - a) + abs(y - b) > 1.6 for a, b in centres):
                centres.append((x, y))
                break
    jelly = SPAWN_JELLY if stage < 2 else SPAWN_JELLY_OLD
    for x, y in centres:
        for dx, dy in ((0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)):
            px, py = int(x) + dx, int(y) + dy
            if 0 <= px < w and 0 <= py < h and surf.get_at((px, py)).a == 0:
                surf.set_at((px, py), jelly)
    for x, y in centres:                       # a glint on the top of each egg
        px, py = int(x), int(y) - 1
        if 0 <= px < w and 0 <= py < h and rng.random() < 0.5:
            surf.set_at((px, py), SPAWN_RIM)
    for i, (x, y) in enumerate(centres):
        if stage == 2 and i % 2:
            continue                            # hatched and gone
        px, py = int(x), int(y)
        surf.set_at((px, py), SPAWN_DOT)
        if stage >= 1:                          # a comma: a tail curling off the dot
            tx = px + (1 if i % 3 else -1)
            if 0 <= tx < w:
                surf.set_at((tx, py), SPAWN_DOT)
    return surf


# Tadpoles: a dark head and a wriggling tail, seen through the water.
TADPOLE = (26, 26, 20, 230)
TADPOLE_TAIL = (40, 42, 32, 150)


def tadpole_frames():
    """{(grown, heading left, tail up): surface}, 4 x 2 pixels: the head
    ahead, the tail flicking behind it."""
    out = {}
    for big in (False, True):
        for up in (False, True):
            surf = pygame.Surface((4, 2), pygame.SRCALPHA)
            for x in ((2, 3) if big else (2,)):
                surf.set_at((x, 0), TADPOLE)
            surf.set_at((1, 1 if up else 0), TADPOLE_TAIL)
            if big:
                surf.set_at((0, 0 if up else 1), TADPOLE_TAIL)
            out[(big, False, up)] = surf
            out[(big, True, up)] = pygame.transform.flip(surf, True, False)
    return out


# --------------------------------------------------------------------------
# Froglets: a frog the size of a fingernail (side view, facing right)

FROGLET = [None, (30, 40, 42), (52, 86, 58), (96, 142, 64), (164, 192, 90), (18, 16, 16)]
FL_OUT, FL_DARK, FL_BASE, FL_LIGHT, FL_EYE = range(1, 6)
FROGLET_ANCHOR = (4, 5)


def _froglet(stretch=0.0, crouch=0.0):
    c = Canvas(9, 7)
    g = 5.6
    if stretch:
        c.paint(c.capsule(1.0, g - 0.4 - stretch, 3.4, g - 1.4, 0.55), FL_DARK)          # legs kicking out behind
    else:
        c.paint(c.ellipse(3.0, g - 0.9 + crouch * 0.2, 1.4, 0.8), FL_DARK)              # folded hind leg
    by = g - 1.7 + crouch * 0.3 - stretch * 0.8
    c.paint(c.ellipse(4.4, by, 2.2 + stretch * 0.5, 1.3, 14 - stretch * 18), FL_BASE)    # body
    c.paint(c.ellipse(6.0 + stretch * 0.8, by - 0.5, 1.2, 1.0), FL_BASE)                 # head
    c.paint(c.ellipse(5.7 + stretch * 0.8, by - 1.3, 0.7, 0.6), FL_BASE)                  # the eye's bump
    grid = c.resolve(len(FROGLET))
    grid = shade(grid, {FL_BASE: (FL_LIGHT, FL_DARK)})
    ex, ey = int(5.9 + stretch * 0.8), int(by - 1.3)
    if 0 <= ex < 9 and 0 <= ey < 7:
        grid[ey, ex] = FL_EYE
    grid = outline(grid, FL_OUT)
    grid = despeckle(grid, keep=(FL_OUT, FL_EYE))
    return to_surface(grid, FROGLET)


def froglet_frames():
    return {"sit": [_froglet(), _froglet(crouch=0.6)], "hop": [_froglet(crouch=1.0), _froglet(stretch=1.0),
                                                              _froglet(stretch=0.6), _froglet(crouch=0.4)]}


# --------------------------------------------------------------------------
# Birds high overhead, seen from below (in the pond) and as shadows

HEADINGS = 16
SS = 8

# Seen in the water: a little darker and bluer than the birds themselves.
STORK_COLOURS = {"white": (196, 208, 212), "black": (30, 34, 44), "red": (176, 74, 60)}
GOOSE_COLOURS = {"body": (126, 118, 106), "belly": (168, 162, 148), "wing": (104, 98, 92), "edge": (72, 68, 66),
                 "bill": (196, 132, 82)}


def _poly(d, pts, fill):
    d.polygon([(x * SS, y * SS) for x, y in pts], fill=fill)


def _line(d, a, b, width, fill):
    d.line([(a[0] * SS, a[1] * SS), (b[0] * SS, b[1] * SS)], fill=fill, width=max(1, int(width * SS)))


def _frame(size, painter, crisp=True):
    """Draw at 8x and bring it down: crisp (majority colour, for
    reflections) or soft (an averaged multiply sprite, for shadows)."""
    big = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    painter(ImageDraw.Draw(big))
    if crisp:
        small = big.resize((size, size), Image.BOX)
        px = small.load()
        for y in range(size):
            for x in range(size):
                r, g, b, a = px[x, y]
                px[x, y] = (r, g, b, 225) if a > 100 else (0, 0, 0, 0)
        return pygame.image.frombuffer(small.tobytes(), small.size, "RGBA").copy()
    small = big.resize((size, size), Image.BOX)
    out = pygame.Surface((size, size))
    out.fill((255, 255, 255))
    px = small.load()
    for y in range(size):
        for x in range(size):
            a = px[x, y][3] / 255.0
            if a > 0.02:
                v = int(255 - a * (255 - px[x, y][0]))
                out.set_at((x, y), (v, v, v))
    return out


def _basis(heading, size):
    c = size / 2
    fx, fy = math.cos(heading), math.sin(heading) * 0.8       # forward (the ground is seen a little squashed)
    sx, sy = -math.sin(heading), math.cos(heading) * 0.8      # to the bird's right

    def at(f, s):
        return c + fx * f + sx * s, c + fy * f + sy * s
    return at


def stork_reflection(heading, span=11.0):
    """A white stork soaring, from below: long straight wings, white in
    front and black behind, the neck out, red bill and legs trailing."""
    k = span / 11.0
    size = int(span + 5)

    def paint(d):
        at = _basis(heading, size)
        half = span / 2
        for side in (-1, 1):
            root_f, root_b = at(1.0 * k, 0), at(-1.0 * k, 0)
            tip_f, tip_b = at(0.6 * k, side * half), at(-0.9 * k, side * half)
            mid_f, mid_b = at(0.0, side * half * 0.5), at(-0.2 * k, 0)
            _poly(d, [root_f, tip_f, tip_b, root_b], STORK_COLOURS["black"])     # the whole wing...
            _poly(d, [root_f, tip_f, at(0.0, side * half), mid_f, mid_b], STORK_COLOURS["white"])   # ...white in front
        _line(d, at(2.0 * k, 0), at(-2.4 * k, 0), 1.3 * k, STORK_COLOURS["white"])     # body and neck
        _line(d, at(2.0 * k, 0), at(3.4 * k, 0), 0.6, STORK_COLOURS["red"])           # bill
        _line(d, at(-2.4 * k, 0), at(-3.8 * k, 0), 0.6, STORK_COLOURS["red"])         # legs
    return _frame(size, paint)


def goose_reflection(heading, beat, span=9.0):
    """A goose from below, wings at ``beat`` (0 up, 0.5 level, 1 down):
    grey-brown, a pale belly, dark trailing edges, the neck stretched out."""
    k = span / 9.0
    size = int(span + 5)
    reach = span / 2 * (0.62 + 0.38 * math.sin(math.pi * beat))     # foreshortened at the top and bottom of a beat

    def paint(d):
        at = _basis(heading, size)
        for side in (-1, 1):
            _poly(d, [at(0.8 * k, 0), at(0.1 * k, side * reach), at(-0.8 * k, side * reach * 0.94), at(-0.9 * k, 0)],
                  GOOSE_COLOURS["edge"])
            _poly(d, [at(0.8 * k, 0), at(0.1 * k, side * reach), at(-0.3 * k, side * reach * 0.9), at(-0.2 * k, 0)],
                  GOOSE_COLOURS["wing"])
        _line(d, at(1.6 * k, 0), at(-2.2 * k, 0), 1.5 * k, GOOSE_COLOURS["body"])
        _line(d, at(-0.4 * k, 0), at(-1.8 * k, 0), 1.0 * k, GOOSE_COLOURS["belly"])
        _line(d, at(1.6 * k, 0), at(3.2 * k, 0), 0.8 * k, GOOSE_COLOURS["body"])     # neck
        _line(d, at(3.2 * k, 0), at(3.9 * k, 0), 0.6, GOOSE_COLOURS["bill"])
    return _frame(size, paint)


def stork_shadow(heading, span=14.0):
    size = int(span + 5)

    def paint(d):
        at = _basis(heading, size)
        dark = (196, 196, 196, 255)
        for side in (-1, 1):
            _poly(d, [at(1.1, 0), at(0.6, side * span / 2), at(-1.0, side * span / 2), at(-1.1, 0)], dark)
        _line(d, at(3.6, 0), at(-4.0, 0), 1.4, dark)
    return _frame(size, paint, crisp=False)


def goose_shadow(heading, beat, span=10.0):
    size = int(span + 5)
    reach = span / 2 * (0.62 + 0.38 * math.sin(math.pi * beat))

    def paint(d):
        at = _basis(heading, size)
        dark = (188, 188, 188, 255)
        for side in (-1, 1):
            _poly(d, [at(0.9, 0), at(0.1, side * reach), at(-0.9, side * reach * 0.94), at(-1.0, 0)], dark)
        _line(d, at(3.6, 0), at(-2.4, 0), 1.5, dark)
    return _frame(size, paint, crisp=False)


_SKY = {}


def heading_index(heading):
    return int(round(heading / (2 * math.pi) * HEADINGS)) % HEADINGS


def sky_sprites(kind):
    """{"reflection": [[frames] per heading], "far": ..., "shadow": ...} for
    "stork" or "goose", drawn once."""
    hit = _SKY.get(kind)
    if hit is None:
        angles = [2 * math.pi * i / HEADINGS for i in range(HEADINGS)]
        if kind == "stork":
            hit = {"reflection": [[stork_reflection(a)] for a in angles],
                   "far": [[stork_reflection(a, span=8.0)] for a in angles],
                   "shadow": [[stork_shadow(a)] for a in angles]}
        else:
            beats = (0.0, 0.5, 1.0, 0.5)
            hit = {"reflection": [[goose_reflection(a, b) for b in beats] for a in angles],
                   "far": [[goose_reflection(a, b, span=7.0) for b in beats] for a in angles],
                   "shadow": [[goose_shadow(a, b) for b in beats] for a in angles]}
        _SKY[kind] = hit
    return hit
