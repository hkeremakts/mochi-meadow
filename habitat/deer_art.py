"""A roe deer, drawn from a posable puppet (side view, facing right).

Like the fox it shares the cat's pose conventions (paws ``fn``/``ff``/
``hn``/``hf``, ground at y = 48), so the cat's gait generator walks it,
but it stands far taller: a roe deer is about 70 cm at the shoulder to
the cat's 25, so the body sits high on long, thin legs and the canvas
reaches well above the cat's.
"""

import math

from . import cat_anims
from .pixelrig import Canvas, Pose, ease, outline, rot, shade, to_surface, two_bone

GROUND = cat_anims.GROUND
CX = 42.0
SCALE = 1.12
HEADROOM = 40        # rows above y = 0 in pose space: the deer stands tall
SHIFT_X = 10
W, H = 104, 98
ANCHOR = (int(CX) + SHIFT_X, int(GROUND) + HEADROOM)

CLEAR, OUT, DEEP, DARK, BASE, LIGHT, WHITE, WHITE_SH, HOOF, NOSE, EYE, EAR_IN = range(12)
PALETTE = [
    None,
    (52, 36, 26),       # OUT
    (98, 64, 42),       # DEEP
    (126, 86, 58),      # DARK    far legs, belly shade
    (160, 112, 74),     # BASE    russet-brown coat
    (190, 144, 100),    # LIGHT   lit back
    (236, 228, 214),    # WHITE   rump patch, throat, muzzle
    (196, 184, 168),    # WHITE_SH
    (40, 30, 26),       # HOOF
    (28, 22, 20),       # NOSE
    (30, 22, 18),       # EYE
    (210, 170, 150),    # EAR_IN
]
SHADE_RULES = {BASE: (LIGHT, DARK), WHITE: (None, WHITE_SH)}

UPPER, LOWER = 14.5, 14.0
STAND = Pose(
    hip=(22.0, 12.0), sho=(52.0, 12.5),
    haunch=(8.6, 8.2), chest=(7.6, 8.8), torso=7.4,
    neck=(59.0, 1.0), head=(65.0, -9.5), tilt=0.0,
    fn=(53.5, GROUND), ff=(50.0, GROUND), hn=(24.5, GROUND), hf=(21.0, GROUND),
    fn_rot=0.0, ff_rot=0.0, hn_lift=0.0, hf_lift=0.0,
    tail=0.0, ear=0.0, eye=1.0, chew=0.0,
)


def canvas():
    return Canvas(W, H, scale=SCALE, pivot=(CX, GROUND), shift=(SHIFT_X, HEADROOM))


def _floor(pt, r):
    return (pt[0], min(pt[1], GROUND - r))


def _foreleg(c, root, paw, rot_deg):
    px, py = paw
    wx, wy = rot(-0.3, -5.5, rot_deg)
    knee = _floor((px + wx, py + wy), 0.9)        # the deer's "knee" is its wrist
    elbow = _floor(two_bone(root, knee, UPPER * 0.62, UPPER * 0.55, bend=-1.0), 1.2)
    leg = c.chain([root, elbow, knee], [2.6, 1.3, 1.0])
    tx, ty = rot(0.4, -0.8, rot_deg)
    toe = _floor((px + tx, py + ty), 0.8)
    leg |= c.capsule(knee[0], knee[1], toe[0], toe[1], 0.95, 0.85)
    hoof = c.ellipse(toe[0] + 0.3, toe[1], 1.3, 0.8, rot_deg)
    return leg, hoof


def _hindleg(c, root, paw, lift):
    px, py = paw
    hx, hy = rot(-2.6, -9.0, lift)
    hock = _floor((px + hx, py + hy), 0.9)
    stifle = _floor(two_bone(root, hock, UPPER * 0.7, UPPER * 0.66, bend=1), 1.4)
    leg = c.chain([root, stifle], [3.6, 1.8]) | c.chain([stifle, hock], [1.6, 1.1])
    tx, ty = rot(0.4, -0.8, lift)
    toe = _floor((px + tx, py + ty), 0.8)
    leg |= c.capsule(hock[0], hock[1], toe[0], toe[1], 1.0, 0.85)
    hoof = c.ellipse(toe[0] + 0.3, toe[1], 1.3, 0.8, lift)
    return leg, hoof


def draw(p):
    c = canvas()
    features = []
    hx, hy = p.hip
    sx, sy = p.sho
    ang = math.degrees(math.atan2(-(sy - hy), sx - hx))
    # far legs
    for leg, hoof in (_hindleg(c, (hx + 1.0, hy + 2.0), p.hf, p.hf_lift),
                      _foreleg(c, (sx - 1.0, sy + 3.0), p.ff, p.ff_rot)):
        c.paint(leg, DARK)
        c.paint(hoof, HOOF)
    # body, with the white rump patch
    body = c.ellipse(hx, hy, p.haunch[0], p.haunch[1], ang)
    body |= c.capsule(hx, hy, sx, sy, p.torso)
    body |= c.ellipse(sx, sy, p.chest[0], p.chest[1], ang)
    c.paint(body, BASE)
    c.paint(c.ellipse(hx - 6.8, hy - 0.4, 3.2, 4.6, ang), WHITE, within=body)
    tail_tip = (hx - 8.6, hy - 2.8 - p.tail * 2.0)
    c.paint(c.capsule(hx - 7.6, hy - 2.2, tail_tip[0], tail_tip[1], 1.1, 0.8), WHITE)
    # near legs
    leg, hoof = _hindleg(c, (hx + 1.0, hy + 2.8), p.hn, p.hn_lift)
    c.part(leg, BASE, crease=DEEP, width=0.7, within=c.below(hy + 3.0))
    c.paint(hoof, HOOF)
    leg, hoof = _foreleg(c, (sx + 0.4, sy + 3.6), p.fn, p.fn_rot)
    c.part(leg, BASE, crease=DEEP, width=0.7, within=c.below(sy + 4.0))
    c.paint(hoof, HOOF)
    # neck and head
    nx, ny = p.neck
    qx, qy = p.head
    c.paint(c.chain([(sx + 2.0, sy - 2.0), (nx, ny), (qx - 1.0, qy + 1.0)], [4.6, 3.2, 2.4]), BASE)
    c.paint(c.ellipse(qx - 0.6, qy + 3.6, 1.8, 1.4, p.tilt), WHITE)                              # throat patch
    t = p.tilt

    def at(dx, dy):
        rx, ry = rot(dx, dy, t)
        return qx + rx, qy + ry

    flat = p.ear
    for off, colour in ((-1.4, DARK), (0.6, BASE)):
        base0, base1 = at(-2.6 + off - flat, -2.2 + flat), at(-0.4 + off, -2.8 + flat * 0.5)
        tip = at(-4.6 + off - flat * 3.0, -7.6 + flat * 4.0)
        c.paint(c.polygon([base0, tip, base1]), colour)
        if colour == BASE:
            c.paint(c.polygon([at(-2.2 + off - flat, -3.0 + flat), at(-4.0 + off - flat * 3.0, -6.6 + flat * 3.6),
                               at(-1.0 + off, -3.4 + flat * 0.5)]), EAR_IN)
    c.paint(c.ellipse(qx, qy, 3.4, 3.0, t), BASE)
    muzzle = [at(1.4, -1.8), at(6.8, -0.2), at(7.0, 1.6), at(1.2, 2.6)]
    c.paint(c.polygon(muzzle), BASE)
    c.paint(c.ellipse(*at(5.6, 1.4 + p.chew * 0.5), 1.6, 1.0, t), WHITE)                     # chin
    features.append((*at(6.7, 0.4), NOSE))
    features.append((*at(6.7, 1.0), NOSE))
    ex, ey = at(0.9, -0.9)
    features.append((ex, ey, EYE if p.eye > 0.5 else DEEP))
    features.append((ex + 0.9, ey, EYE if p.eye > 0.5 else DEEP))
    grid = c.resolve(len(PALETTE))
    grid = shade(grid, SHADE_RULES)
    for x, y, colour in features:
        xi, yi = (int(math.floor(v)) for v in c.to_art(x, y))
        if 0 <= xi < W and 0 <= yi < H:
            grid[yi, xi] = colour
    grid = outline(grid, OUT)
    return to_surface(grid, PALETTE)


# --- animations ---------------------------------------------------------------

WALK_STRIDE = 26.0
BOUND_STRIDE = 76.0
STRIDES = {"walk": WALK_STRIDE * SCALE, "bound": BOUND_STRIDE * SCALE}
BOUND = {"hn": 0.0, "hf": 0.05, "fn": 0.5, "ff": 0.55}


def _blend(a, b, t):
    return a.blend(b, ease(t))


def _with_neck(p, dy=0.0):
    return p.with_(neck=(p.neck[0], p.neck[1] + dy), head=(p.head[0], p.head[1] + dy))


def build():
    gait = cat_anims.side_gait
    anims = {
        "walk": [_with_neck(gait(STAND, i / 8, WALK_STRIDE, 0.66, 4.0, cat_anims.WALK_LATERAL, bob=0.5,
                                 tail_sway=0.0), 0.6 * math.sin(i / 8 * math.tau * 2)) for i in range(8)],
        "bound": [gait(STAND.with_(tail=1.0, ear=0.4), i / 6, BOUND_STRIDE, 0.34, 7.0, BOUND, bob=2.2,
                       tail_sway=0.0) for i in range(6)],
    }
    anims["stand"] = [STAND, STAND, STAND.with_(ear=0.25), STAND, STAND.with_(tail=0.4), STAND]
    graze = STAND.with_(neck=(63.0, 25.0), head=(69.0, 42.5), tilt=-62.0, sho=(52.0, 14.0), ear=0.3)
    anims["graze_start"] = [_blend(STAND, graze, i / 4) for i in range(5)]
    anims["graze"] = [graze, graze.with_(chew=1.0), graze, graze.with_(chew=1.0, head=(69.4, 42.5))]
    anims["graze_end"] = [_blend(graze, STAND, i / 3) for i in range(4)]
    alert = STAND.with_(neck=(58.0, -2.0), head=(63.0, -13.5), tilt=10.0, ear=-0.4, tail=0.6)
    anims["alert"] = [_blend(STAND, alert, i / 2) for i in range(3)] + [alert] * 3
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
