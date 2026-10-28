"""Sprites for the meadow's wildlife.

Small, high-silhouette creatures are drawn pixel by pixel (ASCII grids);
the mouse, whose shape is rounder, is drawn as supersampled ellipses and
quantised down to a limited palette with a one-pixel outline.  Colours
follow the meadow's storybook style: cool in shadow, warm in the light,
plum-tinted outlines, and dark eyes with a glint where there's room.
"""

import math

from PIL import Image, ImageDraw
import pygame

from .art import from_ascii
from .pixelrig import Canvas, despeckle, glint_eye, outline, shade, to_surface

# --------------------------------------------------------------------------
# Supersampled drawing -> limited palette -> outline

SS = 8


def _canvas(w, h):
    return Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))


def _ell(d, box, fill):
    d.ellipse([v * SS for v in box], fill=fill)


def _quantise(img, w, h, palette, outline):
    small = img.resize((w, h), Image.LANCZOS)
    px = small.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 110:
                px[x, y] = (0, 0, 0, 0)
                continue
            best = min(palette, key=lambda c: (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2)
            px[x, y] = (*best, 255)
    out = small.copy()
    op = out.load()
    for y in range(h):
        for x in range(w):
            if px[x, y][3]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and px[nx, ny][3] and px[nx, ny][:3] != (214, 150, 150):
                    op[x, y] = (*outline, 255)
                    break
    return pygame.image.frombuffer(out.tobytes(), out.size, "RGBA").copy()


# --------------------------------------------------------------------------
# Mouse (side view, facing right)

MOUSE_FUR = [(124, 108, 100), (170, 150, 128), (86, 74, 84)]   # fur, warm light, cool shade
MOUSE_PINK = (214, 150, 150)
MOUSE_EYE = (14, 10, 14)
MOUSE_SHINE = (236, 240, 240)
MOUSE_OUTLINE = (46, 32, 46)


def _mouse(body_lift=0.0, legs=0, sit_up=False, nose=0):
    w, h = 16, 11
    img = _canvas(w, h)
    d = ImageDraw.Draw(img)
    fur, light, dark = MOUSE_FUR
    lift = body_lift
    if sit_up:
        _ell(d, (4.5, 2.6 - lift, 10.5, 9.6 - lift), (*fur, 255))        # upright body
        _ell(d, (5.5, 3.4, 9.6, 7.4), (*light, 255))                    # belly
        _ell(d, (7.4, 0.6, 12.0, 4.8), (*fur, 255))                     # head
        _ell(d, (7.0, 0.0, 9.4, 2.4), (*light, 255))                    # ear
        d.line([(5 * SS, 9 * SS), (1 * SS, 9.6 * SS)], fill=(*MOUSE_PINK, 255), width=int(SS * 0.9))
        _ell(d, (6.0, 8.8, 8.0, 10.4), (*dark, 255))                    # haunch
    else:
        _ell(d, (3.0, 4.2 - lift, 11.6, 9.4 - lift), (*fur, 255))         # body
        _ell(d, (4.2, 4.4 - lift, 9.8, 6.6 - lift), (*light, 255))        # back highlight
        _ell(d, (9.4, 3.8 - lift, 14.4 + nose * 0.4, 8.2 - lift), (*fur, 255))  # head
        _ell(d, (9.2, 2.4 - lift, 11.8, 5.2 - lift), (*light, 255))       # ear
        d.line([(3.2 * SS, (7.4 - lift) * SS), (0.2 * SS, (5.6 - lift) * SS)],
               fill=(*MOUSE_PINK, 255), width=int(SS * 0.9))            # tail
        for i, fx in enumerate((4.6, 7.2, 10.0)):
            off = 0.9 if ((i % 2 == 0) == bool(legs)) else 0.0
            _ell(d, (fx, 8.6 - lift + off - 0.6, fx + 1.8, 10.2 - lift + off - 0.4), (*dark, 255))
    surf = _quantise(img, w, h, [fur, light, dark, MOUSE_PINK], MOUSE_OUTLINE)
    # Eye and nose: placed by hand so they never blur away.
    if sit_up:
        surf.set_at((10, 2), MOUSE_EYE)
        surf.set_at((10, 1), MOUSE_SHINE)
        surf.set_at((12, 3), MOUSE_PINK)
    else:
        ey = int(round(5.4 - lift))
        surf.set_at((12, ey), MOUSE_EYE)            # a beady eye with a glint above
        surf.set_at((12, ey - 1), MOUSE_SHINE)
        surf.set_at((14 + nose, ey + 1), MOUSE_PINK)
    return surf


def mouse_frames():
    return {
        "run": [_mouse(0.6, 0), _mouse(0.0, 1)],
        "idle": [_mouse(0.0, 0, nose=0), _mouse(0.0, 0, nose=1)],
        "sit": [_mouse(sit_up=True)],
    }


# --------------------------------------------------------------------------
# Butterflies (top-down; wings open, half, closed)

BUTTERFLY_FRAMES = [
    ["...a.a...",
     ".tt...tt.",
     "tWWW.WWWt",
     "tWWWbWWWt",
     ".WWWbWWW.",
     "..wWbWw..",
     "..ww.ww.."],
    ["...a.a...",
     "..t...t..",
     "..WW.WW..",
     "..WWbWW..",
     "..WWbWW..",
     "...wbw...",
     "...w.w..."],
    ["...a.a...",
     ".........",
     "....W....",
     "...WbW...",
     "...WbW...",
     "....b....",
     "........."],
]

BUTTERFLY_SPECIES = {
    "white": {"W": (238, 238, 230), "w": (212, 214, 206), "t": (78, 78, 86)},
    "brimstone": {"W": (242, 224, 98), "w": (214, 194, 70), "t": (176, 150, 50)},
    "orange": {"W": (236, 132, 46), "w": (196, 96, 36), "t": (40, 30, 30)},
    "blue": {"W": (120, 160, 236), "w": (88, 120, 210), "t": (58, 70, 140)},
}
# Seen once in a long while; never picked at random.
GOLDEN = {"W": (255, 222, 96), "w": (240, 176, 52), "t": (255, 246, 190)}


def golden_butterfly_frames():
    colors = dict(GOLDEN)
    colors["b"] = (90, 60, 30)
    colors["a"] = (120, 90, 40)
    return [from_ascii(rows, colors) for rows in BUTTERFLY_FRAMES]


# --------------------------------------------------------------------------
# Bat (seen from above): wings up, level, down

BAT_FRAMES = [
    ["w.....w",
     "ww.b.ww",
     ".wbbbw.",
     "...b..."],
    [".......",
     "wwwbwww",
     ".wbbbw.",
     "...b..."],
    [".......",
     "...b...",
     "wwbbbww",
     "w..b..w"],
]
BAT_COLORS = {"w": (46, 38, 44), "b": (28, 22, 28)}


def bat_frames():
    return [from_ascii(rows, BAT_COLORS) for rows in BAT_FRAMES]


# --------------------------------------------------------------------------
# A carved pumpkin (late October): the face glows at night

PUMPKIN = [
    "....s....",
    "..ooOoo..",
    ".oOoOoOo.",
    "oOfOoOfOo",
    "oOoOoOoOo",
    "oOffffOOo",
    ".ooOoOoo.",
    "..ooooo..",
]
PUMPKIN_COLORS = {"s": (70, 96, 44), "o": (196, 98, 32), "O": (230, 132, 42), "f": (60, 30, 16)}
PUMPKIN_LIT = dict(PUMPKIN_COLORS, f=(255, 210, 90))


def pumpkin_frames():
    return [from_ascii(PUMPKIN, PUMPKIN_COLORS), from_ascii(PUMPKIN, PUMPKIN_LIT)]


def butterfly_frames(species):
    colors = dict(BUTTERFLY_SPECIES[species])
    colors["b"] = (40, 34, 40)
    colors["a"] = (60, 52, 58)
    return [from_ascii(rows, colors) for rows in BUTTERFLY_FRAMES]


# --------------------------------------------------------------------------
# Ladybird (top-down, heading up); rotated for the other headings

LADYBUG = [".hh.",
           "rkRr",
           "RRRR",
           "rRkR",
           ".rr."]
LADYBUG_COLORS = {"h": (22, 18, 22), "R": (220, 52, 42), "r": (166, 34, 32), "k": (22, 18, 22)}


def ladybug_frames():
    up = from_ascii(LADYBUG, LADYBUG_COLORS)
    up.set_at((1, 0), (236, 236, 236))
    return {"up": up,
            "left": pygame.transform.rotate(up, 90),
            "down": pygame.transform.rotate(up, 180),
            "right": pygame.transform.rotate(up, 270)}


# --------------------------------------------------------------------------
# Dragonfly (top-down, heading up); two wing positions

DRAGONFLY = [
    ["......h......",
     ".wwww.t.wwww.",
     "wwwwwwtwwwwww",
     ".www..t..www.",
     "..wwwwtwwww..",
     "......a......",
     "......a......",
     "......a......",
     "......A......",
     "......a......"],
    ["......h......",
     "......t......",
     ".wwwwwtwwwww.",
     "wwwwwwtwwwwww",
     "..www.t.www..",
     "..wwwwawwww..",
     "......a......",
     "......a......",
     "......A......",
     "......a......"],
]
DRAGONFLY_COLORS = {"h": (30, 70, 80), "t": (44, 110, 118), "a": (64, 160, 182), "A": (30, 70, 80),
                    "w": (206, 230, 236, 150)}


def dragonfly_frames():
    frames = {}
    base = [from_ascii(rows, DRAGONFLY_COLORS) for rows in DRAGONFLY]
    for heading, angle in (("up", 0), ("left", 90), ("down", 180), ("right", 270)):
        frames[heading] = [pygame.transform.rotate(f, angle) for f in base]
    return frames


# --------------------------------------------------------------------------
# Bird shadow seen from below (multiply sprite for the light map)

BIRD_SHADOW = [
    ["x.......x",
     "xx.....xx",
     ".xxx.xxx.",
     "...xxx...",
     "....x...."],
    [".........",
     "xxxx.xxxx",
     "...xxx...",
     "....x....",
     "........."],
]


def bird_shadow_frames(darkness=196):
    frames = []
    for rows in BIRD_SHADOW:
        surf = pygame.Surface((len(rows[0]), len(rows)))
        surf.fill((255, 255, 255))
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "x":
                    surf.set_at((x, y), (darkness, darkness, darkness))
        frames.append(surf)
    return frames


# --------------------------------------------------------------------------
# Posable small creatures (drawn with the same toolkit as the cat)

def _finish(c, palette, rules, features=(), keep=()):
    grid = c.resolve(len(palette))
    grid = shade(grid, rules)
    for x, y, col in features:
        xi, yi = int(math.floor(x)), int(math.floor(y))
        if 0 <= xi < c.w and 0 <= yi < c.h:
            grid[yi, xi] = col
    grid = outline(grid, 1)
    grid = despeckle(grid, keep=(1,) + tuple(keep))
    return to_surface(grid, palette)


# Frog (side view, facing right; feet on y=9 of a 16x11 canvas)
FROG = [None, (30, 40, 42), (44, 80, 62), (84, 136, 60), (158, 190, 82), (214, 208, 132), (18, 16, 16),
        (236, 240, 230), (224, 214, 150)]   # outline, cool shade, body, warm light, belly, eye, glint, sac
F_OUT, F_DARK, F_BASE, F_LIGHT, F_BELLY, F_EYE, F_SHINE, F_SAC = range(1, 9)
FROG_ANCHOR = (8, 9)


def _frog(crouch=0.0, stretch=0.0, sac=0.0, swim=False):
    c = Canvas(16, 11)
    g = 9.0
    if not swim:
        # hind leg: folded thigh and a long foot on the ground
        thigh_x = 4.6 - stretch * 2.6
        c.paint(c.capsule(4.0 - stretch * 4.0, g - 0.6 - stretch * 1.4, 7.0, g - 0.6, 0.7), F_DARK)
        c.paint(c.ellipse(thigh_x + 1.0, g - 2.2 + crouch * 0.4, 2.4, 1.6 - stretch * 0.4, -10 - stretch * 30), F_BASE)
    body_y = g - 3.0 + crouch * 0.6 - stretch * 1.2
    c.paint(c.ellipse(7.4, body_y, 4.2 + stretch * 0.8, 2.6, 18 - stretch * 22), F_BASE)
    c.paint(c.ellipse(8.4, body_y + 1.2, 3.0, 1.2, 10), F_BELLY)
    head = (10.8 + stretch * 1.6, body_y - 1.0 - stretch * 0.6)
    c.paint(c.ellipse(head[0], head[1], 2.6, 1.8, 6), F_BASE)
    c.paint(c.ellipse(head[0] - 0.4, head[1] - 1.4, 1.2, 1.1), F_BASE)            # eye bump
    if sac > 0:
        c.paint(c.ellipse(head[0] + 0.4, head[1] + 1.6, 1.0 + sac * 1.4, 0.6 + sac * 1.2), F_SAC)
    if not swim:
        c.paint(c.capsule(9.6 + stretch, body_y + 1.4, 10.4 + stretch * 3.0, g - 0.5 - stretch * 1.0, 0.6), F_BASE)
    if swim:
        c.idx[int((g - 3.4) * c.ss):, :] = 0          # below the waterline
    features = [(head[0] - 0.6, head[1] - 1.6, F_EYE), (head[0] - 0.9, head[1] - 1.9, F_SHINE)]
    return _finish(c, FROG, {F_BASE: (F_LIGHT, F_DARK)}, features, keep=(F_EYE, F_SHINE, F_SAC))


def frog_frames():
    return {
        "sit": [_frog(), _frog(crouch=0.25)],                 # breathing
        "croak": [_frog(sac=0.4), _frog(sac=1.0), _frog(sac=1.0), _frog(sac=0.4)],
        "hop": [_frog(crouch=0.8), _frog(stretch=1.0), _frog(stretch=0.6), _frog(crouch=0.5)],
        "swim": [_frog(swim=True)],
    }


# Hedgehog (side view, facing right; 20x13 canvas, feet on y=11)
HOG = [None, (44, 28, 38), (70, 52, 56), (118, 92, 66), (158, 130, 96), (214, 184, 136), (20, 14, 18),
       (214, 198, 176), (236, 240, 240)]   # outline, cool shade, spines, light, warm tips, eye, face, glint
H_OUT, H_DARK, H_BASE, H_LIGHT, H_TIP, H_EYE, H_FACE, H_SHINE = range(1, 9)
HOG_ANCHOR = (10, 11)


def _hedgehog(step=0.0, sniff=0.0, ball=False):
    c = Canvas(20, 13)
    g = 11.0
    if ball:
        c.paint(c.ellipse(10.0, g - 3.6, 4.6, 3.8), H_BASE)
        spikes = c.covered()
        for i in range(11):
            a = math.pi * (0.95 + i * 0.13)
            x0, y0 = 10.0 + math.cos(a) * 3.6, g - 3.6 + math.sin(a) * 3.0
            x1, y1 = 10.0 + math.cos(a) * 5.6, g - 3.6 + math.sin(a) * 5.0
            spikes |= c.capsule(x0, y0, x1, y1, 0.55, 0.2)
        c.paint(spikes, H_BASE)
        c.paint(c.ellipse(11.4, g - 2.0, 1.6, 1.0), H_FACE)
        return _finish(c, HOG, {H_BASE: (H_TIP, H_DARK)}, [(12.0, g - 2.6, H_EYE)], keep=(H_EYE,))
    for i, fx in enumerate((6.0, 12.0)):
        lift = step if i == 0 else -step
        c.paint(c.capsule(fx, g - 2.0, fx + lift * 0.8, g - 0.5 - max(0.0, lift) * 0.6, 0.7), H_DARK)
    c.paint(c.ellipse(13.4, g - 3.0, 3.2, 2.2, -8), H_FACE)                      # face and belly fur
    c.paint(c.ellipse(15.6 + sniff * 0.4, g - 2.4 + sniff * 0.4, 2.0, 1.0, -14), H_FACE)  # snout
    back = c.ellipse(9.0, g - 3.4, 6.0, 3.8)
    spikes = back.copy()
    for i in range(12):
        a = math.pi * (1.02 + i * 0.085)
        x0, y0 = 9.0 + math.cos(a) * 4.6, g - 3.4 + math.sin(a) * 2.8
        x1, y1 = 9.0 + math.cos(a) * 7.0 - 0.8, g - 3.4 + math.sin(a) * 4.8
        spikes |= c.capsule(x0, y0, x1, y1, 0.6, 0.2)
    spikes &= c.below(g - 9.5) & ~c.below(g - 1.2)
    c.paint(spikes, H_BASE)
    features = [(17.4 + sniff * 0.4, g - 2.6 + sniff * 0.4, H_EYE)]        # nose
    glint_eye(c, features, 13.6, g - 4.6, 1.0, H_EYE, H_SHINE)              # a beady eye
    return _finish(c, HOG, {H_BASE: (H_TIP, H_DARK)}, features, keep=(H_EYE, H_SHINE))


def hedgehog_frames():
    return {
        "walk": [_hedgehog(step=s) for s in (0.0, 1.0, 0.0, -1.0)],
        "sniff": [_hedgehog(sniff=0.0), _hedgehog(sniff=1.0)],
        "ball": [_hedgehog(ball=True)],
    }


# Snail (side view, facing right; 10x7, foot on y=6)
SNAIL = [None, (46, 30, 40), (104, 66, 56), (170, 116, 66), (222, 172, 104), (176, 160, 140),
         (218, 204, 184), (24, 18, 22)]   # outline, cool shell shade, shell, warm shell light, body, body light, eye
S_OUT, S_SHELL_D, S_SHELL, S_SHELL_L, S_BODY, S_BODY_L, S_EYE = range(1, 8)
SNAIL_ANCHOR = (6, 6)


def _snail(stretch=0.0, tucked=False):
    c = Canvas(13, 7)
    if not tucked:
        c.paint(c.capsule(1.4, 5.3, 9.2 + stretch, 5.3, 0.9, 0.8), S_BODY)
        c.paint(c.capsule(9.0 + stretch, 5.0, 10.2 + stretch, 2.0, 0.4), S_BODY)
    c.paint(c.ellipse(4.4, 3.4, 2.9, 2.6), S_SHELL)
    c.paint(c.ellipse(4.7, 3.2, 1.5, 1.3), S_SHELL_D)
    c.paint(c.ellipse(4.6, 3.1, 0.7, 0.6), S_SHELL)
    features = [] if tucked else [(10.2 + stretch, 1.8, S_EYE)]
    return _finish(c, SNAIL, {S_SHELL: (S_SHELL_L, None), S_BODY: (S_BODY_L, None)}, features, keep=(S_EYE, S_SHELL_D))


def snail_frames():
    return {"crawl": [_snail(0.0), _snail(0.5), _snail(1.0), _snail(0.5)], "tucked": [_snail(tucked=True)]}


# Bee: three body pixels and flickering wings
def bee_frames():
    frames = []
    for wing in (0, 1):
        s = pygame.Surface((4, 3), pygame.SRCALPHA)
        s.fill((0, 0, 0, 0))
        s.set_at((0, 2), (40, 30, 20))
        s.set_at((1, 2), (238, 196, 60))
        s.set_at((2, 2), (40, 30, 20))
        s.set_at((3, 2), (238, 196, 60))
        if wing:
            s.set_at((1, 1), (230, 236, 240, 200))
            s.set_at((2, 1), (230, 236, 240, 200))
        else:
            s.set_at((1, 0), (230, 236, 240, 170))
            s.set_at((2, 1), (230, 236, 240, 200))
        frames.append(s)
    return frames



# --------------------------------------------------------------------------
# Moth: a butterfly's shape in soft night browns

MOTH = {"W": (198, 188, 164), "w": (160, 150, 128), "t": (112, 100, 86)}


def moth_frames():
    colors = dict(MOTH)
    colors["b"] = (84, 74, 64)
    colors["a"] = (120, 108, 94)
    return [from_ascii(rows, colors) for rows in BUTTERFLY_FRAMES]


# --------------------------------------------------------------------------
# Grasshopper (side view, facing right): sitting, and legs out mid-hop

GRASSHOPPER = [
    ["..aa..",
     "gGGGGe",
     ".l..l."],
    ["..a...",
     "gGGGGe",
     "l....l"],
]
GRASSHOPPER_COLORS = {"g": (92, 140, 48), "G": (126, 176, 64), "e": (40, 46, 24), "a": (150, 190, 90),
                      "l": (78, 112, 40)}


def grasshopper_frames():
    return [from_ascii(rows, GRASSHOPPER_COLORS) for rows in GRASSHOPPER]



# --------------------------------------------------------------------------
# Things Mochi carries and wears

GIFTS = {
    "leaf": (["..O", ".oO", "o.."], {"O": (214, 146, 58), "o": (160, 88, 40)}),
    "feather": (["wWWW"], {"W": (230, 230, 236), "w": (150, 150, 166)}),
    "toy mouse": (["..gg", "tgGp"], {"g": (146, 146, 158), "G": (176, 176, 186), "p": (232, 150, 164),
                                      "t": (120, 120, 130)}),
}
BOW = ["r.r", "rRr"]
BOW_COLORS = {"r": (226, 62, 78), "R": (150, 30, 44)}


def gift_frames():
    return {name: from_ascii(rows, colors) for name, (rows, colors) in GIFTS.items()}


def bow_frame():
    return from_ascii(BOW, BOW_COLORS)
