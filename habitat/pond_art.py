"""Birds of the pond, drawn from posable puppets (side view, facing right):
a grey heron, and a mallard duck with her ducklings.

The heron stands about three times the cat's height, all legs and neck:
it waits at the water's edge with its neck drawn in, leans out to hunt,
strikes, swallows, and flies with its neck tucked into an S and its legs
trailing.  The duck waddles, swims low in the water (everything under the
waterline is cut away) and up-ends to feed.  Ducklings are the same
puppet, small, fluffy and yellow.
"""

import math

from .pixelrig import Canvas, Pose, ease, outline, rot, shade, to_surface

# --------------------------------------------------------------------------
# Heron

HERON_W, HERON_H = 118, 116
HERON_GROUND = 48.0
HERON_HEADROOM = 60
HERON_CX = 40.0
HERON_SCALE = 1.5
HERON_SHIFT = 14
HERON_ANCHOR = (int(HERON_CX) + HERON_SHIFT, int(HERON_GROUND) + HERON_HEADROOM)

H_CLEAR, H_OUT, H_DARK, H_BASE, H_LIGHT, H_WHITE, H_BLACK, H_BILL, H_LEG, H_EYE, H_WING = range(11)
HERON_PALETTE = [
    None,
    (40, 42, 50),       # OUT
    (88, 92, 104),      # DARK
    (138, 142, 152),    # BASE   grey back
    (172, 176, 184),    # LIGHT
    (226, 228, 230),    # WHITE  neck and face
    (30, 30, 36),       # BLACK  crest, wing tips, neck streaks
    (214, 178, 70),     # BILL   yellow dagger
    (170, 150, 96),     # LEG
    (230, 200, 60),     # EYE
    (110, 114, 126),    # WING   folded wing
]
HERON_SHADE = {H_BASE: (H_LIGHT, H_DARK), H_WHITE: (None, H_LIGHT)}

HERON_STAND = Pose(
    body=(32.0, 20.0), tilt=24.0, flying=0.0, wing_t=0.0,
    neck=((38.5, 15.0), (41.0, 9.5), (37.5, 3.5), (39.0, -2.0)), head=(41.0, -3.2), bill=10.0,
    fa=(30.0, HERON_GROUND), fb=(34.0, HERON_GROUND), knee=(0.0, 0.0),
)


def _heron_canvas():
    return Canvas(HERON_W, HERON_H, scale=HERON_SCALE, pivot=(HERON_CX, HERON_GROUND),
                  shift=(HERON_SHIFT, HERON_HEADROOM))


def draw_heron(p):
    c = _heron_canvas()
    features = []
    bx, by = p.body
    t = p.tilt

    def at(dx, dy, a=t):
        rx, ry = rot(dx, dy, a)
        return bx + rx, by + ry

    if p.flying:
        _heron_wing(c, p, at, far=True)
        # legs trailing behind
        hip = at(-4.0, 2.0)
        c.paint(c.capsule(hip[0], hip[1], hip[0] - 16.0, hip[1] + 1.4, 0.8, 0.6), H_LEG)
    else:
        for foot, shade_ in ((p.fb, H_DARK), (p.fa, H_LEG)):
            hip = at(-1.0, 3.6)
            knee = ((hip[0] + foot[0]) / 2 - 1.4 + p.knee[0], (hip[1] + foot[1]) / 2 + p.knee[1])
            c.paint(c.chain([hip, knee, (foot[0], foot[1] - 0.4)], [0.9, 0.75, 0.6]), shade_)
            c.paint(c.capsule(foot[0] - 1.6, foot[1] - 0.3, foot[0] + 2.2, foot[1] - 0.3, 0.45), shade_)
    # tail and body
    c.paint(c.polygon([at(-8.0, -2.0), at(-13.0, 0.4), at(-12.4, 2.4), at(-7.0, 2.6)]), H_DARK)
    body = c.ellipse(bx, by, 9.6, 5.2, t)
    c.paint(body, H_BASE)
    c.paint(c.ellipse(*at(2.6, 2.4), 6.6, 3.0, t), H_WHITE, within=body)       # pale breast
    if not p.flying:
        wing = c.ellipse(*at(-1.6, -1.0), 8.4, 3.8, t - 4)
        c.paint(wing, H_WING, within=c.grow(body, 0.3))
        c.paint(c.ellipse(*at(-7.6, -0.2), 3.0, 1.6, t), H_BLACK, within=wing)   # primaries
    # neck: a chain from the shoulders through the S-curve to the head
    pts = [at(6.5, -2.0)] + list(p.neck) + [p.head]
    radii = [2.6, 2.0, 1.7, 1.6, 1.5, 1.6][:len(pts)]
    neck = c.chain(pts, radii)
    c.paint(neck, H_WHITE)
    streak = c.chain(pts[1:-1], [0.45] * (len(pts) - 2))
    c.paint(streak, H_DARK, within=neck)
    hx, hy = p.head
    c.paint(c.ellipse(hx, hy, 2.4, 2.0), H_WHITE)
    # the bill's angle follows the last stretch of neck
    nx, ny = pts[-2]
    a = math.atan2(hy - ny, hx - nx) * 0.5 + p.get("bill_angle", 0.0) * math.pi / 180
    length = p.bill
    tip = (hx + 1.6 + math.cos(a) * length, hy + math.sin(a) * length)
    perp = (-math.sin(a) * 0.9, math.cos(a) * 0.9)
    c.paint(c.polygon([(hx + 1.2 - perp[0], hy - perp[1]), tip, (hx + 1.2 + perp[0], hy + perp[1])]), H_BILL)
    c.paint(c.capsule(hx - 0.4, hy - 1.2, hx - 6.0, hy - 1.8, 0.5, 0.3), H_BLACK)                # crest
    features.append((hx + 0.6, hy - 0.5, H_EYE))
    if p.flying:
        _heron_wing(c, p, at, far=False)
    return _finish(c, features, HERON_PALETTE, HERON_SHADE, H_OUT, HERON_W, HERON_H)


def _heron_wing(c, p, at, far):
    """Broad, slow, bowed wings: the far one up the screen, the near one
    down, as the meadow is seen from above at an angle."""
    beat = math.cos(2 * math.pi * p.wing_t)
    open_ = 0.5 + 0.5 * abs(beat)
    sign = -1 if far else 1
    span = (19.0 if far else 22.0) * open_
    sh = at(1.0, -1.0) if far else at(1.0, 1.0)
    wrist = (sh[0] - 2.0, sh[1] + sign * span * 0.55)
    tip = (sh[0] - 9.0, sh[1] + sign * span)
    trail = (sh[0] - 13.0, sh[1] + sign * span * 0.55)
    back = (sh[0] - 10.0, sh[1] + sign * 0.6)
    c.paint(c.polygon([sh, wrist, tip, trail, back]), H_DARK if far else H_BASE)
    c.paint(c.polygon([wrist, tip, ((tip[0] + trail[0]) / 2, (tip[1] + trail[1]) / 2)]), H_BLACK)


def heron_poses():
    s = HERON_STAND
    hunt = s.with_(tilt=14.0, neck=((40.0, 15.0), (44.0, 12.0), (47.5, 10.5), (50.0, 11.0)), head=(52.0, 12.6),
                   bill_angle=30.0, knee=(0.6, 0.6))
    strike = hunt.with_(neck=((41.0, 17.0), (45.0, 22.0), (48.5, 30.0), (51.0, 37.0)), head=(52.5, 41.0),
                        bill_angle=40.0, tilt=4.0)
    swallow = s.with_(neck=((38.5, 14.0), (40.0, 8.0), (40.5, 2.0), (41.0, -4.0)), head=(41.4, -6.4),
                      bill_angle=-110.0)
    step_a = s.with_(fa=(28.0, HERON_GROUND - 2.4), knee=(-1.0, -1.0))
    step_b = s.with_(fb=(36.5, HERON_GROUND - 2.4), body=(33.2, 20.0))
    # In flight the body keeps its standing height: the flier's ``z``
    # lifts it, so landing and taking off don't jump.
    fly = s.with_(flying=1.0, tilt=2.0, body=(40.0, 20.0),
                  neck=((46.0, 19.0), (47.0, 16.0), (49.0, 17.0), (50.0, 18.6)), head=(51.4, 18.6), bill=8.0,
                  bill_angle=10.0)
    anims = {
        "stand": [s, s.with_(head=(41.4, -3.0)), s, s.with_(head=(40.6, -3.4))],
        "walk": [s, step_a, s, step_b],
        "hunt": [s.blend(hunt, ease(i / 3)) for i in range(4)] + [hunt] * 2,
        "strike": [hunt, hunt.blend(strike, 0.6), strike, strike, strike.blend(hunt, 0.5), hunt],
        "swallow": [s.blend(swallow, ease(i / 2)) for i in range(3)] + [swallow, swallow, s],
        "fly": [fly.with_(wing_t=i / 8, body=(40.0, 20.0 + 0.8 * math.cos(2 * math.pi * i / 8))) for i in range(8)],
        "glide": [fly.with_(wing_t=0.0)],
    }
    return anims


# --------------------------------------------------------------------------
# Duck and ducklings

DUCK_W, DUCK_H = 34, 30
DUCK_GROUND = 22.0
DUCK_CX = 16.0
DUCK_SHIFT = (2, 4)
DUCK_ANCHOR = (int(DUCK_CX) + DUCK_SHIFT[0], int(DUCK_GROUND) + DUCK_SHIFT[1])
WATERLINE = DUCK_GROUND - 2.6     # on water, nothing below this shows

D_CLEAR, D_OUT, D_DARK, D_BASE, D_LIGHT, D_CHEEK, D_STRIPE, D_BILL, D_SADDLE, D_LEG, D_EYE, D_SPEC = range(12)
HEN = [
    None,
    (50, 38, 28),
    (98, 72, 48),       # DARK
    (140, 106, 72),     # BASE    mottled brown
    (178, 142, 100),    # LIGHT
    (196, 168, 128),    # CHEEK
    (70, 52, 38),       # STRIPE  eye stripe, cap
    (206, 132, 56),     # BILL    orange
    (78, 60, 44),       # SADDLE  dark mark on the bill
    (232, 140, 58),     # LEG
    (22, 18, 18),       # EYE
    (64, 86, 176),      # SPEC    blue wing patch
]
DUCKLING = [
    None,
    (78, 60, 30),
    (150, 118, 50),
    (226, 196, 92),     # BASE    downy yellow
    (244, 222, 128),
    (240, 214, 120),
    (110, 84, 40),      # STRIPE  dark back and cap
    (96, 80, 60),       # BILL    grey-brown
    (80, 64, 50),
    (150, 120, 70),
    (22, 18, 18),
    (110, 84, 40),
]
DUCK_SHADE = {D_BASE: (D_LIGHT, D_DARK)}
DUCK_SCALES = {"duck": 1.0, "duckling": 0.46}

DUCK_STAND = Pose(
    body=(14.0, 16.6), tilt=0.0, roll=0.0, head=(20.4, 10.8), neck=1.0, swim=0.0, upend=0.0,
    fa=(13.0, DUCK_GROUND), fb=(15.0, DUCK_GROUND), bill=1.0,
)


def draw_duck(p, kind="duck"):
    palette = HEN if kind == "duck" else DUCKLING
    scale = DUCK_SCALES[kind]
    c = Canvas(DUCK_W, DUCK_H, scale=scale, pivot=(DUCK_CX, DUCK_GROUND), shift=DUCK_SHIFT)
    features = []
    bx, by = p.body
    t = p.tilt + p.upend * 70.0

    def at(dx, dy):
        rx, ry = rot(dx, dy, t)
        return bx + rx, by + ry

    duckling = kind == "duckling"
    if not p.swim:
        for foot, col in ((p.fb, D_DARK), (p.fa, D_LEG)):
            hip = at(0.0, 2.6)
            c.paint(c.capsule(hip[0], hip[1], foot[0], foot[1] - 0.5, 0.7, 0.55), col)
            c.paint(c.ellipse(foot[0] + 0.8, foot[1] - 0.4, 1.4, 0.5), col)
    # body: a boat with an upswept tail
    c.paint(c.polygon([at(-5.0, -1.6), at(-8.6, -3.0 - p.roll), at(-7.6, 0.4), at(-5.0, 1.6)]), D_BASE)
    body = c.ellipse(bx, by, 6.6 if not duckling else 5.4, 3.7 if not duckling else 4.0, t)
    c.paint(body, D_BASE)
    if not duckling:
        c.paint(c.ellipse(*at(-1.0, -0.8), 4.6, 2.0, t), D_DARK, within=body)        # folded wing
        c.paint(c.ellipse(*at(-2.6, 0.2), 1.6, 0.7, t), D_SPEC, within=body)        # speculum
    else:
        c.paint(c.ellipse(*at(-1.0, -1.6), 4.0, 1.6, t), D_STRIPE, within=body)     # dark down on the back
    if p.upend < 0.5:
        hx, hy = p.head
        neck_from = at(4.6, -1.6)
        c.paint(c.capsule(neck_from[0], neck_from[1], hx - 0.4, hy + 0.8, 2.0, 1.7), D_BASE)
        head_r = 2.5 if not duckling else 3.0
        c.paint(c.ellipse(hx, hy, head_r, head_r * 0.92), D_BASE)
        c.paint(c.ellipse(hx + 0.2, hy + 0.6, head_r * 0.8, head_r * 0.55), D_CHEEK)
        c.paint(c.capsule(hx - 2.0, hy - 0.4, hx + 1.6, hy - 0.2, 0.35), D_STRIPE)   # eye stripe
        c.paint(c.ellipse(hx - 0.3, hy - head_r * 0.7, head_r * 0.8, head_r * 0.4), D_STRIPE)
        b0 = hx + head_r * 0.8
        c.paint(c.polygon([(b0, hy - 0.4), (b0 + 3.4 * p.bill, hy + 0.6), (b0 + 3.2 * p.bill, hy + 1.5),
                           (b0, hy + 1.4)]), D_BILL)
        if not duckling:
            c.paint(c.ellipse(b0 + 1.4, hy + 0.5, 1.0, 0.45), D_SADDLE)
        features.append((hx + 0.6, hy - 0.4, D_EYE))
    if p.swim:
        c.idx[c.ys > WATERLINE, :] = 0       # under the water
    return _finish(c, features, palette, DUCK_SHADE, D_OUT, DUCK_W, DUCK_H)


def duck_poses():
    s = DUCK_STAND
    waddle = []
    for i in range(6):
        u = i / 6
        a = 4.0 * math.sin(2 * math.pi * u)
        lift_a = max(0.0, math.sin(2 * math.pi * u)) * 1.2
        lift_b = max(0.0, -math.sin(2 * math.pi * u)) * 1.2
        waddle.append(s.with_(roll=a * 0.15, tilt=a * 0.6,
                              fa=(13.0 + 1.2 * math.cos(2 * math.pi * u), DUCK_GROUND - lift_a),
                              fb=(15.0 - 1.2 * math.cos(2 * math.pi * u), DUCK_GROUND - lift_b),
                              head=(20.4 + 0.5 * math.sin(4 * math.pi * u), 10.8)))
    swim = s.with_(swim=1.0, body=(14.0, 18.8), head=(20.4, 13.0))
    paddle = [swim.with_(body=(14.0, 18.8 + 0.3 * math.sin(i / 4 * math.tau)),
                         head=(20.4 + 0.3 * math.sin(i / 4 * math.tau), 13.0)) for i in range(4)]
    upend = swim.with_(upend=1.0, body=(14.0, 20.4))
    return {
        "stand": [s, s.with_(head=(20.0, 10.6)), s, s.with_(head=(20.8, 11.0))],
        "walk": waddle,
        "swim": paddle,
        "upend": [swim, swim.blend(upend, 0.6), upend, upend, upend, swim.blend(upend, 0.5), swim],
    }


# --------------------------------------------------------------------------

def _finish(c, features, palette, rules, out, w, h):
    grid = c.resolve(len(palette))
    grid = shade(grid, rules)
    for x, y, colour in features:
        xi, yi = (int(math.floor(v)) for v in c.to_art(x, y))
        if 0 <= xi < w and 0 <= yi < h and grid[yi, xi]:
            grid[yi, xi] = colour
    grid = outline(grid, out)
    return to_surface(grid, palette)


def _render(poses, draw):
    cache, out = {}, {}
    for key, frames in poses.items():
        drawn = []
        for p in frames:
            k = repr(sorted(p.items()))
            if k not in cache:
                cache[k] = draw(p)
            drawn.append(cache[k])
        out[key + "_right"] = drawn
    return out


def render_heron():
    return _render(heron_poses(), draw_heron)


def render_ducks():
    out = {}
    for kind in ("duck", "duckling"):
        for key, frames in _render(duck_poses(), lambda p, k=kind: draw_duck(p, k)).items():
            out[f"{kind}_{key}"] = frames
    return out
