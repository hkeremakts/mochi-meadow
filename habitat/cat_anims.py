"""Every animation Mochi has, as poses for the puppet in ``cat_art``.

Keys name the pose and the view: ``walk_right``, ``sit_front``,
``sitdown_back``...  Only right-facing side views are drawn; the loader
mirrors them into ``_left`` keys.  For each animation whose eyes are open
there is also a ``<key>__blink`` twin with the eyes shut, frame for frame,
so the cat can blink in the middle of anything.

Gaits are generated from foot timing: each paw spends part of the cycle
planted (sliding backwards at exactly the body's speed, so it stays put on
the ground) and the rest swinging forward.  ``STRIDES`` gives the art
pixels covered per cycle, which the game uses to lock playback to motion.
"""

import math

from . import cat_art as ca
from .cat_art import BACK, BACK_SIT, FRONT, FRONT_SIT, GROUND, SCALE, SIDE
from .pixelrig import Pose, ease

# =============================================================================
# Key poses (side view, facing right)

STAND = SIDE
SIT = SIDE.with_(hip=(28.0, 41.0), haunch=(6.4, 6.0), sho=(34.5, 33.5), chest=(4.8, 6.0), torso=4.4,
                 head=(38.5, 24.5), fn=(37.5, 48.0), ff=(35.5, 48.0), hn=(33.0, 48.0), hn_lift=55.0,
                 hf=(31.0, 48.0), hf_lift=55.0, tail_front=1.0, troot=(22.8, 46.4), tail=-6.0, curl=1.0,
                 curl2=5.0)
LIE = SIDE.with_(hip=(25.5, 43.0), haunch=(6.2, 4.8), sho=(37.5, 43.2), chest=(4.8, 4.6), torso=4.0,
                 head=(43.0, 35.5), fn=(47.5, 48.0), ff=(46.0, 48.0), fore_bend=1.0,
                 hn=(31.0, 48.0), hn_lift=60.0, hf=(29.0, 48.0), hf_lift=60.0,
                 tail_front=1.0, troot=(19.5, 45.0), tail=225.0, curl=22.0, curl2=10.0)
LOAF_SLEEP = LIE.with_(head=(43.5, 39.0), tilt=-14.0, eye=0.0)
CURL = LIE.with_(hip=(27.0, 42.6), haunch=(7.0, 5.1), sho=(35.5, 43.4), chest=(5.4, 4.3),
                 head=(40.5, 40.0), turn=1.0, eye=0.0, fn=(41.0, 48.0), ff=(40.0, 48.0),
                 troot=(21.0, 46.6), tail=-8.0, curl=2.0, curl2=6.0)
FLAT = SIDE.with_(hip=(24.0, 43.6), haunch=(6.0, 4.0), sho=(37.0, 43.6), chest=(5.0, 4.0), torso=3.8,
                  head=(44.5, 42.6), tilt=-12.0, eye=0.0, fn=(49.0, 47.6), ff=(48.0, 48.0), fn_rot=-80.0,
                  ff_rot=-80.0, fore_bend=1.0, hn=(14.0, 47.0), hn_lift=-120.0, hf=(15.0, 48.0),
                  hf_lift=-120.0, troot=(19.0, 43.5), tail=190.0, curl=-2.0, curl2=-4.0)
STALK = SIDE.with_(hip=(25.0, 37.5), sho=(38.0, 39.0), head=(45.0, 34.5), tilt=-6.0, ear=0.15,
                   tail=186.0, curl=1.0, curl2=4.0, fn=(41.0, 48.0), ff=(38.5, 48.0))
CROUCH = SIDE.with_(hip=(24.5, 40.0), sho=(38.5, 41.0), head=(45.0, 36.5), tilt=-4.0, haunch=(5.8, 5.2),
                    fn=(42.5, 48.0), ff=(41.0, 48.0), hn=(28.0, 48.0), hn_lift=40.0, hf=(26.5, 48.0),
                    hf_lift=40.0, tail=182.0, curl=0.0, curl2=6.0)
BOW = SIDE.with_(sho=(40.0, 40.0), hip=(25.0, 31.5), head=(47.0, 34.0), tilt=12.0, fn=(51.0, 48.0),
                 ff=(49.5, 48.0), fn_rot=-75.0, ff_rot=-75.0, fore_bend=1.0, eye=0.0, mouth=0.6,
                 tail=105.0, curl=-6.0, curl2=-12.0)
HIND_STRETCH = SIDE.with_(hip=(23.5, 35.0), sho=(38.5, 31.5), head=(45.0, 23.5), tilt=8.0,
                          hn=(12.5, 47.5), hn_lift=-75.0, hf=(22.0, 48.0), eye=0.5, tail=200.0, curl=-3.0,
                          curl2=-6.0)
EAT = SIDE.with_(sho=(38.5, 36.0), head=(46.5, 40.5), tilt=-40.0, fn=(41.5, 48.0), ff=(39.0, 48.0),
                 tail=230.0, curl=-6.0, curl2=-14.0)
DRINK = SIDE.with_(hip=(26.0, 40.0), sho=(38.5, 40.5), haunch=(5.8, 5.4), head=(46.0, 40.5), tilt=-34.0,
                   fn=(42.5, 48.0), ff=(41.0, 48.0), hn=(30.0, 48.0), hn_lift=48.0, hf=(28.5, 48.0),
                   hf_lift=48.0, tail=200.0, curl=4.0, curl2=8.0)
HISS = SIDE.with_(hip=(26.0, 33.0), sho=(37.0, 33.5), arch=3.0, puff=1.15, head=(43.5, 27.0), tilt=6.0,
                  ear=1.0, mouth=0.9, fn=(40.5, 48.0), ff=(38.0, 48.0), hn=(24.5, 48.0), hf=(22.5, 48.0),
                  tail=96.0, curl=-1.0, curl2=-5.0)
SNIFF = SIDE.with_(head=(47.0, 33.5), tilt=-22.0, sho=(38.5, 34.5))
REAR = SIT.with_(hip=(27.5, 40.0), sho=(31.0, 28.0), chest=(4.6, 6.2), head=(33.5, 19.0), tilt=12.0,
                 fn=(37.5, 17.0), ff=(36.0, 19.0), fn_rot=-160.0, ff_rot=-160.0, fore_bend=-1.0,
                 hn=(31.5, 48.0), hn_lift=20.0, hf=(29.5, 48.0), hf_lift=20.0)

# Where the cat's nose is while eating or drinking, in art pixels from the
# feet: game code lines the bowl and the water up with it.
_nx, _ny = ca.side_at(0.0, 0.0, EAT.tilt, *ca.NOSE)
MOUTH_REACH = round((EAT.head[0] + _nx - ca.CX) * SCALE)

# =============================================================================
# Helpers


def seq(*parts):
    out = []
    for part in parts:
        out.extend(part)
    return out


def tween(a, b, n):
    """n frames easing from ``a`` to ``b``, ending exactly on ``b``.

    The tail swings the short way round and its root slides between the
    two poses instead of jumping."""
    if "hip" in a and "hip" in b:
        a = a.with_(troot=ca.tail_root(a))
        b = b.with_(troot=ca.tail_root(b))
    if "tail" in a and "tail" in b:
        turn = (b.tail - a.tail + 180.0) % 360.0 - 180.0
        b2 = b.with_(tail=a.tail + turn)
    else:
        b2 = b
    frames = [a.blend(b2, ease(i / n)) for i in range(1, n)]
    return frames + [b]


def hold(p, n):
    return [p] * n


def breathe(p, phase, amount=0.22):
    """Swell the chest and flank.  The belly stays on the ground; the back
    rises."""
    s = math.sin(2 * math.pi * phase)
    q = Pose(p)
    if "sho" in p:                     # side view: chest and haunch are radii
        q["chest"] = (p.chest[0] + amount * 0.4 * s, p.chest[1] + amount * s)
        q["sho"] = (p.sho[0], p.sho[1] - amount * s)
        q["haunch"] = (p.haunch[0] + amount * 0.3 * s, p.haunch[1] + amount * 0.6 * s)
        q["hip"] = (p.hip[0], p.hip[1] - amount * 0.6 * s)
    if "chest_r" in p:                 # front and back views
        q["chest_r"] = (p.chest_r[0] + amount * 0.5 * s, p.chest_r[1] + amount * 0.4 * s)
    return q


def _shift(pt, dx=0.0, dy=0.0):
    return (pt[0] + dx, pt[1] + dy)


# =============================================================================
# Gaits

SIDE_FEET = ("hn", "fn", "hf", "ff")


def side_gait(base, phi, stride, duty, lift, offsets, bob=0.35, tail_sway=4.0):
    """One frame of a gait cycle at phase ``phi``.  ``stride`` is how far the
    body travels per cycle; a planted paw sweeps back by exactly the
    distance the body covers while it is down (``stride * duty``)."""
    p = Pose(base)
    reach = stride * duty
    for leg, off in offsets.items():
        nx, _ = base[leg]
        t = (phi - off) % 1.0
        hind = leg[0] == "h"
        if t < duty:
            u = t / duty
            x = nx + reach / 2 - reach * u
            y = GROUND
            hock = -18.0 * u if hind else 0.0
            paw_rot = 0.0
        else:
            u = (t - duty) / (1.0 - duty)
            x = nx - reach / 2 + reach * ease(u)
            y = GROUND - lift * math.sin(math.pi * u)
            hock = -18.0 * (1 - u) + 30.0 * math.sin(math.pi * u) if hind else 0.0
            paw_rot = -35.0 * math.sin(math.pi * u) if not hind else 0.0
        p[leg] = (x, y)
        if hind:
            p[leg + "_lift"] = base.get(leg + "_lift", 0.0) + hock
        else:
            p[leg + "_rot"] = base.get(leg + "_rot", 0.0) + paw_rot
    wave = math.cos(4 * math.pi * phi)
    p["hip"] = _shift(base.hip, 0, bob * wave)
    p["sho"] = _shift(base.sho, 0, bob * math.cos(4 * math.pi * phi + 1.6))
    p["head"] = _shift(base.head, 0, bob * 0.8 * math.cos(4 * math.pi * phi + 1.6))
    p["tail"] = base.tail + tail_sway * math.sin(2 * math.pi * phi)
    return p


WALK_STRIDE = 16.0      # body travel per cycle, pose units
TROT_STRIDE = 22.0
RUN_STRIDE = 44.0
STALK_STRIDE = 9.0
WALK_LATERAL = {"hn": 0.0, "fn": 0.25, "hf": 0.5, "ff": 0.75}
TROT_DIAGONAL = {"hn": 0.0, "ff": 0.0, "fn": 0.5, "hf": 0.5}
GALLOP = {"hn": 0.0, "hf": 0.1, "fn": 0.5, "ff": 0.6}


def walk_side(n=8):
    return [side_gait(STAND, i / n, WALK_STRIDE, 0.62, 2.0, WALK_LATERAL) for i in range(n)]


def trot_side(n=8):
    base = STAND.with_(tail=120.0, curl=-6.0, curl2=-16.0)
    return [side_gait(base, i / n, TROT_STRIDE, 0.5, 2.6, TROT_DIAGONAL, bob=0.5) for i in range(n)]


def stalk_side(n=8):
    return [side_gait(STALK, i / n, STALK_STRIDE, 0.75, 1.2, WALK_LATERAL, bob=0.15, tail_sway=1.5)
            for i in range(n)]


def run_side(n=6):
    base = STAND.with_(tail=185.0, curl=-2.0, curl2=-6.0, ear=0.35)
    out = []
    for i in range(n):
        phi = i / n
        p = side_gait(base, phi, RUN_STRIDE, 0.32, 3.4, GALLOP, bob=0.0, tail_sway=6.0)
        ext = math.sin(2 * math.pi * (phi - 0.05))
        up = -1.4 * max(0.0, math.sin(2 * math.pi * (phi + 0.2)))
        p["hip"] = (base.hip[0] - 1.8 * ext, base.hip[1] + up + 0.5)
        p["sho"] = (base.sho[0] + 1.8 * ext, base.sho[1] + up + 0.8 * ext)
        p["head"] = (base.head[0] + 1.8 * ext + 0.5, base.head[1] + up + 0.6 * ext + 1.0)
        p["arch"] = 1.6 * max(0.0, -ext)
        out.append(p)
    return out


def front_gait(base, phi, lift=1.6, sway=0.3, back=False):
    p = Pose(base)
    pairs = {"fl": 0.0, "hr": 0.0, "fr": 0.5, "hl": 0.5}
    for leg, off in pairs.items():
        t = (phi - off) % 1.0
        x, y = base[leg]
        if t >= 0.55:
            u = (t - 0.55) / 0.45
            near = (leg[0] == "f") != back
            y -= lift * math.sin(math.pi * u) * (1.0 if near else 0.6)
        p[leg] = (x, y)
    wave = math.cos(4 * math.pi * phi)
    s = sway * math.sin(2 * math.pi * phi)
    p["chest"] = _shift(base.chest, s, 0.35 * wave)
    p["head"] = _shift(base.head, s * 0.6, 0.3 * wave)
    p["tail"] = base.tail + 6.0 * math.sin(2 * math.pi * phi)
    return p


def walk_front(n=8):
    return [front_gait(FRONT, i / n) for i in range(n)]


def walk_back(n=8):
    return [front_gait(BACK, i / n, back=True) for i in range(n)]


def run_front(n=6):
    base = FRONT.with_(ear=0.3)
    return [front_gait(base, i / n, lift=2.6, sway=0.15) for i in range(n)]


def run_back(n=6):
    return [front_gait(BACK, i / n, lift=2.6, sway=0.15, back=True) for i in range(n)]


def stalk_front(n=8):
    base = FRONT.with_(chest=(32.0, 41.5), head=(32.0, 34.5), hl=(27.2, 46.0), hr=(36.8, 46.0), ear=0.15,
                       tail=95.0, curl=0.0, curl2=0.0, tail_len=1.0)
    return [front_gait(base, i / n, lift=1.0, sway=0.15) for i in range(n)]


def stalk_back(n=8):
    base = BACK.with_(chest=(32.0, 40.0), head=(32.0, 33.0), tail=262.0, curl=0.0, curl2=2.0, tail_x=0.0,
                      tail_len=1.3)
    return [front_gait(base, i / n, lift=1.0, sway=0.15, back=True) for i in range(n)]


# =============================================================================
# Idle loops


def idle(base, n, tail_amp=6.0, tip_amp=0.0, breath=0.22, twitch_at=None):
    out = []
    for i in range(n):
        phi = i / n
        p = breathe(base, phi, breath)
        p["tail"] = base.tail + tail_amp * math.sin(2 * math.pi * phi)
        if tip_amp:
            p["curl2"] = base.curl2 + tip_amp * math.sin(2 * math.pi * phi * 2)
        if twitch_at is not None and i == twitch_at:
            p["ear"] = base.get("ear", 0.0) + 0.3
        out.append(p)
    return out


# =============================================================================
# Building the library


def side_anims():
    a = {}
    a["walk"] = walk_side()
    a["trot"] = trot_side()
    a["run"] = run_side()
    a["stalk"] = stalk_side()
    a["stand"] = idle(STAND, 12, tail_amp=7.0, twitch_at=8)
    a["stand_look"] = idle(STAND.with_(turn=1.0, head=(43.5, 25.0)), 12, tail_amp=7.0)
    a["sit"] = idle(SIT, 12, tail_amp=0.0, tip_amp=8.0, twitch_at=5)
    a["sit_look"] = idle(SIT.with_(turn=1.0, head=(37.0, 24.5)), 12, tail_amp=0.0, tip_amp=8.0)
    a["lie"] = idle(LIE, 12, tail_amp=4.0, tip_amp=6.0, twitch_at=9)
    a["lie_look"] = idle(LIE.with_(turn=1.0, head=(42.0, 35.5)), 12, tail_amp=4.0, tip_amp=6.0)
    a["sleep_loaf"] = idle(LOAF_SLEEP, 4, tail_amp=0.0, breath=0.3)
    a["sleep_curl"] = idle(CURL, 4, tail_amp=0.0, breath=0.3)
    a["sleep_flat"] = idle(FLAT, 4, tail_amp=0.0, breath=0.35)
    a["crouch"] = [CROUCH.with_(hip=_shift(CROUCH.hip, dx), hn=_shift(CROUCH.hn, 0, -lift), hn_lift=40 + lift * 10)
                   for dx, lift in ((0.0, 0.0), (0.7, 0.8), (0.0, 0.0), (-0.7, 0.0))]
    # transitions
    a["sitdown"] = tween(STAND, SIT, 6)
    a["standup"] = tween(SIT, STAND, 5)
    a["liedown"] = tween(SIT, LIE, 6)
    a["situp"] = tween(LIE, SIT, 5)
    a["doze"] = tween(LIE, LOAF_SLEEP, 4)
    a["undoze"] = tween(LOAF_SLEEP, LIE, 3)
    a["curlup"] = tween(LIE, CURL, 5)
    a["uncurl"] = tween(CURL, LIE, 4)
    a["sprawl"] = tween(LIE, FLAT, 6)
    a["unsprawl"] = tween(FLAT, LIE, 5)
    a["stretch"] = seq(tween(STAND, BOW, 4), hold(BOW, 5), tween(BOW, STAND, 3),
                       tween(STAND, HIND_STRETCH, 3), hold(HIND_STRETCH, 4), tween(HIND_STRETCH, STAND, 3))
    # yawns
    for name, base in (("sit", SIT), ("lie", LIE), ("stand", STAND)):
        big = base.with_(mouth=1.0, tongue=0.6, eye=0.0, tilt=base.tilt + 14.0,
                         head=_shift(base.head, 0.3, -0.6))
        a[f"yawn_{name}"] = seq(tween(base, big, 3), hold(big, 3), tween(big, base, 3))
        open_ = base.with_(mouth=0.75, tilt=base.tilt + 6.0)
        a[f"meow_{name}"] = seq(tween(base, open_, 2), hold(open_, 2), tween(open_, base, 2))
    # kneading: treading the ground with the fore paws, eyes half shut
    kb = STAND.with_(sho=_shift(STAND.sho, 0, 1.0), head=_shift(STAND.head, 0, 1.2), tilt=-6.0, eye=0.5)
    up_near = kb.with_(fn=_shift(kb.fn, 1.0, -3.4), fn_rot=-35.0)
    up_far = kb.with_(ff=_shift(kb.ff, 1.0, -3.4), ff_rot=-35.0)
    a["knead"] = seq(tween(kb, up_near, 2), tween(up_near, kb, 2), tween(kb, up_far, 2), tween(up_far, kb, 2))
    a["knead_start"] = tween(STAND, kb, 3)
    # grooming
    paw_up = SIT.with_(fn=(41.8, 31.5), fn_rot=-120.0, tilt=-16.0, head=(38.8, 25.0))
    lick = paw_up.with_(tongue=0.8, mouth=0.1, eye=0.0)
    wipe = SIT.with_(fn=(40.0, 22.5), fn_rot=-150.0, tilt=-28.0, head=(38.6, 25.8), eye=0.0)
    a["groom"] = seq(tween(SIT, paw_up, 3), [lick, paw_up.with_(eye=0.0)] * 3,
                     tween(paw_up, wipe, 2), hold(wipe, 2), tween(wipe, paw_up, 2), tween(paw_up, SIT, 3))
    chest_lick = LIE.with_(turn=1.0, head=(41.0, 38.5), eye=0.0, mouth=0.3, tongue=0.8)
    a["groom_lie"] = seq(tween(LIE, chest_lick.with_(tongue=0.0, mouth=0.0), 3),
                         [chest_lick, chest_lick.with_(tongue=0.0, mouth=0.1)] * 3,
                         tween(chest_lick, LIE, 3))
    scratch_a = SIT.with_(hn=(35.0, 23.5), hn_lift=150.0, tilt=-20.0, eye=0.0, head=(38.5, 26.0),
                          hind_over=1.0)
    scratch_b = scratch_a.with_(hn=(35.6, 26.0), hn_lift=160.0)
    lifting = SIT.with_(hn=(35.0, 38.0), hn_lift=120.0, hind_over=1.0)
    a["scratch"] = seq([lifting], [scratch_b, scratch_a] * 6, [lifting, SIT])
    # eating and drinking
    chew = [EAT, EAT.with_(mouth=0.35, head=_shift(EAT.head, 0, -0.5)), EAT,
            EAT.with_(head=_shift(EAT.head, 0.2, 0.3))]
    a["eat"] = chew
    a["eat_start"] = tween(STAND, EAT, 4)
    a["eat_end"] = tween(EAT, STAND, 3)
    lap = [DRINK, DRINK.with_(tongue=0.9, mouth=0.25, head=_shift(DRINK.head, 0.2, 0.4))]
    a["drink"] = lap
    a["drink_start"] = tween(STAND, DRINK, 4)
    a["drink_end"] = tween(DRINK, STAND, 4)
    # hunting
    launch = CROUCH.with_(hip=(24.0, 37.0), sho=(39.5, 32.0), head=(46.5, 27.0), tilt=12.0,
                          fn=(47.5, 38.0), fn_rot=-70.0, ff=(46.5, 40.0), ff_rot=-70.0,
                          hn=(14.0, 46.5), hn_lift=-105.0, hf=(16.0, 47.8), hf_lift=-100.0, tail=175.0)
    air = launch.with_(hip=(22.0, 35.0), sho=(39.5, 34.0), head=(47.0, 30.0), tilt=0.0,
                       fn=(50.5, 41.0), ff=(49.5, 43.0), hn=(11.0, 40.0), hf=(12.5, 42.0), tail=180.0)
    land = CROUCH.with_(hip=(25.0, 35.0), sho=(39.0, 39.0), head=(45.5, 36.0), fn=(46.5, 48.0),
                        ff=(45.0, 48.0), hn=(26.0, 45.5), hn_lift=10.0, hf=(24.0, 46.0), tail=150.0)
    a["pounce"] = [CROUCH, launch, air, land, CROUCH]
    for name, base in (("sit", SIT), ("stand", STAND)):
        up = base.with_(fn=(43.0, 37.0), fn_rot=-90.0, ear=0.2)
        out = base.with_(fn=(48.0, 33.5), fn_rot=-40.0, ear=0.2)
        down = base.with_(fn=(48.0, 44.0), fn_rot=10.0, ear=0.2)
        a[f"swipe_{name}"] = seq([base, up], [out, out, down], tween(down, base, 3))
    a["rear"] = seq(tween(SIT, REAR, 3), [REAR.with_(fn=(39.0, 16.0)), REAR, REAR.with_(fn=(39.5, 18.5))],
                    tween(REAR, SIT, 3))
    a["hiss"] = [HISS, HISS.with_(mouth=0.7, puff=1.17)]
    a["hiss_start"] = tween(STAND, HISS, 3)
    a["sniff"] = [SNIFF, SNIFF.with_(head=_shift(SNIFF.head, 0.4, -0.2)), SNIFF,
                  SNIFF.with_(head=_shift(SNIFF.head, 0.3, 0.2))]
    a["sniff_start"] = tween(STAND, SNIFF, 3)
    return a


def front_anims(view):
    stand, sit = (FRONT, FRONT_SIT) if view == "front" else (BACK, BACK_SIT)
    a = {}
    a["walk"] = walk_front() if view == "front" else walk_back()
    a["run"] = run_front() if view == "front" else run_back()
    a["trot"] = a["walk"]
    a["stalk"] = stalk_front() if view == "front" else stalk_back()
    a["stand"] = idle(stand, 12, tail_amp=8.0, twitch_at=8)
    a["sit"] = idle(sit, 12, tail_amp=0.0, twitch_at=5)
    a["sitdown"] = tween(stand, sit, 4)
    a["standup"] = tween(sit, stand, 4)
    if view == "front":
        for name, base in (("sit", sit), ("stand", stand)):
            big = base.with_(mouth=1.0, tongue=0.6, eye=0.0, head=_shift(base.head, 0, -0.6))
            a[f"yawn_{name}"] = seq(tween(base, big, 3), hold(big, 3), tween(big, base, 3))
            open_ = base.with_(mouth=0.75, head=_shift(base.head, 0, -0.4))
            a[f"meow_{name}"] = seq(tween(base, open_, 2), hold(open_, 2), tween(open_, base, 2))
        paw_up = sit.with_(fr=(33.4, 35.5), head=(31.6, 30.0))
        lick = paw_up.with_(tongue=0.8, mouth=0.1, eye=0.0)
        wipe = sit.with_(fr=(34.6, 27.5), head=(31.0, 30.2), eye=0.0)
        a["groom"] = seq(tween(sit, paw_up, 3), [lick, paw_up.with_(eye=0.0)] * 3,
                         tween(paw_up, wipe, 2), hold(wipe, 2), tween(wipe, paw_up, 2), tween(paw_up, sit, 3))
        up = sit.with_(fr=(35.0, 38.0))
        out = sit.with_(fr=(37.5, 33.5))
        down = sit.with_(fr=(37.0, 42.0))
        a["swipe_sit"] = seq([sit, up], [out, out, down], tween(down, sit, 3))
        eat = stand.with_(head=(32.0, 36.6), chest=(32.0, 39.6))
        a["eat"] = [eat, eat.with_(mouth=0.3, head=(32.0, 36.2)), eat, eat.with_(head=(32.0, 36.9))]
        a["eat_start"] = tween(stand, eat, 3)
        a["eat_end"] = tween(eat, stand, 3)
    else:
        eat = stand.with_(head=(32.0, 33.5))
        a["eat"] = [eat, eat.with_(head=(32.0, 33.1)), eat, eat.with_(head=(32.0, 33.8))]
        a["eat_start"] = tween(stand, eat, 3)
        a["eat_end"] = tween(eat, stand, 3)
    return a


def build():
    """{key: [pose, ...]} together with the view each key is drawn in."""
    out = {}
    for name, poses in side_anims().items():
        out[f"{name}_right"] = ("side", poses)
    for view in ("front", "back"):
        for name, poses in front_anims(view).items():
            out[f"{name}_{view}"] = (view, poses)
    return out


def head_points():
    """{key: [(mouth, crown), ...]} for every animation, left views
    mirrored from the right (art pixels on the 64 x 64 canvas)."""
    out = {}
    for key, (view, poses) in build().items():
        pts = [ca.head_points(view, p) for p in poses]
        out[key] = pts
        if key.endswith("_right"):
            out[key[:-len("_right")] + "_left"] = [(None if m is None else (ca.W - m[0], m[1]), (ca.W - c[0], c[1]))
                                                   for m, c in pts]
    return out


def render_all(progress=None):
    """{key: [Surface, ...]} including the ``__blink`` twins."""
    lib = {}
    cache = {}

    def draw(view, pose):
        k = (view, repr(sorted(pose.items())))
        hit = cache.get(k)
        if hit is None:
            hit = ca.DRAW[view](pose)
            cache[k] = hit
        return hit

    items = build()
    for i, (key, (view, poses)) in enumerate(items.items()):
        lib[key] = [draw(view, p) for p in poses]
        if view != "back" and any(p.get("eye", 1.0) > 0.75 for p in poses):
            lib[key + "__blink"] = [draw(view, p.with_(eye=0.0)) if p.get("eye", 1.0) > 0.75 else
                                    draw(view, p) for p in poses]
        if progress:
            progress(i + 1, len(items))
    return lib


# Art pixels the body covers per gait cycle (for distance-locked playback).
STRIDES = {
    "walk": WALK_STRIDE * SCALE,
    "trot": TROT_STRIDE * SCALE,
    "run": RUN_STRIDE * SCALE,
    "stalk": STALK_STRIDE * SCALE,
}
# Front/back views have no planted-paw geometry to honour; these give a
# cadence that matches the side view at the same speed.
STRIDES_VERTICAL = {"walk": 11.0, "trot": 15.0, "run": 26.0, "stalk": 7.0}
