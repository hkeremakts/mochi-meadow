"""Small birds drawn from a posable puppet (side view, facing right).

One puppet draws both the pigeon and the house sparrow; species differ by
size and palette.  Like the cat, poses are numbers, so the head-bobbing
walk, a peck, wing beats, a glide and the flared landing are all
generated, and walks are stride-locked: the planted foot stays put.

Sizes are true to the cat: a pigeon is about two-thirds of the cat's body
length, a sparrow less than half of that.  Colours follow the meadow's
storybook style (cool in shadow, warm in the light, plum-tinted
outlines), and the crow, big enough for it, has an eye with a glint.
"""

import math

from .pixelrig import Canvas, Pose, despeckle, ease, glint_eye, outline, rot, shade, to_surface

W, H = 32, 40
GROUND = 22.0
CX = 16.0
HEADROOM = 8          # canvas rows above the pose space, for raised wings

CLEAR, OUT, DARK, BASE, LIGHT, WING, BAR, NECK_G, NECK_P, FEET, BEAK, CERE, EYE, BELLY, CAP, SHINE, WORM, STRAW = range(18)
CARRIED = [(176, 102, 102), (206, 196, 128)]     # a worm, a stem of dry grass (every palette ends with these)

PIGEON = [
    None,
    (40, 40, 52),       # OUT
    (86, 88, 104),      # DARK   far wing, shade
    (126, 130, 148),    # BASE   body
    (172, 172, 182),    # LIGHT  warmer
    (150, 156, 172),    # WING   folded wing
    (58, 58, 72),       # BAR    wing bars, tail band
    (88, 146, 112),     # NECK_G iridescent green
    (138, 92, 146),     # NECK_P iridescent purple
    (214, 116, 120),    # FEET
    (58, 52, 58),       # BEAK
    (226, 224, 216),    # CERE
    (236, 148, 48),     # EYE
    (126, 130, 148),    # BELLY
    (110, 114, 132),    # CAP
    (240, 244, 244),    # SHINE
]
SPARROW = [
    None,
    (50, 32, 42),       # OUT    plum-brown
    (94, 66, 58),       # DARK   cooler
    (150, 112, 74),     # BASE   warm brown back
    (198, 160, 108),    # LIGHT  warmer
    (132, 92, 58),      # WING
    (62, 42, 30),       # BAR    streaks
    (60, 52, 50),       # NECK_G -> black bib
    (60, 52, 50),
    (196, 150, 128),
    (60, 52, 48),
    (210, 200, 182),    # CERE   cheek
    (24, 20, 20),       # EYE
    (210, 200, 180),    # BELLY  pale front
    (128, 128, 136),    # CAP    grey crown
    (240, 244, 244),    # SHINE
]
CROW = [
    None,
    (16, 12, 24),
    (26, 26, 36),
    (40, 40, 52),       # BASE   glossy black
    (66, 68, 90),       # LIGHT  blue sheen on top
    (46, 46, 60),
    (38, 38, 50),       # BAR    no bars on a crow: barely darker than the wing
    (52, 58, 86),       # NECK_G blue-violet gloss
    (58, 50, 80),
    (34, 34, 40),       # FEET
    (30, 30, 36),       # BEAK   heavy and black
    (40, 40, 52),       # CERE   (none)
    (12, 10, 14),       # EYE
    (40, 40, 52),
    (36, 36, 48),
    (232, 236, 240),    # SHINE  the glint that makes a black eye readable
]
# The blackbirds that nest in the old tree in spring: the cock all black
# with an orange-yellow bill and eye-ring, the hen dark brown with a
# mottled breast, and their speckled, short-tailed young with the yellow
# gape still at the corners of the bill.
BLACKBIRD = [
    None,
    (28, 20, 38),       # OUT
    (32, 30, 44),       # DARK
    (46, 44, 56),       # BASE   black, a little warm
    (80, 78, 96),       # LIGHT  the sheen on top
    (52, 50, 64),       # WING
    (38, 36, 48),       # BAR
    (46, 44, 56),       # NECK_G (none)
    (46, 44, 56),
    (86, 64, 50),       # FEET   dark brown
    (240, 166, 38),     # BEAK   orange-yellow
    (236, 196, 72),     # CERE   the yellow eye-ring
    (14, 10, 14),       # EYE
    (46, 44, 56),
    (42, 40, 52),       # CAP
    (240, 244, 244),    # SHINE
]
BLACKBIRD_HEN = [
    None,
    (46, 30, 42),       # OUT    plum-brown
    (74, 54, 52),       # DARK   cooler
    (106, 78, 56),      # BASE   dark brown
    (144, 110, 74),     # LIGHT  warmer
    (98, 72, 54),       # WING
    (72, 52, 42),       # BAR    the mottling on her breast
    (134, 104, 78),     # NECK_G a paler throat
    (106, 78, 56),
    (96, 72, 58),       # FEET
    (158, 124, 62),     # BEAK   dull yellow-brown
    (158, 124, 62),     # CERE
    (18, 14, 16),       # EYE
    (126, 94, 66),      # BELLY  warm brown breast
    (98, 72, 52),       # CAP
    (240, 244, 244),    # SHINE
]
FLEDGLING = [
    None,
    (50, 32, 44),       # OUT
    (82, 62, 56),       # DARK
    (122, 92, 64),      # BASE   warm brown, still fluffy
    (166, 130, 90),     # LIGHT
    (110, 82, 58),      # WING
    (200, 164, 112),    # BAR    pale speckles
    (152, 118, 82),     # NECK_G
    (122, 92, 64),
    (156, 122, 100),    # FEET
    (100, 82, 62),      # BEAK
    (238, 206, 92),     # CERE   the yellow gape
    (18, 14, 16),       # EYE
    (152, 114, 76),     # BELLY
    (112, 84, 60),      # CAP
    (240, 244, 244),    # SHINE
]
for _palette in (PIGEON, SPARROW, CROW, BLACKBIRD, BLACKBIRD_HEN, FLEDGLING):
    _palette.extend(CARRIED)
# palette, scale, canvas size, offset of the pose space on it, beak length
SPECIES = {
    "pigeon": (PIGEON, 1.15, (W, H), (0, HEADROOM), 1.0),
    "sparrow": (SPARROW, 0.55, (W, H), (0, HEADROOM), 1.0),
    "crow": (CROW, 1.6, (48, 58), (8, HEADROOM + 12), 1.45),   # ~45 cm, a heavy bill
    "blackbird": (BLACKBIRD, 0.86, (W, H), (0, HEADROOM), 1.05),        # ~25 cm
    "blackbird_hen": (BLACKBIRD_HEN, 0.84, (W, H), (0, HEADROOM), 1.0),
    "fledgling": (FLEDGLING, 0.7, (W, H), (0, HEADROOM), 0.75),
}
# How a species differs from the pigeon's build: tail length, fluffiness,
# and the fledgling's speckles.
FORM = {
    "blackbird": dict(tail=1.35),
    "blackbird_hen": dict(tail=1.35),
    "fledgling": dict(tail=0.4, fluff=1.14, speckled=True, gape=1.0),
}
SHADE = {BASE: (LIGHT, DARK), WING: (LIGHT, None), BELLY: (None, BASE)}

# --- poses -----------------------------------------------------------------

STAND = Pose(
    body=(15.0, 15.5), tilt=14.0, bulk=1.0,     # body centre and pitch (nose up = +)
    head=(20.0, 9.6), look=0.0,                 # look: head pitch
    neck=1.0,
    wings="folded", wing_t=0.0,                 # folded / flap (t = beat phase) / glide / flare
    legs=1.0, fa=(15.0, GROUND), fb=(16.6, GROUND),
    tail_fan=0.0, tail_drop=0.0,
)


def draw(p, species="pigeon"):
    palette, scale, (cw, ch), shift, beak = SPECIES[species]
    form = FORM.get(species, {})
    c = Canvas(cw, ch, scale=scale, pivot=(CX, GROUND), shift=shift)
    features = []
    bx, by = p.body
    t = p.tilt

    def at(dx, dy, ox=bx, oy=by, a=t):
        rx, ry = rot(dx, dy, a)
        return ox + rx, oy + ry

    # far wing (raised or lowered behind the body)
    if p.wings != "folded":
        _wing(c, p, at, far=True)
    # legs
    if p.legs > 0.05:
        hip = at(0.6, 2.6)
        for foot, col in ((p.fb, DARK), (p.fa, FEET)):
            knee = (hip[0] * 0.5 + foot[0] * 0.5 + 0.4, hip[1] * 0.5 + foot[1] * 0.5)
            c.paint(c.chain([hip, knee, (foot[0], foot[1] - 0.5)], [0.55, 0.5, 0.5]), FEET)
            c.paint(c.ellipse(foot[0] + 0.6, foot[1] - 0.45, 1.3, 0.45), FEET)
    # tail
    reach = 5.6 * form.get("tail", 1.0)
    spread = 1.2 + p.tail_fan * 1.6
    tip_a = at(-3.0 - reach, -spread + 0.4 + p.tail_drop)
    tip_b = at(-3.0 - reach, spread + 0.8 + p.tail_drop)
    c.paint(c.polygon([at(-3.0, -1.2), tip_a, tip_b, at(-3.0, 1.6)]), BASE)
    band_x = -3.0 - reach * 4.4 / 5.6
    band = c.polygon([at(band_x, -spread + 0.2 + p.tail_drop), tip_a, tip_b, at(band_x, spread + 1.0 + p.tail_drop)])
    c.paint(band, BAR)
    # body
    bulk = p.bulk * form.get("fluff", 1.0)
    body = c.ellipse(bx, by, 5.2 * bulk, 3.4 * bulk, t)
    c.paint(body, BASE)
    c.paint(c.ellipse(*at(2.6, 0.6), 2.6 * bulk, 2.6 * bulk, t), BELLY, within=body)
    if form.get("speckled"):
        for dx, dy in ((2.4, 0.2), (3.6, 1.6), (1.2, 1.8), (-1.6, -1.6)):
            features.append((*at(dx, dy), BAR))
    # neck and head
    hx, hy = p.head
    neck_root = at(3.6, -1.2)
    c.paint(c.capsule(neck_root[0], neck_root[1], hx, hy + 0.6, 2.3 * p.neck * bulk, 1.6), BASE)
    sheen = c.capsule(neck_root[0], neck_root[1], hx, hy + 0.6, 2.0 * p.neck * bulk, 1.4)
    c.paint(sheen & c.below(hy + 1.6) & ~c.below(neck_root[1] + 0.6), NECK_G)
    c.paint(sheen & c.below(neck_root[1] - 0.2) & ~c.below(neck_root[1] + 1.4), NECK_P)
    c.paint(c.ellipse(hx, hy, 2.0, 1.85), BASE)
    c.paint(c.ellipse(hx - 0.2, hy - 0.9, 1.6, 0.9), CAP)
    lk = p.look
    bk0 = (hx + 1.4, hy - 0.2)
    thick = 0.6 * beak
    gape = p.get("gape", 0.0)
    if gape:
        # Open: the two halves of the bill part, the mouth showing between
        # (a begging youngster's is all mouth).
        size = beak * (1.0 + 0.9 * gape * form.get("gape", 0.0))
        up = rot(2.3 * size, 0.0, lk + 34 * gape)
        down = rot(2.1 * size, 0.6, lk - 30 * gape)
        mouth = c.polygon([(bk0[0] - 0.3, bk0[1] - 0.2), (bk0[0] + up[0], bk0[1] + up[1]),
                           (bk0[0] + down[0], bk0[1] + down[1])])
        c.paint(mouth, CERE)
        c.paint(c.capsule(bk0[0], bk0[1] - thick * 0.6, bk0[0] + up[0], bk0[1] + up[1], 0.5, 0.3), BEAK)
        c.paint(c.capsule(bk0[0], bk0[1] + 0.5 * beak, bk0[0] + down[0], bk0[1] + down[1], 0.45, 0.3), BEAK)
        tip = (bk0[0] + (up[0] + down[0]) / 2, bk0[1] + (up[1] + down[1]) / 2)
    else:
        bk1 = rot(2.3 * beak, 0.5, lk)
        c.paint(c.polygon([(bk0[0], bk0[1] - thick), (bk0[0] + bk1[0], bk0[1] + bk1[1]),
                           (bk0[0], bk0[1] + 0.7 * beak)]), BEAK)
        tip = (bk0[0] + bk1[0], bk0[1] + bk1[1])
    carry = p.get("carry")
    if carry == "worm":          # hanging from the bill, kinked
        mid = (tip[0] + 0.6, tip[1] + 1.6)
        c.paint(c.chain([(tip[0] - 0.6, tip[1] + 0.2), mid, (mid[0] - 0.4, mid[1] + 1.8)], [0.6, 0.6, 0.5]), WORM)
    elif carry == "straw":       # a beakful of dry grass, the ends hanging either side
        c.paint(c.chain([(tip[0] - 3.2, tip[1] + 2.2), (tip[0] - 0.8, tip[1] + 0.2), (tip[0] + 1.6, tip[1] + 0.6),
                         (tip[0] + 2.8, tip[1] + 2.4)], [0.5, 0.55, 0.55, 0.45]), STRAW)
    features.append((hx + 1.3, hy - 0.5, CERE))
    if species == "crow":
        glint_eye(c, features, hx - 0.2, hy - 0.9, 1.0, EYE, SHINE)
    else:
        features.append((hx + 0.3, hy - 0.4, EYE))
    # near wing
    if p.wings == "folded":
        lift = p.get("wing_lift", 0.0)        # held out a little, quivering (a begging fledgling)
        wing = c.ellipse(*at(-0.6 + lift * 0.8, -0.6 - lift * 1.6), 4.4 * bulk, 2.3 * bulk, t - 4 + lift * 26)
        c.paint(wing, WING, within=None if lift else c.grow(body, 0.3))
        for dx in (-1.4, 0.6):
            c.paint(c.capsule(*at(dx, -1.2), *at(dx - 0.6, 1.2), 0.42), BAR, within=wing)
        c.paint(c.capsule(*at(-4.6, 0.2), *at(-2.6, -0.4), 0.6), BAR, within=wing)
    else:
        _wing(c, p, at, far=False)
    grid = c.resolve(len(palette))
    grid = shade(grid, SHADE)
    for x, y, col in features:
        xi, yi = (int(math.floor(v)) for v in c.to_art(x, y))
        if 0 <= xi < cw and 0 <= yi < ch:
            grid[yi, xi] = col
    grid = outline(grid, OUT)
    grid = despeckle(grid, keep=(OUT, BAR, NECK_G, NECK_P, FEET, BEAK, CERE, EYE, SHINE, WORM, STRAW))
    return to_surface(grid, palette)


def _wing(c, p, at, far):
    """An open wing.

    The meadow is seen from above at an angle, so a flying bird shows both
    wings spread: the far one reaching up the screen, the near one down.
    A wing beat changes how far each reaches.  Landing (``flare``) is the
    exception: the wings are cupped up and forward, seen side-on."""
    sh = at(0.8, -1.2) if far else at(0.6, 0.6)
    if p.wings == "flare":
        lift = 0.9
        reach = 9.0 if not far else 7.6
        up = lift * reach
        wrist = (sh[0] - 1.0, sh[1] - up * 0.55 - 0.6)
        tip = (sh[0] - 3.6, sh[1] - up - 0.2)
        trail = (sh[0] - 5.0, sh[1] - up * 0.6 + 1.4)
        shape = [sh, wrist, tip, trail, at(-2.8, -0.4)]
        if far:
            shape = [(x + 1.2, y - 0.4) for x, y in shape]
    else:
        if p.wings == "glide":
            open_ = 1.0
            sweep = 0.0
        else:
            beat = math.cos(2 * math.pi * p.wing_t)      # +1 top of stroke, -1 bottom
            open_ = 0.45 + 0.55 * abs(beat)
            sweep = 1.4 * math.sin(2 * math.pi * p.wing_t)
        span = (9.0 if far else 10.5) * open_
        sign = -1 if far else 1                          # far wing up the screen
        wrist = (sh[0] - 0.6 + sweep * 0.5, sh[1] + sign * span * 0.55)
        tip = (sh[0] - 2.6 + sweep, sh[1] + sign * span)
        trail = (sh[0] - 4.6 + sweep * 0.6, sh[1] + sign * span * 0.8)
        root_back = (sh[0] - 4.2, sh[1] + sign * 0.6)
        shape = [sh, wrist, tip, trail, root_back]
    m = c.polygon(shape)
    c.paint(m, DARK if far else WING)
    if not far:
        c.paint(c.polygon([wrist, tip, trail, ((wrist[0] + trail[0]) / 2, (wrist[1] + trail[1]) / 2)]), BAR)


# --- animations ---------------------------------------------------------------

WALK_STRIDE = 5.0


def walk(n=6):
    """Head-bobbing walk.  The head thrusts forward, then holds still in
    space while the body catches up, which is the pigeon's signature."""
    out = []
    for i in range(n):
        phi = i / n
        p = Pose(STAND)
        for foot, off in (("fa", 0.0), ("fb", 0.5)):
            x0, _ = STAND[foot]
            u = (phi - off) % 1.0
            if u < 0.55:
                x = x0 + WALK_STRIDE / 2 - WALK_STRIDE * (u / 0.55)
                y = GROUND
            else:
                v = (u - 0.55) / 0.45
                x = x0 - WALK_STRIDE / 2 + WALK_STRIDE * ease(v)
                y = GROUND - 1.2 * math.sin(math.pi * v)
            p[foot] = (x, y)
        u = (phi * 2) % 1.0
        if u < 0.7:
            dx = 1.4 - (WALK_STRIDE / 2) * (u / 0.7)
        else:
            dx = 1.4 - WALK_STRIDE / 2 + (WALK_STRIDE / 2) * ease((u - 0.7) / 0.3)
        p["head"] = (STAND.head[0] + dx, STAND.head[1] + 0.3 * math.sin(2 * math.pi * u))
        p["body"] = (STAND.body[0], STAND.body[1] + 0.25 * math.cos(4 * math.pi * phi))
        out.append(p)
    return out


def hop(n=5):
    """A sparrow's two-footed hop (stride 6 per hop)."""
    out = []
    for i in range(n):
        u = i / n
        lift = 2.6 * math.sin(math.pi * u)
        p = STAND.with_(body=(STAND.body[0], STAND.body[1] - lift), head=(STAND.head[0], STAND.head[1] - lift),
                        fa=(STAND.fa[0] - 0.6 * math.sin(math.pi * u), GROUND - lift),
                        fb=(STAND.fb[0] - 0.6 * math.sin(math.pi * u), GROUND - lift), tilt=STAND.tilt + 6 * math.sin(math.pi * u))
        out.append(p)
    return out


def idle():
    looks = [STAND, STAND.with_(head=(19.6, 9.2), look=8.0), STAND,
             STAND.with_(head=(20.4, 9.9), look=-6.0)]
    return looks


def peck():
    down = STAND.with_(tilt=-22.0, body=(15.6, 16.2), head=(22.6, 19.6), look=-50.0, neck=0.9, tail_drop=-0.5)
    mid = STAND.blend(down, 0.5)
    return [mid, down, down.with_(head=(22.8, 20.2)), down, mid]


def coo():
    puffed = STAND.with_(bulk=1.12, neck=1.3, tilt=20.0, head=(19.6, 9.0), tail_fan=0.8, tail_drop=1.0)
    bow = puffed.with_(head=(21.0, 11.4), tilt=6.0, look=-20.0)
    return [STAND, puffed, bow, puffed, bow, puffed, STAND]


def preen():
    turn = STAND.with_(head=(15.8, 11.4), look=-140.0, neck=1.1)
    return [STAND, turn, turn.with_(head=(15.2, 12.0)), turn, STAND]


FLY = STAND.with_(tilt=4.0, body=(15.0, 13.0), head=(20.6, 10.6), legs=0.0, wings="flap", tail_fan=0.4)


def flap(n=6):
    return [FLY.with_(wing_t=i / n, body=(FLY.body[0], FLY.body[1] + 0.4 * math.cos(2 * math.pi * i / n)))
            for i in range(n)]


def glide():
    return [FLY.with_(wings="glide", tail_fan=0.8)]


def flare(n=3):
    """Landing: body pitched up, wings cupped forward, feet reaching."""
    base = STAND.with_(tilt=40.0, body=(14.4, 14.0), head=(18.2, 8.2), wings="flare", tail_fan=1.0,
                       tail_drop=1.4, fa=(15.8, GROUND - 0.5), fb=(16.8, GROUND - 1.0))
    return [base.with_(wings="flap", wing_t=0.5 + 0.5 * i / n) for i in range(n)] + [base]


def takeoff(n=4):
    base = STAND.with_(tilt=26.0, legs=1.0, wings="flap", tail_fan=0.8)
    return [base.with_(wing_t=i / n) for i in range(n)]


# --- the blackbirds ---------------------------------------------------------

def listen():
    """A blackbird on a lawn: a few quick steps, then stock-still with its
    head cocked to the ground, listening for a worm."""
    cocked = STAND.with_(tilt=8.0, body=(15.2, 15.8), head=(20.8, 11.2), look=-26.0, tail_drop=-0.6)
    return [STAND.blend(cocked, 0.5), cocked, cocked, cocked]


def tug():
    """...and the worm pulled out: braced, leaning back, it comes free."""
    stab = STAND.with_(tilt=-22.0, body=(15.6, 16.2), head=(22.6, 19.6), look=-50.0, neck=0.9, tail_drop=-0.5)
    pull = STAND.with_(tilt=26.0, body=(14.2, 15.2), head=(18.8, 9.6), look=-34.0, carry="worm", tail_drop=0.8)
    lean = pull.with_(tilt=30.0, body=(13.8, 15.0), head=(18.2, 9.2), look=-44.0)
    return [stab, stab.with_(carry="worm"), pull, lean, pull, lean, STAND.with_(carry="worm")]


def scold():
    """The alarm at a cat: tail flicked up and fanned, wings drooped, the
    bill snapping open with every call, bobbing."""
    up = STAND.with_(tilt=24.0, head=(19.6, 8.8), look=12.0, tail_drop=-4.2, tail_fan=1.0, gape=0.8,
                     wing_lift=0.3)
    down = STAND.with_(tilt=6.0, body=(15.0, 16.2), head=(20.6, 11.0), look=-6.0, tail_drop=0.6, tail_fan=0.3)
    return [up, up, down, up, down, down]


def feed(carry="worm"):
    """Leaning in to a gaping chick: the food goes in, then a moment's
    look before it's off for more."""
    reach = STAND.with_(tilt=-14.0, body=(15.8, 16.0), head=(22.6, 15.0), look=-30.0, neck=1.15, gape=0.4,
                        carry=carry)
    given = reach.with_(carry=None, gape=0.0, head=(22.8, 15.6))
    return [STAND.with_(carry=carry), reach, reach, given, given, STAND]


def carrying(poses, what):
    return [p.with_(carry=what) for p in poses]


# --- their young -------------------------------------------------------------

FLEDGE = STAND.with_(tilt=10.0, body=(15.0, 16.0), head=(19.6, 10.6), tail_drop=0.6)


def fledgling_idle():
    """Puffed up and still, as fledglings sit waiting to be fed."""
    return [FLEDGE, FLEDGE, FLEDGE.with_(bulk=1.04), FLEDGE.with_(head=(19.2, 10.4), look=6.0)]


def beg():
    """Head up, the yellow mouth wide open, wings quivering."""
    ask = FLEDGE.with_(tilt=26.0, head=(18.6, 7.6), look=62.0, gape=1.0, wing_lift=0.9, neck=1.2)
    return [ask, ask.with_(wing_lift=0.3, head=(18.8, 8.0)), ask, ask.with_(wing_lift=0.4, look=54.0)]


def flutter(n=4):
    """A fledgling's first, clumsy flight: fast beats, legs dangling."""
    base = FLY.with_(tilt=12.0, legs=1.0, tail_fan=0.2)
    return [base.with_(wing_t=i / n) for i in range(n)]


def build(species):
    if species == "fledgling":
        return {"idle": fledgling_idle(), "walk": hop(), "beg": beg(), "peck": peck(), "preen": preen(),
                "flap": flutter(), "flare": flare(), "takeoff": takeoff()}
    anims = {
        "idle": idle(),
        "walk": hop() if species == "sparrow" else walk(),
        "peck": peck(),
        "preen": preen(),
        "flap": flap(),
        "glide": glide(),
        "flare": flare(),
        "takeoff": takeoff(),
    }
    if species in ("pigeon", "crow"):
        anims["coo"] = coo()     # the crow's version is a caw
    if species.startswith("blackbird"):
        anims["listen"] = listen()
        anims["tug"] = tug()
        anims["scold"] = scold()
        for what in ("worm", "straw"):
            anims[f"feed~{what}"] = feed(what)
            for name in ("idle", "walk", "flap", "glide", "flare", "takeoff"):
                anims[f"{name}~{what}"] = carrying(anims[name], what)
    return anims


def render(species):
    cache = {}
    out = {}
    for key, poses in build(species).items():
        frames = []
        for p in poses:
            k = repr(sorted(p.items()))
            if k not in cache:
                cache[k] = draw(p, species)
            frames.append(cache[k])
        out[key] = frames
    return out


ANCHORS = {name: (int(CX + spec[3][0]), int(GROUND) + spec[3][1]) for name, spec in SPECIES.items()}
ANCHOR = ANCHORS["pigeon"]
STRIDE = {"pigeon": WALK_STRIDE * 1.15, "sparrow": 6.0 * 0.55, "crow": WALK_STRIDE * 1.6,
          "blackbird": WALK_STRIDE * 0.86, "blackbird_hen": WALK_STRIDE * 0.84, "fledgling": 6.0 * 0.7}
