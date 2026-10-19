"""Mochi, drawn from a posable puppet.

Three views share one palette and one 64x64 canvas whose ground contact
point is (32, 48), the same contract as the original sprite sheets:

* side (facing right; mirrored for left),
* front (walking toward the viewer), and
* back (walking away).

Each view is a function of a ``Pose``: body joint positions, paw
positions (limbs are solved with two-bone IK so a paw can be planted
exactly), head tilt and turn, eyelids, mouth, ears and a tail chain.
Gaits are generated from foot timing, so planted paws stay still relative
to the ground; every other animation is a few key poses blended into
in-between frames (sitting down, lying down, stretching, a pounce).

Pose numbers are in "pose space"; the canvas scales them by ``SCALE``
about the feet, which sizes the cat without touching any pose.
"""

import math

from .pixelrig import Canvas, Pose, outline, rot, shade, to_surface, two_bone

W = H = 64
GROUND = 48.0
CX = 32.0
SCALE = 1.12

# --- palette ---------------------------------------------------------------
CLEAR, OUT, DEEP, DARK, BASE, LIGHT, CREAM, CREAM_SH, PINK, IRIS, PUPIL, SHINE, MOUTH = range(13)
PALETTE = [
    None,
    (40, 33, 40),      # OUT    outline
    (66, 59, 66),      # DEEP   creases, far-side shade
    (90, 83, 90),      # DARK   far legs, belly shade
    (122, 115, 120),   # BASE   grey coat
    (152, 146, 148),   # LIGHT  lit back
    (232, 226, 214),   # CREAM  bib, muzzle, socks
    (190, 182, 172),   # CREAM_SH
    (222, 150, 156),   # PINK   nose, inner ear, tongue
    (196, 204, 92),    # IRIS
    (24, 20, 26),      # PUPIL
    (211, 223, 225),   # SHINE  eye highlight (the eye-shine code looks for it)
    (92, 40, 52),      # MOUTH
]
SHADE_RULES = {BASE: (LIGHT, DARK), CREAM: (None, CREAM_SH), DARK: (None, DEEP)}
EYE_SHINE = PALETTE[SHINE]


def canvas():
    return Canvas(W, H, scale=SCALE, pivot=(CX, GROUND))


def finish(c, features=(), late=()):
    """Resolve to pixels, shade, place hand-set pixels (eyes, nose), outline,
    then add pixels that must sit outside the outline (whiskers)."""
    grid = c.resolve(len(PALETTE))
    grid = shade(grid, SHADE_RULES)
    for x, y, colour in features:
        xi, yi = (int(math.floor(v)) for v in c.to_art(x, y))
        if 0 <= xi < W and 0 <= yi < H:
            grid[yi, xi] = colour
    grid = outline(grid, OUT)
    for x, y, colour in late:
        xi, yi = (int(math.floor(v)) for v in c.to_art(x, y))
        if 0 <= xi < W and 0 <= yi < H and grid[yi, xi] == CLEAR:
            grid[yi, xi] = colour
    return to_surface(grid, PALETTE)


def _eye(c, features, x, y, openness, mirror=False):
    """A 2x2 eye with its top-left pixel at pose point (x, y)."""
    ax, ay = c.to_art(x, y)
    ex, ey = int(math.floor(ax)), int(math.floor(ay))

    def put(dx, dy, colour):
        features.append((*c.to_pose(ex + dx + 0.5, ey + dy + 0.5), colour))

    a, b = (1, 0) if mirror else (0, 1)
    if openness <= 0.2:
        put(0, 1, DEEP)
        put(1, 1, DEEP)
    elif openness < 0.75:
        put(0, 0, DEEP)
        put(1, 0, DEEP)
        put(a, 1, PUPIL)
        put(b, 1, IRIS)
    else:
        put(a, 0, SHINE)
        put(b, 0, PUPIL)
        put(a, 1, PUPIL)
        put(b, 1, IRIS)


# =============================================================================
# Side view (facing right)

SIDE = Pose(
    hip=(25.0, 33.0), sho=(38.0, 33.5),         # haunch and chest centres
    haunch=(5.6, 5.4), chest=(5.2, 6.2), torso=3.8, arch=0.0,
    head=(44.5, 25.0), tilt=0.0, turn=0.0,      # turn: 0 profile, 1 face to viewer
    ear=0.0, eye=1.0, mouth=0.0, tongue=0.0,
    fn=(40.0, 48.0), ff=(37.0, 48.0),           # fore paws (near, far)
    hn=(25.5, 48.0), hf=(23.0, 48.0),           # hind paws
    fn_rot=0.0, ff_rot=0.0,                     # fore paw orientation (raised paws)
    hn_lift=0.0, hf_lift=0.0,                   # hock orientation
    fore_bend=-1.0,
    tail=245.0, curl=-7.0, curl2=-20.0, tail_len=2.1, tail_front=0.0, troot=None,
    puff=1.0,
)


def _tail_points(x, y, angle, curl, curl2, seg, n=8, floor=GROUND - 1.7):
    pts = [(x, y)]
    a = angle
    for i in range(n):
        a += curl if i < n // 2 else curl2
        x += math.cos(math.radians(a)) * seg
        y = min(floor, y - math.sin(math.radians(a)) * seg)
        pts.append((x, y))
    return pts


def _tail_mask(c, p, root):
    pts = _tail_points(root[0], root[1], p.tail, p.curl, p.curl2, p.tail_len)
    radii = [1.75 * p.puff - i * 0.07 for i in range(len(pts))]
    radii[-1] = 1.15 * p.puff
    return c.chain(pts, radii)


def _floor(pt, radius):
    """Keep a joint of the given thickness from sinking into the ground."""
    return (pt[0], min(pt[1], GROUND - radius))


def _paw(c, toe, rx, ry, angle):
    a = math.radians(angle)
    half = math.hypot(rx * math.sin(a), ry * math.cos(a))
    x, y = _floor(toe, half)
    return c.ellipse(x, y, rx, ry, angle)


def _foreleg(c, root, paw, rot_deg, bend):
    """(fur mask, sock mask) of a foreleg reaching from ``root`` to ``paw``."""
    px, py = paw
    wx, wy = rot(-0.2, -2.6, rot_deg)
    wrist = _floor((px + wx, py + wy), 1.35)
    elbow = _floor(two_bone(root, wrist, 5.6, 5.0, bend=bend), 1.5)
    fur = c.chain([root, elbow, wrist], [1.95, 1.5, 1.35])
    tx, ty = rot(0.5, -1.0, rot_deg)
    toe = _floor((px + tx, py + ty), 1.15)
    sock = c.capsule(wrist[0], wrist[1], toe[0], toe[1], 1.3) | _paw(c, toe, 1.75, 1.15, rot_deg)
    return fur, sock


def _hindleg(c, root, paw, lift):
    px, py = paw
    hx, hy = rot(-2.4, -4.2, lift)
    hock = _floor((px + hx, py + hy), 1.35)
    knee = _floor(two_bone(root, hock, 5.4, 5.2, bend=1), 1.6)
    fur = c.chain([root, knee, hock], [2.3, 1.6, 1.35])
    tx, ty = rot(0.6, -1.0, lift)
    toe = _floor((px + tx, py + ty), 1.15)
    sock = c.capsule(hock[0], hock[1], toe[0], toe[1], 1.3, 1.2) | _paw(c, toe, 1.8, 1.15, lift)
    return fur, sock


def _limb(c, masks, near, crease_below=None):
    fur, sock = masks
    if near:
        within = None if crease_below is None else c.below(crease_below)
        c.part(fur | sock, BASE, crease=DEEP, width=0.8, within=within)
        c.paint(sock, CREAM)
    else:
        c.paint(fur, DARK)
        c.paint(sock, CREAM_SH)


def tail_root(p):
    """Where the tail leaves the body (an explicit ``troot`` wins)."""
    if p.get("troot"):
        return p.troot
    hx, hy = p.hip
    sx, sy = p.sho
    ang = math.atan2(-(sy - hy), sx - hx)
    ca, sa = math.cos(ang), math.sin(ang)
    return (hx - 4.0 * ca + 0.4 * sa, hy - 2.4 + 4.0 * sa)


def draw_side(p):
    c = canvas()
    features, late = [], []
    hx, hy = p.hip
    sx, sy = p.sho
    puff = p.puff
    ang = math.degrees(math.atan2(-(sy - hy), sx - hx))   # body axis
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    root = tail_root(p)

    if p.tail_front < 0.5:
        c.paint(_tail_mask(c, p, root), BASE)
    _limb(c, _hindleg(c, (hx + 1.0, hy + 0.8), p.hf, p.hf_lift), near=False)
    _limb(c, _foreleg(c, (sx - 0.6, sy + 2.0), p.ff, p.ff_rot, p.fore_bend), near=False)

    body = c.ellipse(hx, hy, p.haunch[0] * puff, p.haunch[1] * puff, ang)
    body |= c.capsule(hx, hy, sx, sy, p.torso * puff)
    body |= c.ellipse(sx, sy, p.chest[0] * puff, p.chest[1] * puff, ang)
    if p.arch:
        mx, my = (hx + sx) / 2, (hy + sy) / 2
        body |= c.ellipse(mx, my - p.arch, (sx - hx) / 2 + 1.0, p.torso * puff + 0.4, ang)
    c.paint(body, BASE)
    c.paint(c.ellipse(sx + 3.4 * ca - 0.6 * sa, sy - 0.6 - 3.4 * sa, 2.6, 4.4, ang + 20), CREAM, within=body)

    hind_over = p.get("hind_over", 0.0) >= 0.5   # a hind paw raised to the ear
    if not hind_over:
        _limb(c, _hindleg(c, (hx + 1.0, hy + 1.6), p.hn, p.hn_lift), near=True, crease_below=hy + 1.5)
    # the near thigh sits over the leg's top; its crease shows below the flank
    thigh = c.ellipse(hx + 0.6, hy + 0.4, p.haunch[0] * 0.86 * puff, p.haunch[1] * 0.86 * puff, ang)
    c.part(thigh, BASE, crease=DARK, width=0.7, over=[BASE], within=c.below(hy + 0.5))
    if p.tail_front >= 0.5:
        c.part(_tail_mask(c, p, root), BASE, crease=DEEP, width=0.8)
    _limb(c, _foreleg(c, (sx + 0.4, sy + 2.4), p.fn, p.fn_rot, p.fore_bend), near=True,
          crease_below=min(sy + 2.0, p.fn[1] - 4.0))

    qx, qy = p.head
    c.paint(c.capsule(sx + 1.0 * ca, sy - 1.0, qx - 1.0, qy + 1.0, 3.5 * puff, 3.0), BASE)
    if p.turn >= 0.5:
        _front_face(c, qx, qy, p, features, late)
    else:
        _side_head(c, qx, qy, p, features, late)
    if hind_over:
        _limb(c, _hindleg(c, (hx + 1.0, hy + 1.6), p.hn, p.hn_lift), near=True)
    return finish(c, features, late)


def _side_head(c, qx, qy, p, features, late):
    t = p.tilt

    def at(dx, dy):
        rx, ry = rot(dx, dy, t)
        return qx + rx, qy + ry

    flat = p.ear
    # far ear, behind the head
    b0, b1 = at(-4.8 - flat, -2.6 + flat * 1.2), at(-0.8 - flat * 0.6, -3.9 + flat * 0.6)
    tip = at(-3.2 - flat * 4.4, -8.6 + flat * 5.4)
    c.paint(c.polygon([b0, tip, b1]), DARK)
    c.paint(c.ellipse(qx, qy, 5.6, 4.9, t), BASE)
    b0, b1 = at(-1.8 - flat, -3.2 + flat * 1.2), at(2.6 - flat * 0.6, -3.9 + flat * 0.6)
    tip = at(-0.2 - flat * 4.4, -8.8 + flat * 5.4)
    c.paint(c.polygon([b0, tip, b1]), BASE)
    inner = [at(-0.6 - flat, -3.4 + flat), at(-0.2 - flat * 4.0, -7.2 + flat * 4.6), at(1.4 - flat * 0.6, -3.8 + flat * 0.6)]
    c.paint(c.polygon(inner), PINK)
    c.paint(c.ellipse(*at(4.0, 1.6), 2.0, 1.7, t), CREAM)                 # muzzle
    c.paint(c.ellipse(*at(2.0, 3.0), 2.6, 1.4, t), CREAM)                 # chin and cheek
    if p.mouth > 0.05:
        c.paint(c.ellipse(*at(3.4, 2.6 + p.mouth * 0.6), 1.6 + p.mouth * 0.5, 0.5 + p.mouth * 1.4, t), MOUTH)
        if p.tongue > 0:
            c.paint(c.ellipse(*at(3.8 + p.tongue * 1.4, 3.0 + p.mouth), 1.0, 0.7, t), PINK)
    ex, ey = at(1.6, -1.2)
    _eye(c, features, ex, ey, p.eye)
    features.append((*at(5.7, 0.5), PINK))
    for dx, dy in ((6.8, 1.8), (7.6, 2.6), (6.6, 3.0)):
        late.append((*at(dx, dy), LIGHT))


def _front_face(c, hx, hy, p, features, late):
    """A face turned toward the viewer, centred on (hx, hy)."""
    flat = p.ear
    for side in (-1, 1):
        base_out = (hx + side * 5.4, hy - 1.0 + flat * 1.5)
        base_in = (hx + side * 1.4, hy - 3.6)
        tip = (hx + side * (4.6 + flat * 3.0), hy - 7.8 + flat * 4.6)
        c.paint(c.polygon([base_in, tip, base_out]), BASE)
        inner = [(base_in[0] + side * 0.9, base_in[1] + 0.3), (tip[0] - side * 0.5, tip[1] + 1.6),
                 (base_out[0] - side * 1.0, base_out[1] - 0.4)]
        c.paint(c.polygon(inner), PINK)
    c.paint(c.ellipse(hx, hy, 5.6, 4.7), BASE)
    c.paint(c.ellipse(hx, hy + 1.4, 6.1, 3.4), BASE)                     # cheeks
    c.paint(c.ellipse(hx, hy + 2.2, 2.9, 1.9), CREAM)                    # muzzle
    if p.mouth > 0.05:
        c.paint(c.ellipse(hx, hy + 2.9 + p.mouth * 0.7, 1.3 + p.mouth * 0.3, 0.6 + p.mouth * 1.3), MOUTH)
        if p.tongue > 0:
            c.paint(c.ellipse(hx, hy + 3.5 + p.mouth * 1.2, 0.9, 0.8), PINK)
    _eye(c, features, hx - 3.1, hy - 0.9, p.eye)
    _eye(c, features, hx + 1.3, hy - 0.9, p.eye, mirror=True)
    features.append((hx - 0.4, hy + 1.3, PINK))
    features.append((hx + 0.4, hy + 1.3, PINK))
    for side in (-1, 1):
        for dx, dy in ((6.8, 1.4), (7.8, 1.0), (6.8, 2.8), (7.8, 3.2)):
            late.append((hx + side * dx, hy + dy, LIGHT))


# =============================================================================
# Front view (facing the viewer) and back view (facing away)

FRONT = Pose(
    chest=(32.0, 39.0), chest_r=(4.8, 4.6), head=(32.0, 30.0),
    fl=(30.0, 48.0), fr=(34.0, 48.0),           # fore paws (viewer's left/right)
    hl=(27.6, 47.0), hr=(36.4, 47.0),           # hind paws, a step further away
    sit=0.0,
    ear=0.0, eye=1.0, mouth=0.0, tongue=0.0,
    tail=66.0, curl=4.0, curl2=10.0, tail_len=1.9, tail_x=3.0, puff=1.0,
)
FRONT_SIT = FRONT.with_(sit=1.0, chest=(32.0, 38.6), chest_r=(5.0, 6.0), head=(32.0, 29.6),
                        fl=(30.2, 48.0), fr=(33.8, 48.0), hl=(26.4, 48.0), hr=(37.6, 48.0))


def _column_leg(c, top, paw, radius):
    px, py = paw
    tx, ty = top
    fur = c.capsule(tx, ty, px, py - 2.0, radius, radius * 0.9)
    sock = c.capsule(px, py - 2.2, px, py - 1.0, radius * 0.9) | c.ellipse(px, py - 1.0, 1.7, 1.1)
    return fur, sock


def _wrapped_tail(c, cx, side):
    pts = [(cx + side * 6.6, 44.0), (cx + side * 7.6, 45.8), (cx + side * 6.4, 46.3),
           (cx + side * 4.0, 46.5), (cx + side * 1.8, 46.7)]
    c.part(c.chain(pts, [1.7, 1.6, 1.5, 1.35, 1.2]), BASE, crease=DEEP, width=0.8)


def draw_front(p):
    c = canvas()
    features, late = [], []
    cx, cy = p.chest
    sit = p.sit
    hx, hy = p.head
    if sit < 0.5:
        root = (cx + p.tail_x, cy - 1.5)
        pts = _tail_points(root[0], root[1], p.tail, p.curl, p.curl2, p.tail_len)
        c.paint(c.chain(pts, [1.6 - i * 0.05 for i in range(len(pts))]), BASE)
        for paw in (p.hl, p.hr):
            _limb(c, _column_leg(c, (paw[0], cy + 0.5), paw, 1.5), near=False)
        c.paint(c.ellipse(cx, cy - 1.0, 5.6 * p.puff, 3.8 * p.puff), BASE)  # shoulders
    else:
        c.paint(c.ellipse(cx, 44.5, 7.4, 3.4), BASE)                       # haunches
        for paw in (p.hl, p.hr):
            c.paint(c.ellipse(paw[0], paw[1] - 1.0, 1.9, 1.1), CREAM)
    body = c.ellipse(cx, cy, p.chest_r[0] * p.puff, p.chest_r[1] * p.puff)
    c.paint(body, BASE)
    c.paint(c.ellipse(cx, cy - p.chest_r[1] * 0.35, 2.6, p.chest_r[1] * 0.55), CREAM, within=body)
    for paw in (p.fl, p.fr):
        top = (cx + (paw[0] - cx) * 0.8, cy + 1.0)
        _limb(c, _column_leg(c, top, paw, 1.55), near=True)
    if sit >= 0.5:
        _wrapped_tail(c, cx, 1)
    c.paint(c.capsule(cx, cy - 3.0, hx, hy + 2.0, 3.6), BASE)
    _front_face(c, hx, hy, p, features, late)
    return finish(c, features, late)


BACK = FRONT.with_(tail=70.0, curl=2.0, curl2=-14.0, tail_x=1.6, tail_len=1.7, chest=(32.0, 38.6), chest_r=(5.4, 5.0),
                   head=(32.0, 30.0), fl=(28.6, 46.6), fr=(35.4, 46.6), hl=(29.8, 48.0), hr=(34.2, 48.0))
BACK_SIT = BACK.with_(sit=1.0, head=(32.0, 29.6))


def _back_head(c, hx, hy, p):
    c.paint(c.ellipse(hx, hy, 5.5, 4.6), BASE)
    c.paint(c.ellipse(hx, hy + 1.3, 6.0, 3.4), BASE)
    flat = p.ear
    for side in (-1, 1):
        base_out = (hx + side * 5.4, hy - 1.0 + flat * 1.5)
        base_in = (hx + side * 1.4, hy - 3.6)
        tip = (hx + side * (4.6 + flat * 3.0), hy - 7.8 + flat * 4.6)
        c.paint(c.polygon([base_in, tip, base_out]), BASE)
        c.paint(c.polygon([(base_in[0] + side * 1.2, base_in[1] + 0.5), (tip[0] - side * 0.2, tip[1] + 2.0),
                           (base_out[0] - side * 1.4, base_out[1])]), DARK)


def draw_back(p):
    c = canvas()
    cx, cy = p.chest
    sit = p.sit
    hx, hy = p.head
    if sit < 0.5:
        for paw in (p.fl, p.fr):
            _limb(c, _column_leg(c, (paw[0], cy - 1.0), paw, 1.5), near=False)
    _back_head(c, hx, hy, p)
    if sit < 0.5:
        c.paint(c.ellipse(cx, cy - 2.4, 4.8, 3.8), BASE)                   # shoulders
        c.paint(c.ellipse(cx, cy, p.chest_r[0] * p.puff, p.chest_r[1] * p.puff), BASE)
        for side, paw in ((-1, p.hl), (1, p.hr)):
            leg = _column_leg(c, (cx + side * 2.4, cy + 3.0), paw, 1.55)
            _limb(c, leg, near=True)
            c.part(c.ellipse(cx + side * 2.7, cy + 2.0, 2.5, 3.0), BASE, crease=DARK, width=0.6, over=[BASE])
        root = (cx + p.tail_x, cy - 2.6)
        pts = _tail_points(root[0], root[1], p.tail, p.curl, p.curl2, p.tail_len)
        c.part(c.chain(pts, [1.7 - i * 0.06 for i in range(len(pts))]), BASE, crease=DEEP, width=0.7)
    else:
        c.paint(c.ellipse(cx, 37.6, 4.8, 5.4), BASE)
        c.paint(c.ellipse(cx, 43.4, 7.2, 4.4), BASE)
        pts = [(cx + 1.0, 46.3), (cx + 4.0, 46.4), (cx + 7.0, 46.0), (cx + 8.6, 44.6), (cx + 8.8, 42.6)]
        c.part(c.chain(pts, [1.7, 1.65, 1.55, 1.4, 1.2]), BASE, crease=DEEP, width=0.7)
    return finish(c)


DRAW = {"side": draw_side, "front": draw_front, "back": draw_back}
