"""A red fox, drawn from a posable puppet (side view, facing right).

It shares the cat's pose conventions (paws ``fn``/``ff``/``hn``/``hf``,
``hip``, ``sho``, ``head``, ground at y = 48), so the cat's gait generator
drives its legs too: a fox trots on the diagonal, planted paws still.

Proportions are true to the cat: about half as long again nose to tail,
taller in the leg, with a long brush of a tail.
"""

import math

from . import cat_anims
from .pixelrig import Canvas, Pose, ease, outline, rot, shade, to_surface, two_bone

W, H = 88, 56
GROUND = cat_anims.GROUND
CX = 40.0
SCALE = 1.12
SHIFT = 8             # canvas columns to the left of the pose space, for the brush
ANCHOR = (int(CX) + SHIFT, int(GROUND))

CLEAR, OUT, DEEP, DARK, BASE, LIGHT, WHITE, WHITE_SH, BLACK, BLACK_L, NOSE, EYE = range(12)
PALETTE = [
    None,
    (54, 28, 20),       # OUT
    (122, 54, 26),      # DEEP
    (164, 74, 32),      # DARK    far side
    (208, 106, 46),     # BASE    russet coat
    (234, 144, 72),     # LIGHT   lit back
    (240, 232, 218),    # WHITE   chin, chest, tail tip
    (204, 192, 176),    # WHITE_SH
    (44, 32, 30),       # BLACK   stockings, ear backs
    (78, 60, 54),       # BLACK_L
    (26, 20, 20),       # NOSE
    (46, 30, 18),       # EYE
]
SHADE_RULES = {BASE: (LIGHT, DARK), WHITE: (None, WHITE_SH), BLACK: (BLACK_L, None)}

STAND = Pose(
    hip=(32.0, 30.5), sho=(49.5, 30.0),
    haunch=(6.0, 5.4), chest=(5.4, 6.6), torso=4.6,
    head=(59.5, 21.0), tilt=0.0, snout=1.0,
    fn=(51.0, GROUND), ff=(48.0, GROUND), hn=(33.0, GROUND), hf=(30.0, GROUND),
    fn_rot=0.0, ff_rot=0.0, hn_lift=0.0, hf_lift=0.0,
    tail=204.0, droop=-2.4, ear=0.0, eye=1.0,
)


def canvas():
    return Canvas(W, H, scale=SCALE, pivot=(CX, GROUND), shift=(SHIFT, 0))


def _floor(pt, r):
    return (pt[0], min(pt[1], GROUND - r))


def _foreleg(c, root, paw, rot_deg):
    px, py = paw
    wx, wy = rot(-0.2, -2.8, rot_deg)
    wrist = _floor((px + wx, py + wy), 1.1)
    elbow = _floor(two_bone(root, wrist, 7.4, 7.0, bend=-1.0), 1.3)
    fur = c.chain([root, elbow], [2.1, 1.4])
    stocking = c.chain([elbow, wrist], [1.35, 1.05])
    tx, ty = rot(0.6, -0.9, rot_deg)
    toe = _floor((px + tx, py + ty), 1.0)
    stocking |= c.capsule(wrist[0], wrist[1], toe[0], toe[1], 1.05) | c.ellipse(toe[0], toe[1], 1.6, 1.0, rot_deg)
    return fur, stocking


def _hindleg(c, root, paw, lift):
    px, py = paw
    hx, hy = rot(-2.6, -5.0, lift)
    hock = _floor((px + hx, py + hy), 1.1)
    knee = _floor(two_bone(root, hock, 7.6, 7.0, bend=1), 1.4)
    fur = c.chain([root, knee], [2.6, 1.6]) | c.chain([knee, hock], [1.6, 1.2])
    tx, ty = rot(0.6, -0.9, lift)
    toe = _floor((px + tx, py + ty), 1.0)
    stocking = c.capsule(hock[0], hock[1], toe[0], toe[1], 1.1, 1.0) | c.ellipse(toe[0], toe[1], 1.7, 1.0, lift)
    return fur, stocking


def _tail(c, p):
    hx, hy = p.hip
    root = (hx - 4.4, hy - 1.6)
    pts = [root]
    a = p.tail
    x, y = root
    for i in range(9):
        a += p.droop if i < 5 else p.droop * 0.4
        x += math.cos(math.radians(a)) * 2.2
        y = min(GROUND - 5.0, y - math.sin(math.radians(a)) * 2.2)
        pts.append((x, y))
    radii = [2.0, 3.0, 3.8, 4.2, 4.4, 4.3, 4.0, 3.5, 2.7, 1.6]
    brush = c.chain(pts, radii)
    tip = c.chain(pts[-3:], radii[-3:])
    return brush, tip


def draw(p):
    c = canvas()
    features = []
    hx, hy = p.hip
    sx, sy = p.sho
    ang = math.degrees(math.atan2(-(sy - hy), sx - hx))
    # far legs, then the tail
    fur, stock = _hindleg(c, (hx + 1.0, hy + 1.0), p.hf, p.hf_lift)
    c.paint(fur, DARK)
    c.paint(stock, BLACK)
    fur, stock = _foreleg(c, (sx - 0.6, sy + 2.0), p.ff, p.ff_rot)
    c.paint(fur, DARK)
    c.paint(stock, BLACK)
    brush, tip = _tail(c, p)
    c.paint(brush, BASE)
    c.paint(tip, WHITE)
    # body
    body = c.ellipse(hx, hy, p.haunch[0], p.haunch[1], ang)
    body |= c.capsule(hx, hy, sx, sy, p.torso)
    body |= c.ellipse(sx, sy, p.chest[0], p.chest[1], ang)
    c.paint(body, BASE)
    c.paint(c.ellipse(sx + 3.2, sy + 1.6, 2.8, 4.6, ang + 15), WHITE, within=body)     # chest
    # near legs
    fur, stock = _hindleg(c, (hx + 1.0, hy + 1.8), p.hn, p.hn_lift)
    c.part(fur, BASE, crease=DEEP, width=0.7, within=c.below(hy + 2.0))
    c.paint(stock, BLACK)
    fur, stock = _foreleg(c, (sx + 0.6, sy + 2.6), p.fn, p.fn_rot)
    c.part(fur, BASE, crease=DEEP, width=0.7, within=c.below(sy + 3.0))
    c.paint(stock, BLACK)
    # neck and head
    qx, qy = p.head
    c.paint(c.capsule(sx + 1.0, sy - 1.6, qx - 1.0, qy + 1.4, 3.8, 2.8), BASE)
    t = p.tilt

    def at(dx, dy):
        rx, ry = rot(dx, dy, t)
        return qx + rx, qy + ry

    flat = p.ear
    for near, colour in ((False, BLACK), (True, BLACK)):
        off = 1.6 if near else -1.2
        b0, b1 = at(-2.8 + off - flat, -2.4 + flat), at(0.6 + off, -3.6 + flat * 0.6)
        tip_pt = at(-1.4 + off - flat * 4.0, -9.4 + flat * 5.0)
        c.paint(c.polygon([b0, tip_pt, b1]), colour if not near else BASE)
        if near:
            c.paint(c.polygon([at(-2.0 + off - flat, -4.6 + flat), tip_pt, at(-0.2 + off, -5.2 + flat)]), BLACK)
    c.paint(c.ellipse(qx, qy, 4.4, 3.9, t), BASE)
    snout = [at(1.8, -1.6), at(1.8 + 6.0 * p.snout, 0.9), at(1.6 + 5.6 * p.snout, 2.0), at(0.6, 2.8)]
    c.paint(c.polygon(snout), BASE)
    c.paint(c.polygon([at(0.4, 1.2), at(1.6 + 5.2 * p.snout, 1.8), at(1.4 + 5.0 * p.snout, 2.2),
                       at(-0.6, 3.6), at(-2.6, 2.8)]), WHITE)                                  # cheek and jaw
    c.paint(c.capsule(*at(-1.2, 3.0), sx + 4.0, sy - 0.6, 2.0, 2.6), WHITE)                    # throat
    features.append((*at(1.4 + 6.0 * p.snout, 0.6), NOSE))
    ex, ey = at(0.9, -1.0)
    features.append((ex, ey, EYE if p.eye > 0.5 else DEEP))
    features.append((ex + 0.9, ey, DEEP if p.eye > 0.5 else DEEP))
    grid = c.resolve(len(PALETTE))
    grid = shade(grid, SHADE_RULES)
    for x, y, colour in features:
        xi, yi = (int(math.floor(v)) for v in c.to_art(x, y))
        if 0 <= xi < W and 0 <= yi < H:
            grid[yi, xi] = colour
    grid = outline(grid, OUT)
    return to_surface(grid, PALETTE)


# --- animations ---------------------------------------------------------------

TROT_STRIDE = 30.0
WALK_STRIDE = 20.0
STRIDES = {"trot": TROT_STRIDE * SCALE, "walk": WALK_STRIDE * SCALE}


def _blend(a, b, t):
    return a.blend(b, ease(t))


def build():
    gait = cat_anims.side_gait
    anims = {
        "trot": [gait(STAND, i / 8, TROT_STRIDE, 0.5, 3.0, cat_anims.TROT_DIAGONAL, bob=0.5, tail_sway=3.0)
                 for i in range(8)],
        "walk": [gait(STAND, i / 8, WALK_STRIDE, 0.62, 2.4, cat_anims.WALK_LATERAL, bob=0.3, tail_sway=2.0)
                 for i in range(8)],
    }
    breathe = [STAND.with_(sho=(49.5, 30.0 - 0.3 * math.sin(i / 4 * math.pi * 2))) for i in range(4)]
    anims["stand"] = breathe
    nose_down = STAND.with_(head=(61.5, 33.5), tilt=-38.0, sho=(49.5, 31.0), tail=208.0)
    anims["sniff"] = [_blend(STAND, nose_down, i / 3) for i in range(4)] + \
                     [nose_down.with_(head=(62.0 + 0.4 * (i % 2), 33.5)) for i in range(4)] + \
                     [_blend(nose_down, STAND, i / 3) for i in range(4)]
    alert = STAND.with_(head=(58.5, 18.5), tilt=12.0, ear=-0.3, tail=196.0, droop=-1.6)
    anims["look"] = [_blend(STAND, alert, i / 3) for i in range(4)] + [alert] * 2
    return anims


def render():
    cache = {}
    out = {}
    for key, poses in build().items():
        frames = []
        for p in poses:
            k = repr(sorted(p.items()))
            if k not in cache:
                cache[k] = draw(p)
            frames.append(cache[k])
        out[key + "_right"] = frames
    return out
