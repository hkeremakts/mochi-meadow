"""The cat.

Body: Mochi moves with a heading and a speed.  She steers along smooth
any-angle routes, slows into bends, and pivots in place (with shuffling
steps) when she needs to turn right around.  The sprite view (side, front
or back) follows the heading with a little hysteresis, and gait playback
is locked to the distance covered, so paws stay planted.  Postures change
through real transitions: she sits down, lies down, curls up, gets up.
She blinks, glances about and stretches when she wakes.

Mind: a set of needs (energy, hunger, thirst, grooming, play) and a
repertoire of activities written as generators, so each one reads like a
script: walk to the bush, sit, lie down, doze off, wake, yawn, stretch.
"""

import math
import random

import pygame

from .. import cat_anims, cat_art, pixelrig
from ..assets import generated_library
from ..config import (CAT_ANCHOR, CAT_RUN_SPEED, CAT_STALK_SPEED, CAT_TROT_SPEED, CAT_WALK_SPEED, MEAL_TIMES,
                      NEED_RATES)
from ..paths import clear_line, find_path
from ..personality import Personality
from ..places import ago
from ..chance import Drift, lognormal, sample
from ..settings import SETTINGS
from ..shade import SQUASH
from ..terrain import Spot
from ..util import approach, clamp
from .base import Entity

TAU = 2 * math.pi
HEADING = {"right": 0.0, "down": math.pi / 2, "left": math.pi, "up": -math.pi / 2}
VIEW_OF = {"right": "right", "left": "left", "down": "front", "up": "back"}
FACING_OF = {v: k for k, v in VIEW_OF.items()}
FACING_OF.update({"fr": "right", "br": "right", "fl": "left", "bl": "left"})
QUARTERS = ("fr", "br", "fl", "bl")
SIDE_OF = {"fr": "right", "br": "right", "fl": "left", "bl": "left"}
WALKING = SETTINGS["mochi"]["walking"]
GAIT_SPEED = {"stalk": CAT_STALK_SPEED, "amble": WALKING["amble_speed"], "walk": CAT_WALK_SPEED,
              "brisk": WALKING["brisk_speed"], "trot": CAT_TROT_SPEED, "run": CAT_RUN_SPEED}
# Acceleration and braking as multiples of the gait's cruising speed.
GAIT_ACCEL = 2.6
GAIT_DECEL = 3.2
PIVOT_RATE = 4.2          # rad/s when turning on the spot
ARRIVE_RADIUS = 12.0      # art pixels from the goal where she lines up for the last steps
# Steering like a walking animal: she aims at a point a little way along her
# route (so she curves into bends before she reaches them), and the faster
# she goes the wider she has to turn.
LOOKAHEAD = 12.0          # art pixels ahead along the route
TURN_RADIUS = 12.0        # art pixels: her tightest curve at a walk
TURN_MIN, TURN_MAX = 1.4, 3.2    # rad/s, slowest (just setting off) and fastest (at a trot) she swings round
SHARP = math.radians(125)        # sharper than this at a slow walk: she turns on the spot first
FROM_REST = math.radians(70)     # ...and from a standstill, more than this: a few steps round, then off on a gentle curve
# Turning on the spot is a few deliberate steps, not a spin.
TURN_STEP = 0.18          # seconds a step takes...
TURN_REST = 0.08          # ...and the pause before the next
TURN_STEP_ANGLE = math.radians(34)
LEISURELY = ("amble", "walk", "brisk")
POSTURES = ("stand", "sit", "lie", "sleep")
SLEEP_IN = {"loaf": "doze", "curl": "curlup", "flat": "sprawl"}
SLEEP_OUT = {"loaf": "undoze", "curl": "uncurl", "flat": "unsprawl"}
ARRIVED, PARTIAL, UNREACHABLE = "arrived", "partial", "unreachable"
MOCHI = SETTINGS["mochi"]
COOL = MOCHI["cooldowns"]
RAIN = SETTINGS["mochi"]["rain"]
SHADE = SETTINGS["shade"]
DRIZZLE_CHANCE = RAIN["drizzle_chance"]   # per look-round (every 0.35 s): about once in five minutes of drizzle
PLACE = MOCHI["places"]
AIR = MOCHI["body_language"]
WORTH_REMEMBERING = ("mouse", "fox", "deer", "hedgehog")   # creatures whose places she goes back to

_LIBRARY = {}
_EYES = {}
_POINTS = {}


def _head_points():
    if not _POINTS:
        _POINTS.update(cat_anims.head_points())
    return _POINTS
EYE_HIGHLIGHT = cat_art.EYE_SHINE


def eye_pixels(frame):
    """Positions of the eye highlights in a frame (none when the eyes are
    closed or the head is turned away)."""
    hit = _EYES.get(frame)
    if hit is None:
        w, h = frame.get_size()
        hit = [(x, y) for y in range(h) for x in range(w)
               if frame.get_at((x, y)).a and tuple(frame.get_at((x, y)))[:3] == EYE_HIGHLIGHT]
        _EYES[frame] = hit
    return hit


def with_left(lib):
    """Add the left-facing frames: mirrors of the right-facing ones (side
    and three-quarter views)."""
    for key in list(lib):
        twin = cat_anims.mirror_key(key)
        if twin:
            lib[twin] = [pygame.transform.flip(f, True, False) for f in lib[key]]
    return lib


def cat_library():
    """Mochi's frames, drawn once and cached under assets/generated."""
    if not _LIBRARY:
        sources = [cat_art.__file__, cat_anims.__file__, pixelrig.__file__]
        _LIBRARY.update(with_left(generated_library("mochi", sources, cat_anims.render_all)))
    return _LIBRARY


def wrap(a):
    return (a + math.pi) % TAU - math.pi


# Eight views round the compass (screen y points down, so "front" is
# heading down, toward you): degrees of heading each one covers.
SECTORS = {"right": (-25, 25), "fr": (25, 68), "front": (68, 112), "fl": (112, 155),
           "br": (-68, -25), "back": (-112, -68), "bl": (-155, -112)}


def view_for(heading, current=None, margin=math.radians(10)):
    """Which sprite view shows a cat moving along ``heading``: side-on,
    three-quarters toward you or away, face-on or from behind (the left
    side, and the left three-quarters, are mirrors).  The current view is
    kept until the heading is clearly past its edge, so the sprite does
    not flicker on a boundary."""
    a = math.degrees(wrap(heading))

    def inside(view, extra):
        if view == "left":
            return abs(a) >= 155 - extra
        lo, hi = SECTORS[view]
        return lo - extra <= a <= hi + extra

    if current is not None and inside(current, math.degrees(margin)):
        return current
    for view in SECTORS:
        if inside(view, 0):
            return view
    return "left"


class Mark:
    """Something to pounce on that isn't a creature: a shadow, a leaf."""

    airborne = False
    hidden = False

    def __init__(self, kind, x, y):
        self.kind, self.x, self.y = kind, x, y
        self.alive = True


class Needs:
    __slots__ = ("energy", "hunger", "thirst", "groom", "play")

    def __init__(self, rng):
        self.energy = rng.uniform(0.6, 0.9)
        self.hunger = rng.uniform(0.2, 0.5)
        self.thirst = rng.uniform(0.2, 0.5)
        self.groom = rng.uniform(0.2, 0.5)
        self.play = rng.uniform(0.4, 0.7)

    def clamp(self):
        for name in self.__slots__:
            setattr(self, name, clamp(getattr(self, name), 0.0, 1.0))


class Cat(Entity):
    kind = "cat"
    TRACK = "cat"           # the prints she leaves (marks.py)

    def __init__(self, world, x, y, name="Mochi"):
        super().__init__(world, x, y)
        mochi = type(self) is Cat
        self.p = (getattr(world, "personality", None) if mochi else None) or Personality.neutral()
        self.name = self.p.name if mochi else name
        self.lib = cat_library()
        self.rng = world.rng
        self.needs = Needs(self.rng)
        self.heading = HEADING[self.rng.choice(("left", "right"))]
        self.view = view_for(self.heading)
        self.posture = "sleep"
        self.sleep_style = "curl"
        self.speed = 0.0
        self.moved = 0.0
        self.dt = 0.0
        self.wiggle = 0.0
        self.state = "sleeping"
        self.label = "waking up"
        self.focus = None
        self.sheltered = False
        self.activity = None
        self.activity_name = ""
        self.interruptible = True
        self._perceive_timer = 0.0
        self._cooldowns = {}
        self._ignored = {}  # prey.serial -> time until which the cat ignores it
        self._noticed = set()     # serials of creatures whose place she has already remembered
        self.air = None           # how she carries her tail and ears: happy, cross, wary, or calm (None)
        self.strides = cat_anims.STRIDES                      # art pixels a gait cycle covers (a kitten's are shorter)
        self.strides_quarter = cat_anims.STRIDES_QUARTER
        self._step_clock = 0.0                                # where she is in a step, turning on the spot
        # How she walks varies by its own random numbers, so the walking
        # doesn't change what she decides to do in a seeded meadow.
        self.gait_rng = random.Random(getattr(world, "seed", 0) * 7 + 3)
        self._stroll = Drift(self.gait_rng, 0.0, WALKING["pace_drift"], 3.0)     # a walk's pace wanders a little
        self.strides_vertical = cat_anims.STRIDES_VERTICAL
        self.wet = 0.0            # seconds of rain her coat has taken
        self._blink = 0.0
        self._next_blink = self.rng.uniform(1.0, 4.0)
        self.carrying = None      # the name of a gift in her mouth
        self._dressed = {}
        self.pace = sample(self.rng, MOCHI["pace"])
        self._mood_wander = Drift(self.rng, 0.0, MOCHI["mood_wander"], 600.0)
        self.idle_pose()
        self._first_scene()

    def _first_scene(self):
        """Pick up the meadow mid-life: by day Mochi wakes as you arrive; at
        night (or in the rain) she is already asleep under a bush and stays
        that way until she's rested."""
        env = self.world.env
        spots = self.world.terrain.spots
        shelters = spots["roof"] if (env.rain > 0.35 and spots["roof"]) else spots["shelter"] or spots["roof"]
        if (env.is_night or env.rain > 0.35) and shelters and type(self) is Cat:
            spot = self.rng.choice(shelters)
            self.x, self.y = float(spot.x), float(spot.y)
            self.facing = spot.facing
            self.sleep_style = "curl"
            self.idle_pose()
            self.needs.energy = self.rng.uniform(0.2, 0.45)
            self._start("nap", self.act_sleep_on())
        else:
            self._start("wake", self.act_wake(), interruptible=False)

    # ======================================================================
    # Frame update

    def update(self, dt):
        self.dt = dt
        self.moved = 0.0
        self._update_needs(dt)
        self._update_blink(dt)
        self._perceive_timer -= dt
        if self._perceive_timer <= 0.0:
            self._perceive_timer = 0.35
            if type(self) is Cat:
                self._notice()
            self._carry(self._read_air())
            self._soak(0.35)
            self._perceive()
        if self.activity is None:
            self._start(*self._choose())
        try:
            next(self.activity)
        except StopIteration:
            self.activity = None
            self.interruptible = True
            self.focus = None
        self.anim.update(dt, self.moved)

    def _start(self, name, generator, interruptible=True):
        if self.activity is not None:
            self.activity.close()
        if type(self) is Cat:
            self.world.stats[name] += 1
        self.carrying = None      # whatever she had, she drops
        self.z = 0.0
        self.wiggle = 0.0
        self.activity = generator
        self.activity_name = name
        self.interruptible = interruptible
        self.focus = None

    def _update_needs(self, dt):
        n = self.needs
        p = self.p
        tires = p.lean("lazy", 0.75, 1.3) / self.world.day.energy      # a sleepy day tires her sooner
        if self.posture == "sleep":
            n.energy += NEED_RATES["energy_sleep"] * dt * p.lean("lazy", 1.3, 0.7)   # lazy cats sleep longer
        elif self.speed > 55 or self.activity_name in ("hunt", "zoomies", "butterfly"):
            n.energy += NEED_RATES["energy_active"] * dt * tires
        else:
            n.energy += NEED_RATES["energy_awake"] * dt * tires
        n.hunger += NEED_RATES["hunger"] * dt
        n.thirst += NEED_RATES["thirst"] * dt * (1.6 if self.speed > 55 else 1.0)
        n.groom += NEED_RATES["groom"] * dt
        if self.activity_name not in ("hunt", "butterfly", "zoomies"):
            n.play += NEED_RATES["play"] * dt * p.lean("playful", 0.7, 1.4)
        n.clamp()
        p.settle(dt)
        if type(self) is Cat:
            before = self._mood_wander.value
            p.feel(self._mood_wander.step(dt) - before)     # moods drift a little of their own accord

    def _update_blink(self, dt):
        if self._blink > 0:
            self._blink -= dt
            return
        self._next_blink -= dt
        if self._next_blink <= 0:
            relaxed = self.posture in ("sit", "lie")
            # A slow blink now and then: a contented cat's signature.
            slow = 0.12 + 0.25 * self.p["affectionate"] + 0.2 * max(0.0, self.p.mood)
            self._blink = 0.45 if (relaxed and self.rng.random() < slow) else 0.12
            self._next_blink = self.rng.uniform(2.0, 6.0)
            if self.rng.random() < 0.15:
                self._next_blink = 0.25  # a double blink

    # ======================================================================
    # Drawing

    def sprite(self):
        frame = self.anim.frame
        if self._blink > 0 and self.anim.key:
            twin = self.lib.get(self.anim.key + "__blink")
            if twin:
                frame = twin[self.anim.index]
        bow = self.birthday
        if (self.carrying or bow) and self.anim.key:
            frame = self._dress(frame, self.anim.key, self.anim.index, self.carrying, bow)
        ax, ay = CAT_ANCHOR
        return frame, (ax - self.wiggle, ay), False

    @property
    def birthday(self):
        """On the day she was first met (in later years) she wears a bow."""
        born = getattr(self.p, "born", None)
        if not born or type(self) is not Cat:
            return False
        today = self.world.env.clock.date
        return (today.month, today.day) == (born.month, born.day) and today.year > born.year

    def _dress(self, frame, key, index, carrying, bow):
        """The frame with a gift in her mouth and/or a bow on her head.
        Made once per frame and kept, so the renderer's cache still works."""
        k = (frame, carrying, bow)
        hit = self._dressed.get(k)
        if hit is None:
            from .wildlife import art
            base = key.split("__")[0]
            pts = _head_points().get(base)
            hit = frame
            if pts and index < len(pts):
                mouth, crown = pts[index]
                hit = frame.copy()
                if bow:
                    b = art()["bow"]
                    hit.blit(b, (round(crown[0] - 1.5), round(crown[1] - 1.5)))
                if carrying and mouth is not None:
                    g = art()["gifts"][carrying]
                    flip = key.rsplit("_", 1)[-1] in ("left", "fl", "bl")
                    g = pygame.transform.flip(g, True, False) if flip else g
                    gx = mouth[0] - (g.get_width() - 1 if flip else 0)
                    hit.blit(g, (round(gx), round(mouth[1] - g.get_height() / 2)))
            if len(self._dressed) > 4000:
                self._dressed.clear()
            self._dressed[k] = hit
        return hit

    def shadow(self):
        side, quarter = self.side_view, self.quarter_view
        if self.posture in ("lie", "sleep"):
            rx, ry, dy = 16.0, 3.6, -3
        elif self.posture == "sit":
            rx, ry, dy = (10.0, 3.2, -1) if side else (9.2, 3.3, -1) if quarter else (8.5, 3.2, -1)
        else:
            rx, ry, dy = (14.5, 3.4, -1) if side else (11.0, 3.8, -1) if quarter else (7.0, 4.0, 0)
        k = 1.0 / (1.0 + self.z * 0.07)
        return rx * k, ry * k, int(76 * k), dy

    @property
    def airborne(self):
        return False  # the cat always sorts by its ground position

    def draw_glow(self, r):
        """Eyeshine: in the dark, the cat's eyes catch the light."""
        env = self.world.env
        if env.sun > 0.25:
            return
        frame, _, _ = self.sprite()
        strength = 1.0 - env.sun / 0.25
        ax, ay = CAT_ANCHOR
        ox = self.x - ax + self.wiggle
        oy = self.y - self.z - ay
        color = (int(70 * strength), int(150 * strength), int(110 * strength))
        for x, y in eye_pixels(frame):
            r.blit_px(r.dot(color, 255, 1, 1), ox + x, oy + y, add=True)

    # ======================================================================
    # Facing

    @property
    def facing(self):
        return FACING_OF[self.view]

    @facing.setter
    def facing(self, name):
        self.heading = HEADING[name]
        self.view = VIEW_OF[name]

    @property
    def side_view(self):
        return self.view in ("left", "right")

    @property
    def quarter_view(self):
        return self.view in QUARTERS

    def heading_to(self, x, y):
        return math.atan2(y - self.y, x - self.x)

    # ======================================================================
    # Animation helpers

    def key_for(self, name, view=None):
        key = f"{name}_{view or self.view}"
        return key if key in self.lib else None

    def _side_on_for(self, name):
        """At three-quarters, something only drawn side-on (a sniff, a
        pounce): she turns side-on for it, the nearer side."""
        if self.quarter_view and self.key_for(name) is None:
            side = SIDE_OF[self.view]
            if self.key_for(name, side) is not None:
                self.view = side
                self.heading = HEADING[side]

    def show(self, name, fps=None, stride=None, loop=True, restart=False, keep_phase=False):
        self._side_on_for(name)
        key = (self.air and self.key_for(f"{name}~{self.air}")) or self.key_for(name) or self.key_for("stand")
        self.anim.play(key, self.lib[key], fps=fps, stride=stride, loop=loop, restart=restart,
                       keep_phase=keep_phase)

    def once(self, name, fps=8.0):
        self._side_on_for(name)
        if self.key_for(name) is None:
            return
        self.show(name, fps=fps, loop=False, restart=True)
        while not self.anim.done:
            yield

    def idle_pose(self):
        rng = self.rng
        if self.posture == "sleep":
            self.state = "sleeping"
            self.show(f"sleep_{self.sleep_style}", fps=rng.uniform(0.9, 1.2))
        elif self.posture == "lie":
            self.state = "lying"
            self.show("lie", fps=rng.uniform(2.5, 3.5))
        elif self.posture == "sit":
            self.state = "sitting"
            self.show("sit", fps=rng.uniform(3.0, 4.2))
        else:
            self.state = "idle"
            self.show("stand", fps=rng.uniform(4.0, 5.5))

    # ======================================================================
    # Body language

    def _read_air(self):
        """How she carries herself now.  Wary (ears flat, tail low) when the
        fox is about or the rain is on her fur, whatever her mood; otherwise
        her mood shows: happy or cross, each held until it has properly
        faded, so she doesn't flicker on the edge of one."""
        if self.posture == "sleep":
            return None
        world = self.world
        wet = self._exposed()
        fox = any(e.kind == "fox" and e.alive and not getattr(e, "hidden", False)
                  and self.distance_to(e) < MOCHI["fox_fear_distance"] for e in world.entities)
        if wet or fox or world.storm is not None or self.activity_name == "hide":
            return "wary"
        if any(getattr(e, "scolding", None) is self for e in world.entities):
            return "cross"          # a blackbird telling her off: her ears go back
        mood, give = self.p.mood, AIR["settle"]
        if mood < AIR["cross_below"] + (give if self.air == "cross" else 0.0):
            return "cross"
        if mood > AIR["happy_above"] - (give if self.air == "happy" else 0.0):
            return "happy"
        return None

    def _exposed(self):
        """Out in the rain, away from cover."""
        env = self.world.env
        return (env.rain > RAIN["drizzle_above"] and not self.sheltered
                and not self.world.terrain.under_roof(self.x, self.y))

    def _soak(self, dt):
        """Rain soaks her coat (drizzle only a little); it dries slowly."""
        if self._exposed():
            self.wet += dt * min(1.0, self.world.env.rain / RAIN["shelter_above"])
        else:
            self.wet = max(0.0, self.wet - dt * 0.007)

    def shake_off(self):
        """Wet through: a good shake with the droplets flying, then a long
        groom.  Only a little damp, and the groom is enough."""
        if self.wet < RAIN["wet_shake"]:
            yield from self.to_posture("sit")
            yield from self.once("groom", fps=8)
            self.idle_pose()
            return
        if self.posture != "stand":
            yield from self.to_posture("stand")
        if not self.side_view:
            yield from self.pivot(HEADING["right" if math.cos(self.heading) >= 0 else "left"])
        self.label = "shaking off the rain"
        self.world.particles.dust(self.x, self.y - 7, count=10, spread=7.0, color=(196, 212, 232))
        yield from self.once("shake", fps=14)
        self.idle_pose()
        self.wet = 0.0
        yield from self.to_posture("sit")
        self.label = "grooming the rain off"
        for _ in range(2):
            yield from self.once("groom", fps=8)
        self.idle_pose()

    def _carry(self, air):
        """Change how she carries herself: the clip playing now is swapped
        for its twin in the new mood, at the same point in its cycle."""
        if air == self.air:
            return
        self.air = air
        key = self.anim.key
        if not key:
            return
        clip, view = key.rsplit("_", 1)
        name = clip.split("~")[0]
        if name not in cat_anims.AIRED:
            return
        new = (air and self.key_for(f"{name}~{air}", view)) or self.key_for(name, view)
        if new and new != key:
            self.anim.play(new, self.lib[new], fps=self.anim.fps, stride=self.anim.stride, loop=self.anim.loop,
                           keep_phase=True)

    def wait(self, seconds):
        elapsed = 0.0
        while elapsed < seconds:
            elapsed += self.dt
            yield

    def _gait_anim(self, gait):
        """The clip for how fast she is really going: a walk that's only
        getting going (or winding down) is an amble."""
        ambling = (self.anim.key or "").startswith("amble")
        if gait == "stalk":
            name = "stalk"
        elif self.speed > 66:
            name = "run"
        elif self.speed > 36:
            name = "trot"
        elif gait == "amble" or self.speed < (20.0 if ambling else 17.0):
            name = "amble"
        else:
            name = "walk"
        strides = self._strides()
        self.show(name, stride=strides[name], keep_phase=True)

    # ======================================================================
    # Posture

    def to_posture(self, target, style=None):
        """Change posture through the in-between frames: stand <-> sit <->
        lie <-> sleep, one step at a time."""
        if style is not None and target == "sleep" and self.posture == "sleep" and style != self.sleep_style:
            yield from self.once(SLEEP_OUT[self.sleep_style], fps=5)
            self.posture = "lie"
        if style is not None:
            self.sleep_style = style
        while self.posture != target:
            here = POSTURES.index(self.posture)
            there = POSTURES.index(target)
            if there > here:
                if self.posture == "stand":
                    yield from self.once("sitdown", fps=9)
                    self.posture = "sit"
                elif self.posture == "sit":
                    if not self.side_view:
                        # Lying down is a side-on pose: stand, turn, resettle.
                        yield from self.once("standup", fps=9)
                        self.posture = "stand"
                        side = "right" if math.cos(self.heading) >= 0 else "left"
                        yield from self.pivot(HEADING[side])
                        continue
                    yield from self.once("liedown", fps=7)
                    self.posture = "lie"
                else:
                    yield from self.once(SLEEP_IN[self.sleep_style], fps=4)
                    self.posture = "sleep"
            else:
                if self.posture == "sleep":
                    yield from self.once(SLEEP_OUT[self.sleep_style], fps=5)
                    self.posture = "lie"
                elif self.posture == "lie":
                    yield from self.once("situp", fps=7)
                    self.posture = "sit"
                else:
                    yield from self.once("standup", fps=9)
                    self.posture = "stand"
        self.idle_pose()

    # ======================================================================
    # Locomotion

    def pivot(self, heading, stand=True):
        """Turn on the spot, stepping around, through whichever views lie
        between."""
        if self.posture != "stand":
            yield from self.to_posture("stand")
        while True:
            diff = wrap(heading - self.heading)
            if abs(diff) < 0.04:
                self.heading = heading
                self.view = view_for(heading, self.view)
                break
            self.speed = approach(self.speed, 0.0, 120.0 * self.dt)
            self._turn_in_steps(diff, "stalk" if not stand else "walk")
            yield
        if stand:
            self.idle_pose()

    def _turn_in_steps(self, diff, gait="walk"):
        """One frame of turning on the spot, a step at a time: the paws
        step round about a third of a right angle, a short pause, the next
        step.  The legs only move while a step is being taken."""
        period = TURN_STEP + TURN_REST
        self._step_clock = (self._step_clock + self.dt) % period
        if self._step_clock < TURN_STEP:
            turn = math.copysign(min(abs(diff), TURN_STEP_ANGLE / TURN_STEP * self.dt), diff)
            self.heading = wrap(self.heading + turn)
            stride = self._strides()["walk"]
            self.moved = stride / 4 / TURN_STEP * self.dt       # a quarter of a walk cycle a step
        else:
            self.moved = 0.0
        self.view = view_for(self.heading, self.view)
        self._gait_anim(gait)

    def _strides(self):
        """Art pixels a gait cycle covers, as she's seen just now."""
        if self.side_view:
            return self.strides
        return self.strides_quarter if self.quarter_view else self.strides_vertical

    def _ready(self, gx, gy):
        """A moment before setting off, as a cat takes; heading toward you,
        she glances your way first."""
        rng = self.gait_rng
        yield from self.wait(lognormal(rng, 0.22, 0.5))
        heading = self.heading_to(gx, gy)
        if self.side_view and math.sin(heading) > 0.6 and rng.random() < WALKING["glance"]:
            self.show("stand_look", fps=4)
            yield from self.wait(rng.uniform(0.3, 0.7))
            self.idle_pose()

    def _aim(self, points, i):
        """The point LOOKAHEAD along the route from her: aiming there curves
        her into each bend before she reaches it."""
        left = LOOKAHEAD
        x, y = self.x, self.y
        for k in range(i, len(points)):
            px, py = points[k]
            seg = math.hypot(px - x, py - y)
            if seg >= left:
                return x + (px - x) * left / seg, y + (py - y) * left / seg
            left -= seg
            x, y = px, py
        return points[-1]

    def _bend_ahead(self, points, i):
        """How sharply the route turns at the next corner, if it's close."""
        if i + 1 >= len(points):
            return 0.0
        ax, ay = points[i]
        if math.hypot(ax - self.x, ay - self.y) > LOOKAHEAD * 2:
            return 0.0
        bx, by = points[i + 1]
        into = math.atan2(ay - self.y, ax - self.x)
        out = math.atan2(by - ay, bx - ax)
        return abs(wrap(out - into))

    def face(self, target, stand=True):
        """Pivot toward a facing name, a heading, or an (x, y) point."""
        if isinstance(target, str):
            heading = HEADING[target]
        elif isinstance(target, tuple):
            heading = self.heading_to(*target)
        else:
            heading = target
        if self.posture != "stand" and view_for(heading, self.view) == self.view:
            return  # already looking that way; no need to get up
        yield from self.pivot(heading, stand=stand)

    def go(self, gx, gy, gait="walk", max_time=None, stop=True, stand=True, dawdle=False):
        """Steer along a route to (gx, gy).

        She aims a little way along the route, so bends become curves; how
        sharply she can turn depends on how fast she's going; she eases off
        before a sharp corner, and her pace drifts a little as she goes.
        From a standstill she sets off on a curve, unless the way is nearly
        behind her: then she turns on the spot first, in steps.  With
        ``dawdle`` (a leisurely walk) she now and then stops to sniff or
        look about before going on.

        Returns ARRIVED, PARTIAL (ran out of ``max_time``) or UNREACHABLE.
        UNREACHABLE comes back without consuming a frame, so loops that
        retry must not spin on it.  With ``stop`` False a PARTIAL walk keeps
        its momentum so the next call carries on without a hitch."""
        terrain = self.world.terrain
        route = find_path(terrain.blocked, (self.x, self.y), (gx, gy), wide=terrain.blocked_wide)
        if route is None:
            return UNREACHABLE
        if self.posture != "stand":
            yield from self.to_posture("stand")
        base = GAIT_SPEED[gait] * self.pace
        accel, decel = base * GAIT_ACCEL, base * GAIT_DECEL
        points = [(float(x), float(y)) for x, y in route]
        if points and self.speed < 1.0 and gait in LEISURELY and math.dist(points[-1], (self.x, self.y)) > 20:
            yield from self._ready(*points[0])
        i = 0
        elapsed = 0.0
        closing = 0.0          # seconds spent on the final approach
        status = ARRIVED
        replans = 0
        while points:
            tx, ty = points[i]
            dx, dy = tx - self.x, ty - self.y
            d = math.hypot(dx, dy)
            last = i == len(points) - 1
            if not last and d < LOOKAHEAD * 0.6:
                i += 1
                continue
            if last and d < 0.6:
                self.x, self.y = tx, ty
                break
            remaining = d + sum(math.dist(points[k], points[k + 1]) for k in range(i, len(points) - 1))
            final = last and remaining < ARRIVE_RADIUS
            ax, ay = (tx, ty) if final else self._aim(points, i)
            if (ax, ay) != (tx, ty) and not clear_line(terrain.blocked, (self.x, self.y), (ax, ay)):
                ax, ay = tx, ty          # no cutting the corner where it would clip a bush or the bank
            diff = wrap(math.atan2(ay - self.y, ax - self.x) - self.heading)
            if final:
                closing += self.dt
                if closing > 3.0:
                    # Something keeps her from curving in: just step the last bit.
                    yield from self.step_to(tx, ty)
                    break
            step = 0.0
            if final and abs(diff) > math.radians(40):
                # Close, but not facing it: a curve that tight can't be walked
                # (she'd circle the spot), so brake and turn to it first.
                self.speed = approach(self.speed, 0.0, decel * 2.0 * self.dt)
                if self.speed > 2.0:
                    turn = math.copysign(min(abs(diff), PIVOT_RATE * self.dt), diff)
                    self.heading = wrap(self.heading + turn)
                    step = min(self.speed * self.dt, d * 0.5)
                    self.moved = step
                else:
                    self._turn_in_steps(diff)
            elif abs(diff) > (FROM_REST if self.speed < 3.0 else SHARP) and self.speed < base * 0.5:
                # Well round from where she's facing: turn on the spot, a step
                # at a time (a wide swing would take her off her route).
                self.speed = approach(self.speed, 0.0, decel * self.dt)
                self._turn_in_steps(diff)
            else:
                rate = clamp(self.speed / TURN_RADIUS, TURN_MIN, TURN_MAX)
                self.heading = wrap(self.heading + clamp(diff, -rate * self.dt, rate * self.dt))
                cruise = base * (1.0 + self._stroll.step(self.dt))
                bend = self._bend_ahead(points, i)
                ease = 1.0 - 0.45 * clamp((bend - 0.6) / 1.6, 0.0, 1.0)       # slow into a sharp corner
                floor = 0.0 if final else 0.3
                target = min(cruise * ease * max(floor, math.cos(diff)), math.sqrt(2.0 * decel * remaining) + 0.5)
                self.speed = approach(self.speed, target, (accel if target > self.speed else decel) * self.dt)
                step = min(self.speed * self.dt, remaining)
                self.moved = step
            if step > 0:
                nx = self.x + math.cos(self.heading) * step
                ny = self.y + math.sin(self.heading) * step
                if not terrain.walkable(nx, ny) and terrain.walkable(self.x, self.y):
                    # Grazing an edge on a bend: step straight at the
                    # waypoint, or slide along the edge.
                    straight = math.atan2(dy, dx)
                    for a in (straight, straight + 0.4, straight - 0.4, straight + 0.8, straight - 0.8):
                        nx, ny = self.x + math.cos(a) * step, self.y + math.sin(a) * step
                        if terrain.walkable(nx, ny):
                            break
                    if not terrain.walkable(nx, ny):
                        self.speed = 0.0
                        off = wrap(straight - self.heading)
                        if abs(off) > 0.5:
                            # Up against an edge, facing the wrong way: turn
                            # to the way out first (replanning won't help).
                            self._turn_in_steps(off)
                            yield
                            continue
                        route = find_path(terrain.blocked, (self.x, self.y), (gx, gy), wide=terrain.blocked_wide) if replans < 3 else None
                        replans += 1
                        if not route:
                            status = UNREACHABLE if route is None else ARRIVED
                            break
                        points = [(float(x), float(y)) for x, y in route]
                        i = 0
                        yield
                        continue
                self.x, self.y = nx, ny
            self.view = view_for(self.heading, self.view)
            self.state = "moving"
            self._gait_anim(gait)
            if gait == "run" and self.rng.random() < self.dt * 3.0:
                self.world.particles.dust(self.x - math.cos(self.heading) * 10, self.y, count=2, spread=2.0)
            elapsed += self.dt
            if max_time is not None and elapsed >= max_time:
                status = PARTIAL
                break
            if dawdle and not final and remaining > 50 and self.gait_rng.random() < self.dt * WALKING["dawdle_rate"]:
                yield from self._dawdle()
            yield
        if status == ARRIVED or stop:
            yield from self.settle(stand=stand, gait=gait)
        return status

    def _dawdle(self):
        """A pause on the way: a sniff at something, or a look about."""
        label = self.label
        rng = self.gait_rng
        yield from self.settle()
        if self.side_view and rng.random() < 0.6:
            self.label = "sniffing the grass"
            yield from self.once("sniff_start", fps=8)
            self.show("sniff", fps=5)
            yield from self.wait(rng.uniform(0.8, 2.0))
        else:
            self.label = "looking around"
            if self.side_view and rng.random() < 0.5:
                self.show("stand_look", fps=4)
            yield from self.wait(rng.uniform(0.6, 1.6))
        self.idle_pose()
        self.label = label

    def settle(self, stand=True, gait="walk"):
        """Come to a stop.  With ``stand`` False the gait frame freezes
        mid-stride, which is exactly how a stalking cat stops."""
        decel = max(60.0, self.speed * GAIT_DECEL)
        while self.speed > 0.5:
            self.speed = approach(self.speed, 0.0, decel * self.dt)
            step = self.speed * self.dt
            nx = self.x + math.cos(self.heading) * step
            ny = self.y + math.sin(self.heading) * step
            if self.world.terrain.walkable(nx, ny):
                self.x, self.y = nx, ny
                self.moved = step
            else:
                self.speed = 0.0
            self._gait_anim(gait)
            yield
        self.speed = 0.0
        if stand:
            self.idle_pose()

    def go_to_spot(self, spot, gait="walk", dawdle=False, loose=False):
        """Walk to a spot and face the way it wants.  A ``loose`` spot (a
        place to nap or loaf, out of the rain or into the shade) doesn't
        care which way she lies: she keeps the side she's facing, rather
        than turning round on arrival."""
        status = yield from self.go(*spot.approach, gait=gait, dawdle=dawdle)
        if status != ARRIVED:
            return False
        if (spot.x, spot.y) != tuple(spot.approach):
            # The last step may enter a blocked margin (under a bush, onto
            # the bank), so it is walked directly.
            yield from self.step_to(spot.x, spot.y)
        if loose:
            if not self.side_view:
                yield from self.face("right" if math.cos(self.heading) >= 0 else "left")
        elif self.facing != spot.facing:
            yield from self.face(spot.facing)
        return True

    def step_to(self, x, y, speed=CAT_WALK_SPEED * 0.7):
        heading = self.heading_to(x, y)
        if abs(wrap(heading - self.heading)) > 0.3 and math.hypot(x - self.x, y - self.y) > 5:
            yield from self.pivot(heading)       # (a step or two she just shuffles, without turning to it)
        while True:
            dx, dy = x - self.x, y - self.y
            d = math.hypot(dx, dy)
            if d < 0.5:
                self.x, self.y = float(x), float(y)
                break
            self.speed = approach(self.speed, min(speed, d * 4 + 3), speed * 3 * self.dt)
            step = min(d, self.speed * self.dt)
            self.x += dx / d * step
            self.y += dy / d * step
            self.moved = step
            self._gait_anim("walk")
            yield
        self.speed = 0.0
        self.idle_pose()

    # ======================================================================
    # Choosing what to do

    def _enough(self, setting):
        """How long until she's had enough of something (Weibull: the longer
        it goes on, the likelier she is to stop)."""
        return sample(self.rng, MOCHI[setting], self.world.day.spread)

    def _cooldown_ok(self, name):
        return self.world.time >= self._cooldowns.get(name, 0.0)

    def _cool(self, name, seconds):
        """Not again for about ``seconds``: more or less, as with any cat."""
        seconds = lognormal(self.rng, seconds, MOCHI["cooldown_spread"])
        self._cooldowns[name] = self.world.time + seconds

    def _choose(self):
        n = self.needs
        env = self.world.env
        spots = self.world.terrain.spots
        night = env.is_night
        twilight = env.clock.between(5.0, 7.5) or env.clock.between(18.5, 21.0)
        options = []
        sleepy = 0.22 + 0.26 * self.p["lazy"]      # a lazy cat calls it a day sooner
        if n.energy < sleepy or (night and n.energy < sleepy + 0.3):
            options.append(("nap", 2.5 + (sleepy + 0.3 - n.energy) * 8 + (2.5 if night else 0.0)))
        if n.hunger > 0.55 and spots["bowl"]:
            options.append(("eat", 2.0 + n.hunger * 4 + (12.0 if n.hunger > 0.85 else 0.0)))   # starving comes first
        if n.thirst > 0.55 and spots["drink"]:
            options.append(("drink", 2.0 + n.thirst * 4 + (12.0 if n.thirst > 0.85 else 0.0)))
        if n.groom > 0.55 and self._cooldown_ok("groom"):
            options.append(("groom", 1.0 + n.groom * 2.5))
        options.append(("wander", 2.0 + (0.8 if twilight else 0.0)))
        options.append(("sit", 1.6 + (0.6 if n.energy < 0.5 else 0.0)))
        if self._cooldown_ok("loaf"):
            options.append(("loaf", 1.0 + (1.0 if n.energy < 0.55 else 0.0) + (0.6 if env.sun > 0.6 else 0.0)))
        if n.groom > 0.3 and self._cooldown_ok("groom"):
            options.append(("groom", 0.4))
        if spots["watch"] and env.sun > 0.2 and self._cooldown_ok("watch_pond"):
            options.append(("watch_pond", 0.5))
        if n.energy > 0.6 and n.play > 0.7 and self._cooldown_ok("zoomies"):
            options.append(("zoomies", 0.3 + (0.6 if twilight else 0.0)))
        if self.world.terrain.bushes and self._cooldown_ok("explore"):
            options.append(("explore", 0.5))
        if self._cooldown_ok("meow"):
            options.append(("meow", 0.12))
        stories = getattr(self.world, "stories", None)
        if type(self) is Cat and stories is not None and self._cooldown_ok("watch_nest") and stories.nest_watchable():
            options.append(("watch_nest", 0.35))
        calls = self._recall()
        if calls:
            options.append(("revisit", PLACE["weight"] * min(1.5, sum(pull for _, pull in calls))))
        options += self._quirk_options()
        options = [(name, w * self._leaning(name)) for name, w in options]
        total = sum(w for _, w in options)
        r = self.rng.uniform(0, total)
        for name, w in options:
            r -= w
            if r <= 0:
                break
        return name, getattr(self, f"act_{name}")()

    def _leaning(self, activity):
        """How her character tilts the odds of an activity."""
        p = self.p
        env = self.world.env
        clock = env.clock
        night = env.is_night
        dawn = clock.between(4.8, 8.0)
        sunny = env.sun > 0.6 and env.weather.cloud < 0.45
        k = 1.0
        if activity == "nap":
            k = p.lean("lazy", 0.7, 1.4)
            if p.has("night owl"):
                k *= 0.5 if night else 1.4
            if p.has("early riser"):
                k *= 0.3 if dawn else (1.5 if clock.between(20.5, 23.0) else 1.0)
        elif activity == "loaf":
            k = p.lean("lazy") * (2.5 if p.has("loafer") else 1.0) * (1.8 if sunny and p.has("sunbather") else 1.0)
        elif activity == "sit":
            k = p.lean("lazy", 0.8, 1.3)
        elif activity == "zoomies":
            k = p.lean("playful", 0.3, 2.0) * (1.8 if night and p.has("night owl") else 1.0)
            k *= 0.4 if p.mood < -0.25 else 1.0
        elif activity == "explore":
            k = p.lean("curious", 0.4, 1.8)
        elif activity == "watch_pond":
            k = p.lean("curious", 0.6, 1.5) * (3.0 if p.has("pond gazer") else 1.0)
            k *= 2.0 if dawn and p.has("pond gazer") else 1.0
        elif activity == "wander":
            k = p.lean("curious", 0.8, 1.3)
            if (night and p.has("night owl")) or (dawn and p.has("early riser")):
                k *= 1.6
        elif activity == "meow":
            k = p.lean("affectionate", 0.3, 2.0)
        elif activity in ("revisit", "watch_nest"):
            k = p.lean("curious", 0.5, 1.8)
        elif activity == "groom":
            k = 1.4 if p.mood < -0.25 else 1.0
        return k

    def _afraid(self):
        """A timid cat doesn't wait to be curious about a fox: she hides."""
        if self.p["bold"] >= 0.35 or self.posture == "sleep" or self.activity_name == "hide":
            return False
        for e in self.world.entities:
            if e.kind == "fox" and e.alive and not e.hidden and self.distance_to(e) < SETTINGS["mochi"]["fox_fear_distance"]:
                if self.world.terrain.spots["shelter"]:
                    self.p.feel(-0.2)
                    self._start("hide", self.act_hide_from(e))
                    return True
        return False

    def _quirk_options(self):
        """Things only some cats do."""
        p = self.p
        out = []
        if p.has("bowl watcher") and self._cooldown_ok("wait_dinner") and self.world.terrain.spots["bowl"]:
            hour = self.world.env.hour
            if any(0 < meal - hour < 0.4 for meal in MEAL_TIMES):
                out.append(("wait_dinner", 6.0))
        return out

    def _notice(self):
        """Remember where she saw something worth coming back for: for a
        mouse, the bush it lives in; for anything else, the spot."""
        world = self.world
        self._noticed &= {e.serial for e in world.entities}
        if self.posture == "sleep":
            return
        t = world.terrain
        for e in world.entities:
            if (e.kind not in WORTH_REMEMBERING or not e.alive or getattr(e, "hidden", False)
                    or e.serial in self._noticed or self.distance_to(e) > PLACE["sight"]):
                continue
            home = getattr(e, "home", None) if e.kind == "mouse" else None
            if home is not None:
                spots = [s for s in t.spots["shelter"] if s.owner is home]
                if not spots:
                    continue
                spot = min(spots, key=lambda s: math.hypot(s.x - self.x, s.y - self.y))
                x, y = spot.approach
                look = (home.x, home.y)
            else:
                x, y, look = e.x, e.y, None
                if not (0 < x < world.width and 0 < y < world.height and t.walkable(x, y)):
                    continue      # not yet in the meadow, or out of reach: maybe in a moment
            self._noticed.add(e.serial)
            world.places.remember(e.kind, x, y, look=look)

    def _recall(self):
        """The places calling her back, and how strongly.  A timid cat
        would rather not go where the fox was."""
        if type(self) is not Cat or not self._cooldown_ok("revisit"):
            return []
        places = self.world.places
        now = self.world.env.clock.moment
        calls = []
        for place in places.all:
            pull = places.pull(place, now)
            if place.kind == "fox":
                pull *= self.p.lean("bold", 0.2, 1.4)
            if pull > 0:
                calls.append((place, pull))
        return calls

    def _perceive(self):
        if not self.interruptible:
            return
        env = self.world.env
        if env.rain > RAIN["shelter_above"] and not self.sheltered and self.activity_name != "shelter":
            if self.world.terrain.spots["shelter"] or self.world.terrain.spots["roof"]:
                self._start("shelter", self.act_shelter())
                return
        if (RAIN["drizzle_above"] < env.rain <= RAIN["shelter_above"] and not self.sheltered
                and self.world.terrain.spots["roof"]
                and self.posture != "sleep" and self._cooldown_ok("drizzle")
                and self.activity_name not in ("eat", "drink", "hunt", "zoomies", "drizzle", "shelter")
                and self.rng.random() < DRIZZLE_CHANCE):
            self._start("drizzle", self.act_drizzle())
            return
        if self._afraid():
            return
        if self.posture == "sleep" or self.activity_name in ("eat", "drink", "nap", "shelter", "groom",
                                                              "hunt", "butterfly", "hiss", "zoomies", "watch"):
            return
        n = self.needs
        if n.energy < 0.25:
            return
        world = self.world
        best = None
        for e in world.entities:
            if e is self or not e.alive or self._ignored.get(e.serial, 0.0) > world.time:
                continue
            interest = getattr(e, "interest", None)
            if interest is None:
                continue
            score = interest(self)
            if score <= 0:
                continue
            if best is None or score > best[0]:
                best = (score, e)
        if best is None:
            return
        score, prey = best
        if (self.p.has("chatterer") and prey.kind in ("pigeon", "sparrow") and getattr(prey, "state", "") == "ground"
                and self._cooldown_ok("chatter") and self.rng.random() < 0.08):
            self._start("chatter", self.act_chatter(prey))     # not play: she simply can't help it
            return
        if n.play < 0.3:
            return
        eagerness = (0.2 + 0.8 * n.play) * self.p.lean("playful", 0.6, 1.4)
        if self.rng.random() < score * eagerness * 0.06:
            p = self.p
            if prey.kind == "crow" and p["bold"] > 0.65 and self.rng.random() < 0.5 and self._cooldown_ok("hunt"):
                self._start("hiss", self.act_hiss(prey))
                return
            if prey.kind == "golden_butterfly":
                self._start("golden", self.act_follow(prey))
            elif prey.kind in ("butterfly", "moth"):
                if self._cooldown_ok("butterfly"):
                    self._start("butterfly", self.act_butterfly(prey))
            elif prey.kind == "pigeon" and getattr(prey, "landed_close", lambda c: False)(self) \
                    and self.posture == "sit" and self.rng.random() < 0.5:
                self._start("hiss", self.act_hiss(prey))
            elif getattr(prey, "watch_only", False):
                if self._cooldown_ok("watch"):
                    self._start("watch", self.act_watch(prey))
            elif self._cooldown_ok("hunt"):
                self._start("hunt", self.act_hunt(prey))

    def attend(self, name, generator, wake=False):
        """Something happened that Mochi responds to (an event): start
        ``generator`` if she is free.  A sleeping cat is only roused when
        ``wake`` is set."""
        busy = not self.interruptible or self.activity_name in ("eat", "drink", "hunt", "zoomies")
        if busy or (self.posture == "sleep" and not wake):
            generator.close()
            return False
        self._start(name, generator)
        return True

    # ======================================================================
    # Activities

    def act_wake(self):
        """The first scene: curled up asleep, then waking and stretching."""
        self.label = "waking up"
        self.posture = "sleep"
        self.idle_pose()
        yield from self.wait(self.rng.uniform(1.5, 3.0))
        yield from self.wake_up()

    def act_sleep_on(self):
        """Already asleep: sleep on until rested, then get up."""
        self.label = "napping"
        self.posture = "sleep"
        self.idle_pose()
        while self.needs.energy < 0.97 or self._sleep_in():
            yield
        yield from self.wake_up()

    def wake_up(self):
        self.label = "waking up"
        yield from self.to_posture("lie")
        yield from self.wait(self.rng.uniform(0.6, 1.4))
        yield from self.once("yawn_lie", fps=6)
        self.idle_pose()
        yield from self.wait(self.rng.uniform(0.6, 1.4))
        yield from self.to_posture("stand")
        if self.rng.random() < 0.75:
            self.label = "stretching"
            yield from self.once("stretch", fps=6)
            self.idle_pose()
            yield from self.wait(self.rng.uniform(0.3, 0.8))

    def act_wander(self):
        self.label = "wandering"
        goal = self._wander_goal()
        if goal is None:
            yield from self.look_around()
            return
        gait = self._wander_pace()
        yield from self.go(*goal, gait=gait, dawdle=gait in ("amble", "walk"))
        yield from self.look_around()

    def look_around(self):
        self.label = "looking around"
        if self.posture != "stand":
            yield from self.to_posture("stand")
        yield from self.wait(self.rng.uniform(0.5, 1.4))
        roll = self.rng.random()
        if roll < 0.3 and self.side_view:
            self.show("stand_look", fps=4)
            yield from self.wait(self.rng.uniform(1.0, 2.2))
            self.idle_pose()
        elif roll < 0.55 and self.side_view:
            self.label = "sniffing the grass"
            yield from self.once("sniff_start", fps=8)
            self.show("sniff", fps=5)
            yield from self.wait(self.rng.uniform(1.0, 2.5))
            self.idle_pose()
        elif roll < 0.8:
            yield from self.pivot(wrap(self.heading + self.rng.choice((-1, 1)) * self.rng.uniform(0.5, 1.3)))
            yield from self.wait(self.rng.uniform(0.5, 1.5))

    def _wander_pace(self):
        """How she sets off on a wander: an amble more often when she's
        tired or lazy, now and then brisk, or a trot."""
        tired = clamp(0.55 - self.needs.energy, -0.3, 0.4)
        amble = clamp(WALKING["amble_share"] + tired + 0.25 * (self.p["lazy"] - 0.5), 0.05, 0.85)
        r = self.gait_rng.random()
        if r < amble:
            return "amble"
        r -= amble
        if r < WALKING["brisk_share"]:
            return "brisk"
        r -= WALKING["brisk_share"]
        return "trot" if r < WALKING["trot_share"] else "walk"

    def _wander_goal(self):
        t = self.world.terrain
        rng = self.rng
        candidates = []
        if rng.random() < 0.35:
            for kind in ("shelter", "watch", "nap"):
                for spot in t.spots[kind]:
                    candidates.append(spot.approach)
            if t.perches:
                for _ in range(4):
                    px, py, _ = rng.choice(t.perches)
                    candidates.append((px + rng.choice((-18, 18)), py))
            rng.shuffle(candidates)
        for _ in range(14):
            angle = rng.uniform(0, TAU)
            dist = rng.uniform(45, 170)
            candidates.append((self.x + math.cos(angle) * dist, self.y + math.sin(angle) * dist * 0.75))
        here = (self.x, self.y)
        for x, y in candidates:
            gx, gy = int(round(x)), int(round(y))
            if math.hypot(gx - self.x, gy - self.y) < 12 or not t.walkable(gx, gy):
                continue
            if t.regions.connected(here, (gx, gy)) or not t.walkable(self.x, self.y):
                return gx, gy
        return None

    def act_sit(self):
        self.label = "sitting"
        self.speed = 0.0
        yield from self.to_posture("sit")
        duration = self._enough("sit_seconds")
        elapsed = 0.0
        next_glance = self.rng.uniform(3.0, 7.0)
        looking = False
        while elapsed < duration:
            elapsed += self.dt
            next_glance -= self.dt
            if next_glance <= 0:
                next_glance = self.rng.uniform(3.0, 7.0)
                if self.side_view and not looking and self.rng.random() < 0.6:
                    self.show("sit_look", fps=3.5)
                    looking = True
                elif looking:
                    self.idle_pose()
                    looking = False
                elif self.rng.random() < 0.2:
                    yield from self.once("yawn_sit", fps=6)
                    self.idle_pose()
            yield
        if looking:
            self.idle_pose()

    def act_loaf(self):
        self._cool("loaf", COOL["loaf"])
        want = self._wants_light()
        if want and not self._right_light(want) and self.rng.random() < SHADE["seek_chance"]:
            spot = self._light_spot(want)
            if spot is not None:
                self.label = "looking for some shade" if want == "shade" else "finding a patch of sun"
                yield from self.go_to_spot(spot, loose=True)
        self._rest_label()
        self.speed = 0.0
        yield from self.to_posture("lie")
        self._settle_light()
        duration = self._enough("loaf_seconds")
        elapsed = 0.0
        while elapsed < duration:
            elapsed += self.dt
            if self._restless():
                yield from self._move_for_light(asleep=False)
                self._rest_label()
            r = self.rng.random()
            if r < self.dt * 0.05:
                self.show("lie_look", fps=3)
                yield from self.wait(self.rng.uniform(2.0, 5.0))
                self.idle_pose()
            elif r < self.dt * 0.08:
                yield from self.once(self.rng.choice(("groom_lie", "yawn_lie", "meow_lie")), fps=6)
                self.idle_pose()
            if self.needs.energy < 0.3:
                yield from self.doze(until=lambda: self.needs.energy >= 0.9)
                return
            yield

    def act_groom(self):
        self.label = "grooming"
        self.speed = 0.0
        if self.view in ("back", "br", "bl"):
            yield from self.face("down")
        yield from self.to_posture("sit")
        yield from self.wait(self.rng.uniform(0.4, 0.9))
        for _ in range(self.rng.randint(1, 3)):
            yield from self.once("groom", fps=7)
        self.idle_pose()
        yield from self.wait(self.rng.uniform(1.0, 2.5))
        self.needs.groom = 0.0
        self._cool("groom", COOL["groom"])

    def act_nap(self, spot=None):
        self.label = "looking for a cozy spot"
        if spot is None:
            spot = self._nap_spot()
        if spot is not None:
            arrived = yield from self.go_to_spot(spot, gait="amble", loose=True)
            if arrived and type(self) is Cat:
                world = self.world
                if self.p.napped(world.terrain.seed, spot.x, spot.y):
                    world.say(f"{self.name} has a favourite nap spot now", "uncommon")
        if self.gait_rng.random() < MOCHI["circle_before_nap"]:
            yield from self.turn_round()
        if self.p.has("kneader") or (self.p.mood > 0.5 and self.rng.random() < 0.3):
            yield from self.knead()
        # A catnap or a proper sleep; she wakes once it's over and she's
        # rested enough (and sleeps on at night).
        length = sample(self.rng, MOCHI["nap_minutes"], self.world.day.spread) * 60.0
        start = self.world.time
        yield from self.doze(until=lambda: self.world.time - start >= length and self.needs.energy >= 0.55
                             and not self._sleep_in())

    def turn_round(self):
        """Before settling for a proper sleep, a cat often turns round once
        or twice on the spot, slowly, treading as she goes: an old
        nest-making habit."""
        if self.posture != "stand":
            yield from self.to_posture("stand")
        label = self.label
        self.label = "turning round to settle"
        rounds = 1 if self.gait_rng.random() < 0.7 else 2
        way = self.gait_rng.choice((-1, 1))
        left = rounds * TAU
        while left > 0.02:
            before = self.heading
            self._turn_in_steps(way * left, "amble")
            left -= abs(wrap(self.heading - before))
            yield
        self.idle_pose()
        if not self.side_view:
            yield from self.face("right" if math.cos(self.heading) >= 0 else "left")
        self.label = label

    def _sleep_style(self):
        env = self.world.env
        if env.is_night or env.rain > 0.1 or env.weather.cloud > 0.7:
            return "curl"                     # keep warm
        if self._wants_light() == "shade":
            return "flat"                     # too hot to curl up
        if env.sun > 0.75 and env.weather.cloud < 0.4:
            if self.p.has("sunbather"):
                return "flat"
            return self.rng.choice(("flat", "flat", "loaf"))   # sprawl in the warm
        if self.p.has("loafer"):
            return "loaf"
        return self.rng.choice(("curl", "loaf"))

    def doze(self, until):
        """Lie down, fall asleep until ``until()``, then wake slowly."""
        self.label = "settling down"
        yield from self.to_posture("lie")
        yield from self.wait(self.rng.uniform(2.0, 4.0))
        if self.rng.random() < 0.4:
            yield from self.once("groom_lie", fps=6)
            self.idle_pose()
            yield from self.wait(1.0)
        self.label = "napping"
        yield from self.to_posture("sleep", style=self._sleep_style())
        self._settle_light()
        shift = self.rng.uniform(60, 140)
        slept = 0.0
        dream = sample(self.rng, MOCHI["dream_wait"])
        while not until() or slept < 20.0:
            slept += self.dt
            shift -= self.dt
            dream -= self.dt
            if self._restless():
                yield from self._move_for_light(asleep=True)
            if dream <= 0 and slept > MOCHI["dream_after"] and self.posture == "sleep":
                # deep sleep: her paws paddle and an ear twitches
                self.label = "dreaming"
                yield from self.once(f"dream_{self.sleep_style}", fps=7)
                self.idle_pose()
                self.label = "napping"
                dream = sample(self.rng, MOCHI["dream_wait"])
            if shift <= 0:
                # Shift position now and then, as sleeping cats do.
                shift = self.rng.uniform(70, 160)
                yield from self.to_posture("sleep", style=self._sleep_style())
            yield
        yield from self.wake_up()
        self.needs.groom += 0.3

    def _sleep_in(self):
        """At night the cat keeps sleeping past full energy, most of the time."""
        env = self.world.env
        if not env.is_night:
            return False
        if not hasattr(self, "_sleep_in_until"):
            self._sleep_in_until = 0.0
        if self.world.time > self._sleep_in_until + 600:
            self._sleep_in_until = self.world.time + self.rng.uniform(60, 300)
        return self.world.time < self._sleep_in_until

    def _nap_spot(self):
        t = self.world.terrain
        env = self.world.env
        want = self._wants_light()
        if want and self.rng.random() < SHADE["seek_chance"]:
            spot = self._light_spot(want)
            if spot is not None:
                return spot
        pool = list(t.spots["shelter"]) if (env.is_night or env.rain > 0.1) else list(t.spots["nap"])
        if not pool:
            pool = list(t.spots["nap"])
        if not pool:
            return None
        fav = self.p.favourite(t.seed)
        if fav and not (env.is_night or env.rain > 0.1) and self.rng.random() < 0.6:
            fx, fy = (float(v) for v in fav.split(":", 1)[1].split(","))
            return min(pool, key=lambda s: (s.x - fx) ** 2 + (s.y - fy) ** 2)
        pool.sort(key=lambda s: (s.x - self.x) ** 2 + (s.y - self.y) ** 2)
        return self.rng.choice(pool[:3])

    # --- sun and shade ----------------------------------------------------

    def _wants_light(self):
        """On a hot sunny day she rests in the shade; on a cold one, in the sun."""
        env = self.world.env
        if env.rain > 0.1 or self.world.shade.strength < 0.35 or env.is_night:
            return None
        if env.temperature > SHADE["hot_above"]:
            return "shade"
        if env.temperature < SHADE["cold_below"]:
            return "sun"
        return None

    def _right_light(self, want, x=None, y=None):
        """Is (x, y) (where she is) the kind of place she wants?  Only the
        tree's shade counts: a passing cloud isn't worth moving for."""
        x = self.x if x is None else x
        y = self.y if y is None else y
        shade = self.world.shade
        if want == "shade":
            return shade.covers(x, y)
        return not shade.covers(x, y, margin=-0.15) and not self.world.terrain.under_roof(x, y)

    def _light_spot(self, want):
        """The nearest good place to lie down in the shade, or in the sun."""
        t = self.world.terrain
        shade = self.world.shade
        rng = self.rng
        here = (self.x, self.y)
        best = None
        for _ in range(60):
            if want == "shade":
                if shade.ellipse is None:
                    return None
                cx, cy, ux, uy, major, minor = shade.ellipse
                a, r = rng.uniform(0, TAU), math.sqrt(rng.random()) * 0.7
                along, across = r * math.cos(a) * major, r * math.sin(a) * minor
                x = cx + along * ux + across * uy
                y = cy - (-along * uy + across * ux) * SQUASH
                ok = self._right_light(want, x - 10, y) and self._right_light(want, x + 10, y)
            else:
                a, r = rng.uniform(0, TAU), rng.uniform(20, 120)
                x, y = self.x + math.cos(a) * r, self.y + math.sin(a) * r * 0.7
                ok = self._right_light(want, x - 14, y) and self._right_light(want, x + 14, y)
            gx, gy = int(round(x)), int(round(y))
            if not (ok and t.walkable(gx, gy) and t.walkable(gx - 16, gy) and t.walkable(gx + 16, gy)):
                continue
            if not t.regions.connected(here, (gx, gy)):
                continue
            d = math.hypot(gx - self.x, gy - self.y)
            if best is None or d < best[0]:
                best = (d, gx, gy)
        if best is None:
            return None
        _, gx, gy = best
        facing = "left" if gx > self.x else "right"
        return Spot(gx, gy, rng.choice((facing, facing, "left", "right")), (gx, gy))

    def _rest_label(self):
        want = self._wants_light()
        if want == "shade" and self._right_light("shade"):
            self.label = "lying in the shade"
        elif self.world.shade.sunlit(self.x, self.y) > 0.4:
            self.label = "sunbathing"
        else:
            self.label = "loafing"

    def _settle_light(self):
        self._wrong_light = 0.0
        self._light_patience = sample(self.rng, SHADE["restless_after"])

    def _restless(self):
        """The shade has moved off her (or onto her) and stayed that way."""
        if not hasattr(self, "_wrong_light"):
            self._settle_light()
        want = self._wants_light()
        if want is None or self._right_light(want):
            self._wrong_light = max(0.0, self._wrong_light - 2.0 * self.dt)
            return False
        self._wrong_light += self.dt
        return self._wrong_light > self._light_patience

    def _move_for_light(self, asleep):
        """Get up, move a little way into the shade (or the sun), lie down again."""
        want = self._wants_light()
        spot = self._light_spot(want)
        self._settle_light()
        if spot is None:
            self._light_patience *= 3.0          # nowhere better: put up with it a while
            return
        if asleep:
            yield from self.wake_up()
        else:
            yield from self.to_posture("stand")
        self.label = "following the shade" if want == "shade" else "moving into the sun"
        yield from self.go_to_spot(spot, loose=True)
        yield from self.to_posture("lie")
        yield from self.wait(self.rng.uniform(1.0, 2.5))
        if asleep:
            self.label = "napping"
            yield from self.to_posture("sleep", style=self._sleep_style())
        self._settle_light()

    def act_eat(self):
        spots = self.world.terrain.spots["bowl"]
        if not spots:
            return
        spot = min(spots, key=lambda s: abs(s.x - self.x) + abs(s.y - self.y))
        self.label = "heading to the food bowl"
        ok = yield from self.go_to_spot(spot, gait="brisk" if self.needs.hunger > 0.75 else "walk")
        if not ok:
            return
        world = self.world
        if world.bowl_fill <= 0.02:
            self.label = "asking for food"
            yield from self.face("down")
            yield from self.to_posture("sit")
            for _ in range(self.rng.randint(2, 3)):
                yield from self.once("meow_sit", fps=5)
                self.idle_pose()
                yield from self.wait(self.rng.uniform(1.0, 2.2))
            self.needs.hunger = min(self.needs.hunger, 0.5)
            return
        self.label = "eating"
        self.state = "eating"
        self.p.feel(0.1)
        yield from self.once("eat_start", fps=8)
        self.show("eat", fps=self.rng.uniform(5.0, 6.5))
        duration = sample(self.rng, MOCHI["eat_seconds"])
        elapsed = 0.0
        while elapsed < duration and world.bowl_fill > 0:
            elapsed += self.dt
            world.bowl_fill = max(0.0, world.bowl_fill - self.dt * 0.013)
            self.needs.hunger = max(0.0, self.needs.hunger - self.dt * 0.1)
            yield
        self.needs.hunger = min(self.needs.hunger, 0.1)
        self.needs.groom += 0.4
        yield from self.once("eat_end", fps=7)
        self.idle_pose()
        yield from self.wait(self.rng.uniform(0.5, 1.2))
        if self._after_dinner_dash():
            self.label = "evening zoomies!"
            yield from self.wait(self.rng.uniform(1.0, 4.0))
            yield from self.act_zoomies()
        elif self.rng.random() < 0.6:
            yield from self.act_groom()

    def _after_dinner_dash(self):
        """Fed at dusk, many cats go mad for a minute: a playful one more
        often, a tired or grumpy one less."""
        clock = self.world.env.clock
        if not clock.between(*MOCHI["evening_zoomies_hours"]) or self.needs.energy < 0.45:
            return False
        if not self._cooldown_ok("zoomies") or self.p.mood < -0.25:
            return False
        return self.rng.random() < MOCHI["evening_zoomies_chance"] * self.p.lean("playful", 0.4, 1.6)

    def act_drink(self):
        spots = self.world.terrain.spots["drink"]
        if not spots:
            return
        spots = sorted(spots, key=lambda s: abs(s.x - self.x) + abs(s.y - self.y))
        spot = self.rng.choice(spots[:4])
        self.label = "going for a drink"
        ok = yield from self.go_to_spot(spot)
        if not ok:
            return
        if self.world.env.frozen:
            yield from self.test_the_ice()
            return
        self.label = "drinking from the pond"
        self.state = "eating"
        yield from self.once("drink_start", fps=8)
        self.show("drink", fps=7)
        sign = 1 if spot.facing == "right" else -1
        mouth_x = spot.x + sign * (cat_anims.MOUTH_REACH + 1)
        duration = self.rng.uniform(4.0, 7.0)
        elapsed = 0.0
        lap = 0.0
        while elapsed < duration:
            elapsed += self.dt
            lap -= self.dt
            if lap <= 0:
                lap = self.rng.uniform(0.5, 0.9)
                self.world.water.ripple(mouth_x, spot.y - 1, small=True)
            self.needs.thirst = max(0.0, self.needs.thirst - self.dt * 0.2)
            yield
        self.needs.thirst = 0.0
        yield from self.once("drink_end", fps=8)
        self.idle_pose()
        yield from self.wait(self.rng.uniform(0.6, 1.2))

    def test_the_ice(self):
        """The pond is hard: a careful paw to see, another tap, a sniff, and
        then a lick at the ice, which is something."""
        self.label = "testing the ice"
        yield from self.to_posture("stand")
        if self.side_view:
            yield from self.once("crouch", fps=6)
            for _ in range(2):
                yield from self.once("swipe_stand", fps=10)
                self.idle_pose()
                yield from self.wait(self.rng.uniform(0.6, 1.4))
            yield from self.once("sniff_start", fps=8)
            self.show("sniff", fps=5)
            yield from self.wait(self.rng.uniform(1.0, 2.0))
        self.label = "licking the ice"
        yield from self.once("drink_start", fps=8)
        self.show("drink", fps=5)
        yield from self.wait(self.rng.uniform(3.0, 5.0))
        self.needs.thirst = max(0.0, self.needs.thirst - 0.4)    # ice is slow going
        yield from self.once("drink_end", fps=8)
        self.idle_pose()

    def act_watch_pond(self):
        spots = self.world.terrain.spots["watch"]
        if not spots:
            return
        self._cool("watch_pond", COOL["watch_pond"])
        self.label = "heading to the pond"
        ok = yield from self.go_to_spot(spots[0])
        if not ok:
            return
        pond = getattr(self.world, "stories", None)
        pond = pond.pond if pond is not None else None
        self.label = "watching the tadpoles" if pond is not None and pond.tadpoles else "watching the pond"
        yield from self.to_posture("sit")
        yield from self.wait(self._enough("pond_watch_seconds"))

    def act_explore(self):
        t = self.world.terrain
        self._cool("explore", self.rng.uniform(60, 120))
        spots = list(t.spots["shelter"])
        if not spots:
            return
        spot = self.rng.choice(spots)
        self.label = "exploring"
        status = yield from self.go(*spot.approach, gait="amble", dawdle=True)
        if status != ARRIVED:
            return
        bush = spot.owner
        side = "right" if bush.x > self.x else "left"
        yield from self.face(side)
        self.label = "sniffing the bush"
        yield from self.once("sniff_start", fps=8)
        self.show("sniff", fps=5)
        yield from self.wait(self.rng.uniform(1.0, 2.5))
        self.idle_pose()
        if self.rng.random() < 0.45:
            yield from self.once("swipe_stand", fps=12)
            self.world.flush_bush(bush, self)
            self.idle_pose()
            yield from self.wait(self.rng.uniform(0.8, 1.6))

    def act_revisit(self, place=None):
        """Go back to where something happened (sometimes days ago) and see
        whether it's still there."""
        world = self.world
        places = world.places
        if place is None:
            calls = self._recall()
            if not calls:
                return
            r = self.rng.uniform(0, sum(pull for _, pull in calls))
            for place, pull in calls:
                r -= pull
                if r <= 0:
                    break
        self._cool("revisit", COOL["revisit"])
        now = world.env.clock.moment
        old = (now - place.when).total_seconds() >= PLACE["caption_after_hours"] * 3600
        when = ago(place.when, now) if old else None
        self.label = f"going back to {place.phrase}"
        status = yield from self.go(place.x, place.y, gait="walk", max_time=40.0, dawdle=True)
        if status == UNREACHABLE:
            places.forget(place)
            return
        if status != ARRIVED:
            return
        lx, ly = place.look
        yield from self.face("right" if lx >= self.x else "left")
        self.label = f"checking {place.phrase}"
        if when and self._cooldown_ok("revisit_caption"):
            self._cool("revisit_caption", COOL["revisit_caption"])
            world.say(f"{self.name} went back to {place.phrase} {when}", "uncommon")
        yield from self.once("sniff_start", fps=8)
        self.show("sniff", fps=5)
        yield from self.wait(self.rng.uniform(1.5, 3.0))
        self.idle_pose()
        if place.kind == "mouse":
            # Sit and watch the bush; then, perhaps, a paw in to see.
            yield from self.to_posture("sit")
            yield from self.wait(self._enough("watch_seconds"))
            bush = min(world.terrain.bushes, key=lambda b: math.hypot(b.x - lx, b.y - ly), default=None)
            if bush is not None and self.rng.random() < 0.5:
                yield from self.to_posture("stand")
                yield from self.once("swipe_stand", fps=12)
                world.flush_bush(bush, self)
                self.idle_pose()
            found = any(getattr(m, "home", None) is bush for m in world.of_kind("mouse"))
        else:
            yield from self.look_around()
            found = any(e.kind == place.kind and e.alive and math.hypot(e.x - place.x, e.y - place.y) < 60
                        for e in world.entities)
        places.visited(place, found)

    def act_gaze(self, x, y, seconds, label):
        """Stop and look at something for a while."""
        self.label = label
        self.speed = 0.0
        yield from self.face((x, y))
        if self.posture == "stand":
            yield from self.to_posture("sit")
        yield from self.wait(seconds)

    def act_look_up(self, flock, label):
        """Something high overhead (storks circling, a skein of geese): she
        sits and follows it, head tipped back, until it has gone over."""
        self._cool("look_up", 45)
        self.label = label
        self.speed = 0.0
        if not self.side_view:
            side = "right" if math.cos(self.heading) >= 0 else "left"
            yield from self.pivot(HEADING[side])
        if self.posture != "sit":
            yield from self.to_posture("sit")
        self.show("sit_skyward", fps=3)
        end = self.world.time + self.rng.uniform(6, 16)
        while self.world.time < end and flock.alive and flock.over_meadow:
            yield
        self.idle_pose()
        yield from self.wait(self.rng.uniform(0.5, 1.5))

    def act_watch_nest(self):
        """Up at the blackbirds' nest: she sits at the edge of the tree's
        shade and watches the comings and goings, head tipped back (and
        gets told off for it)."""
        nest = self.world.stories.nest
        self._cool("watch_nest", self.rng.uniform(240, 600))
        fx, fy = nest.foot
        t = self.world.terrain
        goal = None
        for _ in range(12):
            a = self.rng.uniform(0.15 * math.pi, 0.85 * math.pi)
            r = self.rng.uniform(34, 50)
            gx, gy = fx + math.cos(a) * r, fy + 4 + math.sin(a) * r * 0.5
            if t.walkable(gx, gy):
                goal = (gx, gy)
                break
        if goal is None:
            return
        self.label = "heading for the tree"
        status = yield from self.go(*goal, gait="amble", max_time=15.0)
        if status == UNREACHABLE:
            return
        self.label = "watching the blackbirds' nest"
        side = "right" if fx > self.x else "left"
        if self.view != side:
            yield from self.pivot(HEADING[side])
        yield from self.to_posture("sit")
        self.show("sit_skyward", fps=3)
        yield from self.wait(self._enough("watch_seconds") + 4.0)
        self.idle_pose()

    def act_sniff_at(self, x, y, label):
        """Walk over to something on the ground and sniff it."""
        self.label = label
        side = -1 if self.x < x else 1
        gx, gy = x + side * 14, y
        if not self.world.terrain.walkable(gx, gy):
            gx = x - side * 14
        status = yield from self.go(gx, gy, gait="walk", max_time=12.0)
        if status == UNREACHABLE:
            return
        yield from self.face("right" if x > self.x else "left")
        yield from self.once("sniff_start", fps=8)
        self.show("sniff", fps=5)
        yield from self.wait(self.rng.uniform(1.5, 3.0))
        self.idle_pose()
        if self.rng.random() < 0.5:
            yield from self.once("swipe_stand", fps=12)
            self.idle_pose()
        yield from self.wait(0.6)

    def act_shadow(self, flock):
        """A bird's shadow sweeps over the grass: crouch, wait for it, pounce
        on it, and then look up, baffled."""
        self.label = "eyeing a bird's shadow"
        yield from self.settle()
        if self.posture != "stand":
            yield from self.to_posture("stand")
        waited = 0.0
        target = None
        while flock.alive and waited < 10.0:
            near = min(flock.birds, key=lambda b: math.hypot(b[0] + 4 - self.x, b[1] + 2 - self.y))
            bx, by = near[0] + 4, near[1] + 2
            d = math.hypot(bx - self.x, by - self.y)
            closing = (bx - self.x) * flock.vx + (by - self.y) * flock.vy < 0
            if d < 70 and closing:
                lead = 0.25
                target = Mark("shadow", bx + flock.vx * lead, by + flock.vy * lead)
                break
            waited += self.dt
            yield
        if target is None:
            return
        yield from self.pounce(target)      # ...and then "watching where the shadow went"

    def act_chase(self, thing, tries=2):
        """Run after something skittering across the grass and pounce on it."""
        pounces = 0
        give_up = self.world.time + 20.0
        while thing.alive and pounces < tries and self.world.time < give_up:
            self.label = f"chasing a {thing.kind}"
            d = self.distance_to(thing)
            if d > 30:
                side = -1 if self.x < thing.x else 1
                status = yield from self.go(thing.x - side * 14, thing.y, gait="trot", max_time=0.5, stop=False)
                if status == UNREACHABLE:
                    return
                continue
            yield from self.settle(stand=False)
            yield from self.pounce(thing)
            pounces += 1

    def act_drink_puddle(self, puddle):
        """Rainwater: far better than the bowl, as every cat knows."""
        self.label = "heading for a puddle"
        side = -1 if self.x < puddle.x else 1
        gx = puddle.x + side * (puddle.rx + 9)
        if not self.world.terrain.walkable(gx, puddle.y):
            gx = puddle.x - side * (puddle.rx + 9)
        status = yield from self.go(gx, puddle.y, gait="walk", max_time=15.0)
        if status != ARRIVED or not puddle.alive:
            return
        yield from self.face("right" if puddle.x > self.x else "left")
        self.label = "drinking from a puddle"
        yield from self.once("drink_start", fps=8)
        self.show("drink", fps=6)
        end = self.world.time + self.rng.uniform(4.0, 8.0)
        while self.world.time < end and puddle.alive:
            self.needs.thirst = max(0.0, self.needs.thirst - self.dt / 15.0)
            yield
        yield from self.once("drink_end", fps=8)
        self.idle_pose()

    def knead(self, seconds=None):
        """Tread the ground with the fore paws, eyes half shut."""
        if self.posture != "stand":
            yield from self.to_posture("stand")
        if not self.side_view:
            yield from self.pivot(HEADING["right" if math.cos(self.heading) >= 0 else "left"])
        self.label = "kneading"
        yield from self.once("knead_start", fps=8)
        self.show("knead", fps=7)
        yield from self.wait(seconds or self.rng.uniform(2.5, 5.0))
        self.idle_pose()

    def act_wait_dinner(self):
        """Bowl watchers know when dinner is due."""
        self._cool("wait_dinner", COOL["wait_dinner"])
        spots = self.world.terrain.spots["bowl"]
        spot = min(spots, key=lambda s: abs(s.x - self.x) + abs(s.y - self.y))
        self.label = "heading to the bowl early"
        ok = yield from self.go_to_spot(spot)
        if not ok:
            return
        yield from self.face("down")
        yield from self.to_posture("sit")
        self.label = "waiting for dinner"
        world = self.world
        start_fill = world.bowl_fill
        end = world.time + 25 * 60
        while world.time < end and world.bowl_fill <= start_fill + 0.01:
            if self.rng.random() < self.dt * 0.03:
                yield from self.once("meow_sit", fps=5)
                self.idle_pose()
            yield
        if world.bowl_fill > start_fill:
            self.p.feel(0.15)
            yield from self.act_eat()

    def act_chatter(self, bird):
        """That strange rapid jaw-chatter cats make at birds they can't reach."""
        self._cool("chatter", COOL["chatter"])
        self.focus = bird
        self.label = f"chattering at the {bird.kind}s"
        yield from self.face((bird.x, bird.y))
        yield from self.to_posture("sit")
        for _ in range(self.rng.randint(2, 4)):
            for _ in range(3):
                yield from self.once("meow_sit", fps=16)
            self.idle_pose()
            yield from self.wait(self.rng.uniform(0.6, 1.4))
            if not bird.alive or getattr(bird, "state", "") != "ground":
                break

    def act_hide_from(self, creature):
        """A timid cat keeps out of sight until the danger has gone."""
        self.label = f"hiding from the {creature.kind}"
        yield from self.act_shelter(until=lambda: not creature.alive or getattr(creature, "hidden", False)
                                    or self.distance_to(creature) > 200)

    def act_gift(self, what):
        """Find something, carry it to the bowl, and leave it there for you."""
        world = self.world
        t = world.terrain
        bowls = t.spots["bowl"]
        finds = t.spots["shelter"] or t.spots["nap"]
        if not bowls or not finds:
            return
        self.label = "looking for something"
        find = self.rng.choice(finds)
        status = yield from self.go(*find.approach, gait="walk", max_time=25.0)
        if status == UNREACHABLE:
            return
        yield from self.once("sniff_start", fps=8)
        self.show("sniff", fps=5)
        yield from self.wait(self.rng.uniform(1.2, 2.2))
        self.idle_pose()
        world.places.remember("gift", *find.approach, look=(find.x, find.y), what=what)
        self.carrying = what
        self.interruptible = False     # nothing distracts a cat with a present
        self.label = f"carrying a {what}"
        bowl = min(bowls, key=lambda s: abs(s.x - self.x) + abs(s.y - self.y))
        ok = yield from self.go_to_spot(bowl)
        self.interruptible = True
        if not ok:
            self.carrying = None
            return
        yield from self.face("down")
        self.carrying = None
        from .wildlife import Gift
        world.entities.append(Gift(world, self.x + (8 if self.x < bowl.x else -8), self.y + 4, what))
        world.say(f"{self.name} left you a {what} by the bowl", "uncommon")
        self.p.feel(0.2)
        yield from self.to_posture("sit")
        yield from self.once("meow_sit", fps=5)
        self.idle_pose()
        self._blink = 0.45
        yield from self.wait(2.0)

    def act_tail_chase(self):
        """Round and round after her own tail, then a dazed sit."""
        self._cool("tail_chase", COOL["tail_chase"])
        self.label = "chasing her tail!"
        if self.posture != "stand":
            yield from self.to_posture("stand")
        turns = self.rng.uniform(2.0, 3.5)
        spin = self.rng.choice((-1, 1)) * 8.5
        turned = 0.0
        while turned < turns * TAU:
            step = abs(spin) * self.dt
            turned += step
            self.heading = wrap(self.heading + math.copysign(step, spin))
            self.view = view_for(self.heading, self.view)
            self.moved = step * 9.0
            self.speed = 0.0
            strides = self._strides()
            self.show("trot", stride=strides["trot"], keep_phase=True)
            if self.rng.random() < self.dt * 4:
                self.world.particles.dust(self.x, self.y, count=1, spread=6.0)
            yield
        self.idle_pose()
        yield from self.to_posture("sit")
        self.label = "a little dizzy"
        yield from self.wait(self.rng.uniform(1.5, 2.5))
        yield from self.act_groom()

    def act_fourth_wall(self):
        """Mochi walks right up to the screen, looks out at whoever is
        watching, and taps the glass."""
        world = self.world
        t = world.terrain
        self.label = "looking at you"
        gx = clamp(world.width / 2 + self.rng.uniform(-40, 40), 40, world.width - 40)
        goal = None
        for gy in range(int(world.height - 14), int(world.height * 0.55), -3):
            for dx in (0, 12, -12, 24, -24):
                if t.walkable(gx + dx, gy) and t.regions.connected((self.x, self.y), (gx + dx, gy)):
                    goal = (gx + dx, gy)
                    break
            if goal:
                break
        if goal is None:
            return
        status = yield from self.go(*goal, gait="walk")
        if status != ARRIVED:
            return
        yield from self.face("down")
        yield from self.to_posture("sit")
        yield from self.wait(1.2)
        yield from self.once("meow_sit", fps=5)
        self.idle_pose()
        yield from self.wait(1.0)
        for _ in range(self.rng.randint(2, 3)):
            yield from self.once("swipe_sit", fps=11)
            world.glass_tap(self.x + self.rng.uniform(-3, 3), self.y - 22)
            self.idle_pose()
            yield from self.wait(self.rng.uniform(0.25, 0.6))
        yield from self.wait(2.0)
        self._blink = 0.45   # a slow blink, a cat's "I like you"
        yield from self.wait(2.5)

    def act_flee_noise(self):
        """Bangs in the night (fireworks): straight under the nearest bush."""
        self.label = "hiding from the bangs"
        yield from self.act_shelter(until=lambda: not self.world.events.noisy)

    def act_meow(self):
        self._cool("meow", COOL["meow"])
        self.label = "meowing"
        yield from self.face("down")
        yield from self.to_posture("sit")
        yield from self.wait(0.6)
        for _ in range(self.rng.randint(1, 2)):
            yield from self.once("meow_sit", fps=5)
            self.idle_pose()
            yield from self.wait(self.rng.uniform(0.8, 1.6))

    def act_zoomies(self):
        self._cool("zoomies", COOL["zoomies"])
        self.label = "doing zoomies!"
        t = self.world.terrain
        for _ in range(self.rng.randint(3, 6)):
            for _ in range(10):
                angle = self.rng.uniform(0, TAU)
                dist = self.rng.uniform(50, 150)
                gx = int(self.x + math.cos(angle) * dist)
                gy = int(self.y + math.sin(angle) * dist * 0.7)
                if t.walkable(gx, gy) and t.regions.connected((self.x, self.y), (gx, gy)):
                    break
            else:
                break
            self.world.particles.dust(self.x, self.y, count=4)
            yield from self.go(gx, gy, gait="run", stop=True, stand=False)
            self.world.particles.dust(self.x, self.y, count=5)
            self.idle_pose()
            yield from self.wait(self.rng.uniform(0.1, 0.5))
        self.speed = 0.0
        self.idle_pose()
        yield from self.wait(0.4)
        self.needs.play = 0.0
        yield from self.act_groom()

    def act_shelter(self, until=None):
        """Into cover until ``until()`` (default: the rain or snow eases off).

        In the weather she makes for the tree, whose crown keeps the rain
        off, or else a bush.  Sheltering isn't sitting still forever: now and
        then (more often for a curious or bold cat, less in a downpour) she
        goes out for a look round in the wet and comes back to groom it off."""
        env = self.world.env
        t = self.world.terrain
        weather = until is None
        if weather:
            until = lambda: env.rain < 0.15
        roof, bushes = t.spots["roof"], t.spots["shelter"]
        near = lambda s: abs(s.x - self.x) + abs(s.y - self.y)
        if weather and roof and (self.rng.random() < RAIN["roof_preference"] or not bushes):
            spot = self.rng.choice(sorted(roof, key=near)[:2])
        elif bushes:
            spot = min(bushes, key=near)
        elif roof:
            spot = min(roof, key=near)
        else:
            return
        if weather:
            self.label = "running for cover"
        if self.posture == "sleep":
            if weather:
                self.label = "woken by the snow" if env.snowing else "woken by the rain"
            yield from self.to_posture("sit")
            yield from self.wait(0.8)
        ok = yield from self.go_to_spot(spot, gait="trot", loose=spot.owner is t.tree)
        if not ok:
            return
        if weather:
            self.p.feel(-0.15)
        self.sheltered = True
        self.interruptible = False
        cover = "the tree" if spot.owner is t.tree else "a bush"
        try:
            if self.wet >= RAIN["wet_shake"]:
                yield from self.shake_off()
            if weather and self.needs.energy < 0.5:
                yield from self.doze(until=until)
                return
            while not until():
                if weather:
                    self.label = f"sheltering under {cover}"
                yield from self.to_posture("lie" if self.rng.random() < 0.6 else "sit")
                while not until():
                    if weather and self.rng.random() < self.dt * self._venture_rate():
                        yield from self.act_rain_walk(spot)
                        break
                    yield
            yield from self.to_posture("stand")
            yield from self.wait(1.0)
        finally:
            self.sheltered = False
        self.needs.groom += 0.5

    def act_drizzle(self):
        """A drizzle doesn't send her running, but now and then she ducks
        under the tree for a little while, then gets on with her day."""
        self._cool("drizzle", COOL["drizzle"])
        env = self.world.env
        roof = self.world.terrain.spots["roof"]
        spot = min(roof, key=lambda s: abs(s.x - self.x) + abs(s.y - self.y))
        self.label = "ducking under the tree"
        ok = yield from self.go_to_spot(spot, loose=True)
        if not ok:
            return
        self.sheltered = True
        try:
            self.label = "waiting out the drizzle"
            yield from self.to_posture("sit")
            end = self.world.time + sample(self.rng, RAIN["drizzle_stay"], self.world.day.spread)
            while self.world.time < end and 0.05 < env.rain <= RAIN["shelter_above"]:
                yield
        finally:
            self.sheltered = False

    def _venture_rate(self):
        """How often (per second) she pops out into the rain."""
        p = self.p
        rain = self.world.env.rain
        return RAIN["venture_rate"] * p.lean("curious", 0.4, 1.6) * p.lean("bold", 0.5, 1.5) * max(0.2, 1.4 - rain)

    def act_rain_walk(self, home):
        """A look round in the wet: a few steps out, a sniff (or a drink from
        a puddle), then back under cover to groom the rain off."""
        world = self.world
        t = world.terrain
        self.label = "heading out into the rain"
        puddles = [p for fx in world.effects for p in getattr(fx, "items", ()) if hasattr(p, "rx")]
        if puddles and self.rng.random() < 0.5:
            yield from self.act_drink_puddle(min(puddles, key=lambda p: self.distance_to(p)))
        else:
            for _ in range(20):
                a = self.rng.uniform(0, TAU)
                d = self.rng.uniform(40, 90)
                gx, gy = self.x + math.cos(a) * d, self.y + math.sin(a) * d * 0.6
                if t.walkable(gx, gy) and not t.under_roof(gx, gy) and t.regions.connected((self.x, self.y), (gx, gy)):
                    break
            else:
                return
            status = yield from self.go(gx, gy, gait="walk", max_time=12.0)
            if status == UNREACHABLE:
                return
            self.label = "out in the rain"
            yield from self.once("sniff_start", fps=8)
            self.show("sniff", fps=5)
            yield from self.wait(self.rng.uniform(2.0, 4.0))
            self.idle_pose()
            yield from self.wait(self.rng.uniform(1.0, 3.0))
        self.label = "hurrying back under cover"
        yield from self.go_to_spot(home, gait="trot", loose=home.owner is t.tree)
        self.label = "grooming the rain off"
        yield from self.shake_off()
        self.p.feel(0.05 if self.p["bold"] > 0.6 else -0.05)

    # --- hunting -------------------------------------------------------------

    def act_hunt(self, prey):
        self._cool("hunt", self.rng.uniform(50, 110))
        self.focus = prey
        self.label = f"spotted a {prey.kind}"
        self.speed = 0.0
        yield from self.face((prey.x, prey.y))
        # Lock on: a low, frozen stare before creeping in.
        self.show("stalk", stride=1e9)
        yield from self.wait(self.rng.uniform(0.4, 1.0))
        self.label = f"stalking a {prey.kind}"
        give_up = self.world.time + 25.0
        t = self.world.terrain
        while True:
            if not prey.alive or getattr(prey, "hidden", False) or prey.airborne:
                yield from self.lost_interest(prey)
                return
            if self.world.time > give_up or self.distance_to(prey) > 170:
                yield from self.lost_interest(prey)
                return
            # Creep in to a spot level with the prey, side-on, pounce range.
            side = -1 if self.x < prey.x else 1
            tx, ty = prey.x + side * 26, prey.y
            if not t.walkable(tx, ty):
                tx = prey.x - side * 26
                if not t.walkable(tx, ty):
                    yield from self.lost_interest(prey)
                    return
            if math.hypot(self.x - tx, self.y - ty) < 4:
                break
            status = yield from self.go(tx, ty, gait="stalk", max_time=0.6, stop=False, stand=False)
            if status == UNREACHABLE:
                yield from self.lost_interest(prey)
                return
            if status == PARTIAL and self.rng.random() < 0.08:
                # Freeze mid-stride, as stalking cats do when prey stirs.
                self.label = "freezing..."
                yield from self.settle(stand=False, gait="stalk")
                yield from self.wait(self.rng.uniform(0.5, 1.5))
                self.label = f"stalking a {prey.kind}"
        yield from self.settle(stand=False, gait="stalk")
        yield from self.pounce(prey)

    def pounce(self, prey):
        self.interruptible = False
        side = "right" if prey.x > self.x else "left"
        if self.facing != side:
            yield from self.pivot(HEADING[side], stand=False)
        self.label = "wiggling..."
        self.show("crouch", fps=9)
        wiggle_time = self.rng.uniform(0.6, 1.3)
        elapsed = 0.0
        while elapsed < wiggle_time:
            elapsed += self.dt
            if prey.alive and getattr(prey, "notices_crouch", None):
                prey.notices_crouch(self)
            if getattr(prey, "state", None) == "flee" or prey.airborne:
                break  # prey bolted: launch now
            yield
        self.label = "pounce!"
        if type(self) is Cat:
            self.world.stats["pounce"] += 1
        hit = getattr(prey, "on_pounce", None)
        if hit is not None:
            hit(self)
        key = f"pounce_{side}"
        self.anim.play(key, self.lib[key], fps=0.0, restart=True)
        self.anim.phase = 1.0
        dx, dy = prey.x - self.x, prey.y - self.y
        d = math.hypot(dx, dy) or 1.0
        ux, uy = dx / d, dy / d
        distance = clamp(d + 4, 16, 36)
        duration = 0.38
        height = 9.0
        elapsed = 0.0
        t = self.world.terrain
        while elapsed < duration:
            elapsed += self.dt
            f = min(1.0, elapsed / duration)
            self.z = 4.0 * height * f * (1.0 - f)
            self.anim.phase = 1.0 if f < 0.3 else 2.0
            step = distance * self.dt / duration
            if t.walkable(self.x + ux * step, self.y + uy * step):
                self.x += ux * step
                self.y += uy * step
            yield
        self.z = 0.0
        self.anim.phase = 3.0
        self.world.particles.dust(self.x + ux * 8, self.y, count=6, spread=6)
        yield from self.wait(0.16)
        self.anim.phase = 4.0
        yield from self.wait(0.22)
        self.posture = "stand"
        self.interruptible = True
        self.needs.play = max(0.0, self.needs.play - 0.5)
        self.p.feel(0.05)
        yield from self.lost_interest(prey)

    def lost_interest(self, prey):
        now = self.world.time
        self._ignored = {k: until for k, until in self._ignored.items() if until > now}
        until = now + self.rng.uniform(90, 200)
        if hasattr(prey, "serial"):          # (a shadow or a leaf is gone anyway)
            self._ignored[prey.serial] = until
        self.label = f"watching where the {prey.kind} went"
        self.speed = 0.0
        if prey.alive:
            yield from self.face((prey.x, prey.y))
        yield from self.to_posture("sit")
        yield from self.wait(self.rng.uniform(2.0, 5.0))
        if self.rng.random() < 0.45:
            yield from self.act_groom()

    def act_butterfly(self, bf):
        self._cool("butterfly", self.rng.uniform(60, 140))
        self.focus = bf
        self.label = f"watching a {bf.kind}"
        if self.distance_to(bf) > 55:
            side = -1 if self.x < bf.x else 1
            yield from self.go(bf.x + side * 32, bf.y, gait="walk", max_time=4.0)
        self.speed = 0.0
        side = "right" if bf.x > self.x else "left"
        yield from self.face(side)
        yield from self.to_posture("sit")
        end = self.world.time + self.rng.uniform(8.0, 20.0)
        while self.world.time < end and bf.alive and not getattr(bf, "leaving", False):
            dx, dy = bf.x - self.x, bf.y - self.y
            if (dx > 0) != (self.facing == "right") and abs(dx) > 14:
                yield from self.to_posture("stand")
                yield from self.face("right" if dx > 0 else "left")
                yield from self.to_posture("sit")
            if abs(dx) < 24 and abs(dy) < 12 and bf.z < 24 and self._cooldown_ok("swat"):
                self._cool("swat", 2.5)
                self.label = f"batting at a {bf.kind}"
                if bf.z > 12 and self.rng.random() < 0.6:
                    yield from self.once("rear", fps=8)
                else:
                    yield from self.once("swipe_sit", fps=13)
                startle = getattr(bf, "startle", None)
                if startle:
                    startle(self)
                self.idle_pose()
                self.label = f"watching a {bf.kind}"
            if bf.z <= 0.5 and self.distance_to(bf) < 70 and self.rng.random() < self.dt * 0.4:
                yield from self.act_hunt(bf)
                return
            yield
        self.needs.play = max(0.0, self.needs.play - 0.3)

    def act_follow(self, bf):
        """Follow the golden butterfly all over the meadow: trot after it,
        sit and gaze when it settles, bat at it when it dips low."""
        self.focus = bf
        t = self.world.terrain
        while bf.alive and not bf.leaving:
            self.label = "following the golden butterfly"
            d = self.distance_to(bf)
            if d > 30:
                side = -1 if self.x < bf.x else 1
                gx, gy = bf.x + side * 18, bf.y
                if not t.walkable(gx, gy):
                    gx, gy = bf.x - side * 18, bf.y
                gait = "trot" if d > 70 else "walk"
                status = yield from self.go(gx, gy, gait=gait, max_time=1.5, stop=False)
                if status == UNREACHABLE:
                    yield from self.wait(0.5)
                continue
            yield from self.settle()
            yield from self.face("right" if bf.x > self.x else "left")
            if bf.z < 14 and self._cooldown_ok("swat") and self.rng.random() < 0.5:
                self._cool("swat", 3.0)
                yield from self.once("rear" if bf.z > 8 else "swipe_stand", fps=9)
                bf.startle(self)
                self.idle_pose()
            elif self.posture == "stand" and bf.state == "perched":
                yield from self.to_posture("sit")
                self.label = "gazing at the golden butterfly"
            yield from self.wait(0.4)
        self.needs.play = 0.0
        self.p.feel(0.5)

    def act_greet(self, other):
        """Another cat has come to visit: touch noses, then follow the
        visitor's mood."""
        self.focus = other
        self.label = f"watching {other.name} come over"
        if self.posture == "sleep":
            yield from self.to_posture("sit")
        yield from self.settle()
        while other.alive and other.phase == "arriving":
            want = view_for(self.heading_to(other.x, other.y))
            if want in ("left", "right") and want != self.view:
                yield from self.face(want)
            yield
        self.label = f"meeting {other.name}"
        yield from self.face("right" if other.x > self.x else "left")
        if self.posture != "stand":
            yield from self.to_posture("stand")
        yield from self.once("sniff_start", fps=8)
        self.show("sniff", fps=5)
        while other.alive and other.phase == "greeting":
            yield
        self.idle_pose()
        if other.phase == "spat":
            self.label = f"hissing at {other.name}"
            yield from self.once("hiss_start", fps=10)
            self.show("hiss", fps=5)
            yield from self.wait(1.6)
            self.idle_pose()
            return
        while other.alive and other.phase == "play":
            self.label = "playing chase"
            if self.distance_to(other) > 34:
                side = -1 if self.x < other.x else 1
                status = yield from self.go(other.x + side * 22, other.y, gait="run", max_time=0.8, stop=False)
                if status == UNREACHABLE:
                    yield from self.wait(0.4)
            else:
                yield from self.settle()
                yield
        self.needs.play = 0.0
        if other.alive and other.phase == "snuggle":
            self.label = f"napping beside {other.name}"
            yield from self.settle()
            yield from self.to_posture("sleep", style="curl")
            while other.alive and other.phase == "snuggle":
                yield
            yield from self.to_posture("sit")
        if other.alive and other.phase == "friendly":
            self.label = f"sitting with {other.name}"
            yield from self.settle()
            yield from self.face("right" if other.x > self.x else "left")
            yield from self.to_posture("sit")
            while other.alive and other.phase == "friendly":
                yield
        self.label = f"watching {other.name} go"
        yield from self.wait(3.0)

    def act_watch(self, creature):
        """Sit and watch something she won't (or can't) chase: a frog on the
        bank, sparrows, a hedgehog shuffling past."""
        self._cool("watch", self.rng.uniform(40, 90))
        self.focus = creature
        self.label = f"watching a {creature.kind}"
        keep = getattr(creature, "watch_distance", 50.0)
        if self.distance_to(creature) > keep + 20:
            dx, dy = self.x - creature.x, self.y - creature.y
            d = math.hypot(dx, dy) or 1.0
            gx, gy = creature.x + dx / d * keep, creature.y + dy / d * keep
            if self.world.terrain.walkable(gx, gy):
                yield from self.go(gx, gy, gait="walk", max_time=6.0)
        yield from self.face((creature.x, creature.y))
        yield from self.to_posture("sit")
        end = self.world.time + self._enough("watch_seconds")
        while self.world.time < end and creature.alive and not getattr(creature, "hidden", False):
            yield
        until = self.world.time + self.rng.uniform(60, 160)
        if hasattr(creature, "serial"):
            self._ignored[creature.serial] = until

    def act_hiss(self, pigeon):
        self._cool("hunt", 10)
        self.label = f"hissing at a {pigeon.kind}"
        side = "right" if pigeon.x > self.x else "left"
        yield from self.face(side)
        yield from self.once("hiss_start", fps=10)
        self.show("hiss", fps=5)
        yield from self.wait(self.rng.uniform(0.9, 1.6))
        scare = getattr(pigeon, "scare", None)
        if scare:
            scare(self)
        self.idle_pose()
        yield from self.wait(0.8)
