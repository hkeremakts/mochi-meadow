"""The meadow's other residents and visitors.

Every creature the cat might notice offers the same small interface:

    interest(cat)        how worth watching it is right now (0 = ignore)
    on_pounce(cat)       the cat leapt at it
    notices_crouch(cat)  called while the cat wiggles before a pounce
    startle(cat)         a near miss (a paw swipe)
"""

import math

import numpy as np
import pygame

from .. import bird_art, cat_anims, critter_art, deer_art, fox_art, pixelrig, pond_art
from ..assets import generated_library
from ..paths import find_path, widen
from ..util import clamp
from .base import Entity

_ART = {}


def art():
    if not _ART:
        sources = [bird_art.__file__, pixelrig.__file__]
        for species in ("pigeon", "sparrow", "crow"):
            _ART[species] = generated_library(species, sources, lambda sp=species: bird_art.render(sp))
        _ART["mouse"] = critter_art.mouse_frames()
        _ART["butterfly"] = {s: critter_art.butterfly_frames(s) for s in critter_art.BUTTERFLY_SPECIES}
        _ART["ladybug"] = critter_art.ladybug_frames()
        _ART["dragonfly"] = critter_art.dragonfly_frames()
        _ART["bird_shadow"] = critter_art.bird_shadow_frames()
        _ART["frog"] = critter_art.frog_frames()
        _ART["hedgehog"] = critter_art.hedgehog_frames()
        _ART["snail"] = critter_art.snail_frames()
        _ART["bee"] = critter_art.bee_frames()
        _ART["butterfly"]["golden"] = critter_art.golden_butterfly_frames()
        _ART["butterfly"]["moth"] = critter_art.moth_frames()
        _ART["grasshopper"] = critter_art.grasshopper_frames()
        _ART["gifts"] = critter_art.gift_frames()
        _ART["bow"] = critter_art.bow_frame()
        _ART["bat"] = critter_art.bat_frames()
        fox = generated_library("fox", [fox_art.__file__, cat_anims.__file__, pixelrig.__file__], fox_art.render)
        for key in list(fox):
            fox[key.replace("_right", "_left")] = [pygame.transform.flip(f, True, False) for f in fox[key]]
        _ART["fox"] = fox
        deer = generated_library("deer", [deer_art.__file__, cat_anims.__file__, pixelrig.__file__], deer_art.render)
        for key in list(deer):
            deer[key.replace("_right", "_left")] = [pygame.transform.flip(f, True, False) for f in deer[key]]
        _ART["deer"] = deer
        for name, build in (("heron", pond_art.render_heron), ("ducks", pond_art.render_ducks)):
            lib = generated_library(name, [pond_art.__file__, pixelrig.__file__], build)
            for key in list(lib):
                lib[key.replace("_right", "_left")] = [pygame.transform.flip(f, True, False) for f in lib[key]]
            _ART[name] = lib
        _ART["pumpkin"] = critter_art.pumpkin_frames()
    return _ART


def _cat_speed(cat):
    return getattr(cat, "speed", 0.0)


# ==========================================================================
# Birds on the ground: pigeons and sparrows

class Bird(Entity):
    """A small bird that flies in, lands, potters about and flies off.

    Flight is steered, not scripted: the bird eases toward its landing spot
    and glides down a shallow slope, flaps when it climbs or speeds up,
    flares with its feet out to land, and leaps into a hard flapping climb
    when startled."""

    kind = "bird"
    SPECIES = "pigeon"
    CRUISE = 70.0        # flight speed
    WALK = 11.0          # ground speed
    WARY = (30.0, 44.0, 62.0)   # flee distance for a still, walking, running cat
    PERSONAL = (16, 8)   # personal space on the ground

    def __init__(self, world, land_x, land_y, delay=0.0):
        rng = world.rng
        side = rng.choice((-1, 1))
        start_x = -24 if side < 0 else world.width + 24
        super().__init__(world, start_x, clamp(land_y + rng.uniform(-50, 50), 20, world.height - 10))
        self.art = art()[self.SPECIES]
        self.rng = rng
        self.target = (land_x, land_y)
        self.cruise_z = rng.uniform(55, 85)
        self.z = self.cruise_z
        self.state = "waiting" if delay > 0 else "arriving"
        self.timer = delay
        self.facing = 1 if land_x > self.x else -1
        self.vx = (land_x - self.x) * 0.0
        self.vy = 0.0
        self.vz = 0.0
        self.wings = "flap"
        self.glide_timer = 0.0
        self.stay = rng.uniform(35, 95)
        self.on_ground_for = 0.0
        self.action = "idle"
        self.action_timer = 0.0
        self.walk_target = None
        self.walk_speed = 0.0
        self.flock = None
        self.exit = None
        self.anim.play("flap", self.art["flap"], fps=14)

    # --- interface for the cat -----------------------------------------
    def interest(self, cat):
        if self.state != "ground":
            return 0.0
        d = self.distance_to(cat)
        return 0.0 if d > 150 else 0.65 * (1.0 - d / 150.0) + 0.2

    def landed_close(self, cat):
        return self.state == "ground" and self.distance_to(cat) < 52

    def scare(self, cat):
        self._take_off(away_from=cat, startled=True)

    def on_pounce(self, cat):
        self._take_off(away_from=cat, startled=True)

    def notices_crouch(self, cat):
        if self.state == "ground" and self.distance_to(cat) < 36 and self.rng.random() < self.world.dt_hint * 0.8:
            self._take_off(away_from=cat, startled=True)

    startle = scare

    @property
    def hidden(self):
        return False

    # --- behaviour --------------------------------------------------------
    def _take_off(self, away_from=None, startled=False):
        if self.state in ("taking_off", "leaving", "waiting"):
            return
        rng = self.rng
        if away_from is not None:
            dx, dy = self.x - away_from.x, self.y - away_from.y
            heading = math.atan2(dy, dx) + rng.uniform(-0.4, 0.4)
        else:
            heading = rng.choice((0.0, math.pi)) + rng.uniform(-0.5, 0.5)
        self.exit = heading
        self.vx = math.cos(heading) * 12.0
        self.vy = math.sin(heading) * 8.0
        self.vz = 38.0 if startled else 26.0
        self.facing = 1 if self.vx > 0 else -1
        self.state = "taking_off"
        self.timer = 0.0
        self.anim.play("takeoff", self.art["takeoff"], fps=22, restart=True)
        if startled:
            self.world.particles.feathers(self.x, self.y, 6, count=self.rng.randint(1, 3))
            if self.flock:
                for mate in self.flock:
                    if mate is not self and mate.state == "ground":
                        mate._take_off(away_from=away_from, startled=False)

    def update(self, dt):
        if self.state == "waiting":
            self.timer -= dt
            if self.timer > 0:
                return
            self.state = "arriving"  # and set off this very tick
        if self.state == "ground":
            self.on_ground_for += dt
            self._ground(dt, self.world.cat)
            return
        self._fly(dt)

    def _steer(self, want_vx, want_vy, accel, dt):
        dvx, dvy = want_vx - self.vx, want_vy - self.vy
        dv = math.hypot(dvx, dvy)
        if dv > accel * dt:
            dvx, dvy = dvx / dv * accel * dt, dvy / dv * accel * dt
        self.vx += dvx
        self.vy += dvy

    def _fly(self, dt):
        world = self.world
        rng = self.rng
        cruise = self.CRUISE
        if self.state == "arriving":
            tx, ty = self.target
            dx, dy = tx - self.x, ty - self.y
            dist = math.hypot(dx, dy)
            # Ease off the speed on the approach, and descend along a glide
            # slope so the bird comes down in a long, gentle line.
            want = cruise * clamp(dist / 60.0, 0.12, 1.0)
            if dist > 0.01:
                self._steer(dx / dist * want, dy / dist * want, 90.0, dt)
            target_z = min(self.cruise_z, dist * 0.5)
            self.vz = clamp((target_z - self.z) * 2.2, -26.0, 20.0)
            if dist < 16 and self.z < 10:
                self.wings = "flare"
            elif self.vz < -5 and math.hypot(self.vx, self.vy) > 22:
                self.wings = "glide" if self.glide_timer > 0 or rng.random() < dt * 1.5 else "flap"
            else:
                self.wings = "flap"
            if dist < 1.2 and self.z < 0.8:
                self.x, self.y, self.z = tx, ty, 0.0
                self.vx = self.vy = self.vz = 0.0
                self.state = "ground"
                self.on_ground_for = 0.0
                self.action = "settle"
                self.action_timer = rng.uniform(0.3, 0.6)
                self.anim.play("flare_end", self.art["flare"][-1:], fps=0.0)
                return
            cat = world.cat
            if cat.distance_to(self) < 40 and self.z < 25:
                self._take_off(away_from=cat)
                return
        elif self.state == "taking_off":
            self.timer += dt
            heading = self.exit
            self._steer(math.cos(heading) * cruise, math.sin(heading) * cruise * 0.6, 120.0, dt)
            self.vz = max(self.vz - 20 * dt, 22.0)
            self.wings = "takeoff" if self.timer < 0.3 else "flap"
            if self.z > 32:
                self.state = "leaving"
        elif self.state == "leaving":
            heading = self.exit
            self._steer(math.cos(heading) * cruise * 1.2, math.sin(heading) * cruise * 0.5, 60.0, dt)
            self.vz = clamp((85.0 - self.z) * 0.8, -5.0, 18.0)
            self.wings = "glide" if (self.glide_timer > 0 or (self.vz < 3 and rng.random() < dt * 0.8)) else "flap"
            if self.x < -40 or self.x > world.width + 40 or self.y < -40 or self.y > world.height + 60:
                self.alive = False
        if self.wings == "glide" and self.glide_timer <= 0:
            self.glide_timer = rng.uniform(0.4, 1.1)
        self.glide_timer = max(0.0, self.glide_timer - dt)
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z = max(0.0, self.z + self.vz * dt)
        if abs(self.vx) > 4:
            self.facing = 1 if self.vx > 0 else -1
        art_ = self.art
        if self.wings == "flare":
            self.anim.play("flare", art_["flare"], fps=10, loop=False)
        elif self.wings == "takeoff":
            self.anim.play("takeoff", art_["takeoff"], fps=22)
        elif self.wings == "glide":
            self.anim.play("glide", art_["glide"], fps=0.0)
        else:
            climbing = self.vz > 4 or self.state == "taking_off"
            self.anim.play("flap", art_["flap"], fps=20 if climbing else 14)
        self.anim.update(dt)

    def _ground(self, dt, cat):
        rng = self.rng
        d = self.distance_to(cat)
        cat_speed = _cat_speed(cat)
        still, walking, running = self.WARY
        wariness = still if cat_speed < 12 else walking if cat_speed < 40 else running
        if d < wariness:
            self._take_off(away_from=cat, startled=d < wariness * 0.85)
            return
        if self.on_ground_for > self.stay:
            self._take_off()
            return
        self.action_timer -= dt
        if self.action_timer <= 0:
            self._next_action()
        moved = 0.0
        if self.action == "walk" and self.walk_target:
            tx, ty = self.walk_target
            dx, dy = tx - self.x, ty - self.y
            dist = math.hypot(dx, dy)
            want = min(self.WALK, dist * 3.0)
            self.walk_speed = approach_value(self.walk_speed, want, self.WALK * 4 * dt)
            if dist < 0.6:
                self.action = "idle"
                self.action_timer = rng.uniform(0.3, 1.0)
            else:
                step = min(dist, self.walk_speed * dt)
                self.x += dx / dist * step
                self.y += dy / dist * step
                moved = step
                if abs(dx) > 0.5:
                    self.facing = 1 if dx > 0 else -1
            self.anim.play("walk", self.art["walk"], stride=bird_art.STRIDE[self.SPECIES])
        elif self.action in ("peck", "preen", "coo", "settle"):
            if self.action != "settle":
                self.anim.play(self.action, self.art[self.action], fps=self.ACTION_FPS[self.action], loop=False)
            if self.anim.done or self.action == "settle":
                if self.action_timer <= 0:
                    self._next_action()
        else:
            self.walk_speed = 0.0
            if self.anim.key != "idle":
                self.anim.play("idle", self.art["idle"], fps=0.0)
            if rng.random() < dt * 1.2:
                self.anim.phase = float(rng.randrange(len(self.art["idle"])))
        self.anim.update(dt, moved)

    ACTION_FPS = {"peck": 9.0, "preen": 4.0, "coo": 6.0}

    def _next_action(self):
        rng = self.rng
        roll = rng.random()
        self.walk_speed = 0.0
        if roll < 0.4:
            self.action = "peck"
            self.action_timer = rng.uniform(0.6, 1.2)
            self.anim.play("peck", self.art["peck"], fps=self.ACTION_FPS["peck"], loop=False, restart=True)
        elif roll < 0.8:
            self.action = "walk"
            self.action_timer = rng.uniform(1.2, 3.0)
            others = [p for p in self.world.of_kind(self.kind) if p is not self and p.state == "ground"]
            px, py = self.PERSONAL
            for _ in range(6):
                tx = self.x + rng.uniform(-30, 30)
                ty = self.y + rng.uniform(-14, 14)
                crowded = any(abs(tx - o.x) < px and abs(ty - o.y) < py for o in others)
                if not crowded and self.world.terrain.free_ground(tx, ty) and 10 < tx < self.world.width - 10 \
                        and 24 < ty < self.world.height - 4:
                    self.walk_target = (tx, ty)
                    break
            else:
                self.action = "idle"
        elif roll < 0.87:
            self.action = "preen"
            self.action_timer = rng.uniform(1.0, 2.0)
            self.anim.play("preen", self.art["preen"], fps=self.ACTION_FPS["preen"], loop=False, restart=True)
        elif roll < 0.93 and "coo" in self.art:
            self.action = "coo"
            self.action_timer = rng.uniform(1.0, 1.6)
            self.anim.play("coo", self.art["coo"], fps=self.ACTION_FPS["coo"], loop=False, restart=True)
        else:
            self.action = "idle"
            self.action_timer = rng.uniform(0.8, 2.0)

    def sprite(self):
        if self.state == "waiting":
            return None
        return self.anim.frame, bird_art.ANCHORS[self.SPECIES], self.facing < 0

    SHADOW = 6.0

    def shadow(self):
        if self.state == "waiting":
            return None
        # Shrinks and softens with height, but stays visible: a bird's
        # shadow sliding over the grass is what sells the altitude.
        size = 1.0 / (1.0 + self.z * 0.011)
        fade = 1.0 / (1.0 + self.z * 0.012)
        return self.SHADOW * size, self.SHADOW * 0.3 * size, int(76 * fade)


class Pigeon(Bird):
    kind = "pigeon"
    SPECIES = "pigeon"


class Crow(Bird):
    """A crow drops in alone, struts about with a heavy walk, caws, and
    is in no hurry to leave on account of a cat."""

    kind = "crow"
    SPECIES = "crow"
    CRUISE = 64.0
    WALK = 13.0
    WARY = (22.0, 34.0, 56.0)    # bold
    PERSONAL = (20, 10)
    SHADOW = 8.0
    ACTION_FPS = {"peck": 7.0, "preen": 3.5, "coo": 5.0}
    watch_only = True            # far too big to hunt: Mochi only stares

    def __init__(self, world, land_x, land_y, delay=0.0):
        super().__init__(world, land_x, land_y, delay)
        self.stay = self.rng.uniform(40, 90)

    def interest(self, cat):
        return 0.0 if self.state != "ground" else 1.0


class Sparrow(Bird):
    """Sparrows come in small, twitchy flocks and hop rather than walk."""

    kind = "sparrow"
    SPECIES = "sparrow"
    CRUISE = 62.0
    WALK = 14.0
    WARY = (40.0, 58.0, 80.0)
    PERSONAL = (8, 5)
    SHADOW = 3.6
    ACTION_FPS = {"peck": 12.0, "preen": 5.0}

    def __init__(self, world, land_x, land_y, delay=0.0):
        super().__init__(world, land_x, land_y, delay)
        self.cruise_z = self.rng.uniform(35, 60)
        self.z = self.cruise_z
        self.stay = self.rng.uniform(20, 60)

    def interest(self, cat):
        return 0.8 * super().interest(cat)


def approach_value(value, target, step):
    if value < target:
        return min(target, value + step)
    return max(target, value - step)


# ==========================================================================
# Butterfly

class Butterfly(Entity):
    kind = "butterfly"
    ANCHOR = (4, 6)

    def __init__(self, world, species=None):
        rng = world.rng
        side = rng.choice((-1, 1))
        x = -6 if side < 0 else world.width + 6
        super().__init__(world, x, rng.uniform(30, world.height - 20))
        self.rng = rng
        self.species = species or rng.choice(list(critter_art.BUTTERFLY_SPECIES))
        self.frames = art()["butterfly"][self.species]
        self.heading = 0.0 if side < 0 else math.pi
        self.speed = rng.uniform(13, 21)
        self.z = rng.uniform(12, 28)
        self.cruise = self.z
        self.state = "flying"
        self.timer = rng.uniform(5, 12)
        self.flap = rng.random()
        self.flap_rate = rng.uniform(11, 15)
        self.glide = 0.0
        self.perch = None
        self.leaving = False
        self.life = rng.uniform(70, 200)
        self.flee_timer = 0.0
        self.t = rng.random() * 10

    def interest(self, cat):
        d = self.distance_to(cat)
        if d > 110 or self.leaving:
            return 0.0
        base = 0.75 if self.state == "perched" else 0.5 if self.z < 26 else 0.2
        return base * (1.0 - d / 110.0) + 0.1

    def on_pounce(self, cat):
        self.startle(cat)

    def notices_crouch(self, cat):
        if self.state == "perched" and self.rng.random() < self.world.dt_hint * 0.35:
            self.startle(cat)

    def startle(self, cat):
        self.state = "flying"
        self.perch = None
        self.flee_timer = self.rng.uniform(1.5, 3.0)
        dx, dy = self.x - cat.x, self.y - cat.y
        self.heading = math.atan2(dy, dx) + self.rng.uniform(-0.6, 0.6)
        self.cruise = self.rng.uniform(26, 40)

    def leave(self):
        self.leaving = True
        if self.state == "perched":
            self.state = "flying"
            self.perch = None

    def update(self, dt):
        rng = self.rng
        world = self.world
        self.t += dt
        self.life -= dt
        if self.life <= 0 or world.env.rain > 0.15:
            self.leave()
        if self.state == "perched":
            self.timer -= dt
            px, py, ph = self.perch
            self.x, self.y, self.z = px, py, float(ph)
            cat = world.cat
            if self.timer <= 0 or self.leaving or (self.distance_to(cat) < 18 and _cat_speed(cat) > 5):
                self.state = "flying"
                self.perch = None
                self.timer = rng.uniform(6, 14)
                self.cruise = rng.uniform(14, 28)
            # Slow open-close while resting.
            self.flap += dt * 0.6
            return
        speed = self.speed * (1.8 if self.flee_timer > 0 else 1.0)
        self.flee_timer = max(0.0, self.flee_timer - dt)
        if self.leaving:
            ex = -20 if self.x < world.width / 2 else world.width + 20
            target_heading = math.atan2(0.0, ex - self.x)
            self.heading += _angle_diff(target_heading, self.heading) * min(1.0, dt * 1.5)
            if self.x < -15 or self.x > world.width + 15:
                self.alive = False
        elif self.state == "to_perch":
            px, py, ph = self.perch
            dx, dy = px - self.x, py - self.y
            dist = math.hypot(dx, dy)
            self.heading += _angle_diff(math.atan2(dy, dx), self.heading) * min(1.0, dt * 4.0)
            self.cruise = ph + max(0.0, dist * 0.4)
            if dist < 2.5 and abs(self.z - ph) < 3:
                self.state = "perched"
                self.timer = rng.uniform(4, 14)
                return
            speed = max(6.0, min(speed, dist * 1.5))
        else:
            self.heading += rng.uniform(-1, 1) * 3.2 * dt + math.sin(self.t * 0.7) * 0.6 * dt
            margin = 24
            if self.x < margin or self.x > world.width - margin or self.y < margin or self.y > world.height - margin:
                centre = math.atan2(world.height / 2 - self.y, world.width / 2 - self.x)
                self.heading += _angle_diff(centre, self.heading) * min(1.0, dt * 2.0)
            self.timer -= dt
            if self.timer <= 0 and world.terrain.perches and self.flee_timer <= 0:
                near = [p for p in world.terrain.perches
                        if abs(p[0] - self.x) < 110 and abs(p[1] - self.y) < 80]
                if near:
                    self.perch = rng.choice(near)
                    self.state = "to_perch"
                else:
                    self.timer = rng.uniform(4, 9)
            if rng.random() < dt * 0.15:
                self.cruise = rng.uniform(10, 32)
        self.x += math.cos(self.heading) * speed * dt + world.env.wind.drift * 0.5 * dt
        self.y += math.sin(self.heading) * speed * 0.7 * dt
        bob = math.sin(self.t * 9.0) * 1.2
        self.z += (self.cruise + bob - self.z) * min(1.0, dt * 3.0)
        self.z = max(0.5, self.z)
        if self.glide > 0:
            self.glide -= dt
        elif rng.random() < dt * 0.4:
            self.glide = rng.uniform(0.15, 0.35)
        else:
            self.flap += dt * self.flap_rate

    def sprite(self):
        if self.state == "perched":
            frame = self.frames[0] if int(self.flap) % 2 == 0 else self.frames[2]
        elif self.glide > 0:
            frame = self.frames[0]
        else:
            frame = self.frames[(0, 1, 2, 1)[int(self.flap) % 4]]
        return frame, self.ANCHOR, False

    def shadow(self):
        k = 1.0 / (1.0 + self.z * 0.06)
        return 2.5 * k, 1.0, int(56 * k)

    @property
    def airborne(self):
        return self.state != "perched"


def _angle_diff(a, b):
    return (a - b + math.pi) % (2 * math.pi) - math.pi


# ==========================================================================
# Mouse

class Mouse(Entity):
    kind = "mouse"
    ANCHOR = (8, 9)

    def __init__(self, world, bush):
        super().__init__(world, bush.x + world.rng.uniform(-bush.rx * 0.4, bush.rx * 0.4), bush.y - 1)
        self.rng = world.rng
        self.frames = art()["mouse"]
        self.home = bush
        self.state = "emerge"
        self.timer = 0.0
        self.target = None
        self.facing = self.rng.choice((-1, 1))
        self.speed = 0.0
        self.hidden = False
        self.life = self.rng.uniform(35, 100)
        self.leaving = False
        self.flee_from = None
        self._pick_target(near=True)

    def interest(self, cat):
        if self.hidden:
            return 0.0
        d = self.distance_to(cat)
        return 0.0 if d > 150 else 0.95 - d / 300.0

    def notices_crouch(self, cat):
        if self.distance_to(cat) < 32 and self.rng.random() < self.world.dt_hint * 0.6:
            self.flee(cat)

    def on_pounce(self, cat):
        self.flee(cat, dodge=True)

    def startle(self, cat):
        self.flee(cat)

    def leave(self):
        self.leaving = True

    def flee(self, cat, dodge=False):
        if self.state == "flee":
            return
        self.state = "flee"
        self.flee_from = cat
        bushes = self.world.terrain.bushes
        if bushes:
            def score(b):
                away = math.hypot(b.x - cat.x, b.y - cat.y)
                near = math.hypot(b.x - self.x, b.y - self.y)
                return near - away * 0.5
            self.home = min(bushes, key=score)
        self.target = (self.home.x + self.rng.uniform(-4, 4), self.home.y - 2)
        if dodge:
            self.y += self.rng.choice((-6, 6))

    def _pick_target(self, near=False):
        t = self.world.terrain
        for _ in range(10):
            reach = self.rng.uniform(12, 28) if near else self.rng.uniform(18, 60)
            angle = self.rng.uniform(0, 2 * math.pi)
            tx = self.x + math.cos(angle) * reach
            ty = self.y + math.sin(angle) * reach * 0.5
            if 14 < tx < self.world.width - 14 and 26 < ty < self.world.height - 6 and not t.is_water(tx, ty):
                self.target = (tx, ty)
                return
        self.target = (self.home.x, self.home.y - 2)

    def update(self, dt):
        rng = self.rng
        world = self.world
        cat = world.cat
        self.life -= dt
        if self.life <= 0 or world.env.rain > 0.4:
            self.leaving = True
        if self.state != "flee":
            d = self.distance_to(cat)
            cs = _cat_speed(cat)
            if d < 20 or (d < 38 and cs > 16) or (d < 60 and cs > 60):
                self.flee(cat)
        if self.state in ("emerge", "dash", "flee", "home"):
            tx, ty = self.target
            dx, dy = tx - self.x, ty - self.y
            dist = math.hypot(dx, dy)
            top = 95.0 if self.state == "flee" else 66.0
            self.speed = min(top, self.speed + 400 * dt)
            if dist < 1.5:
                self.speed = 0.0
                if self.state in ("flee", "home"):
                    self.hidden = True
                    self.alive = False
                    return
                self.state = "pause"
                self.timer = rng.uniform(0.5, 2.6)
                self.anim.play("idle", self.frames["idle"], fps=rng.uniform(3, 6), restart=True)
                return
            step = min(dist, self.speed * dt)
            nx, ny = self.x + dx / dist * step, self.y + dy / dist * step
            if world.terrain.is_water(nx, ny):
                self._pick_target()
                return
            self.x, self.y = nx, ny
            if abs(dx) > 0.3:
                self.facing = 1 if dx > 0 else -1
            self.anim.play("run", self.frames["run"], stride=5.0)
            self.anim.update(dt, step)
        elif self.state in ("pause", "sit"):
            self.timer -= dt
            if self.state == "sit":
                self.anim.play("sit", self.frames["sit"], fps=0.0)
            self.anim.update(dt)
            if self.timer <= 0:
                if self.leaving:
                    self.state = "home"
                    self.target = (self.home.x, self.home.y - 2)
                elif self.state == "pause" and rng.random() < 0.3:
                    self.state = "sit"
                    self.timer = rng.uniform(0.8, 2.0)
                else:
                    self.state = "dash"
                    self._pick_target()

    def sprite(self):
        return self.anim.frame or self.frames["idle"][0], self.ANCHOR, self.facing < 0

    def shadow(self):
        return 4.0, 1.2, 60


# ==========================================================================
# Firefly

class Firefly(Entity):
    kind = "firefly"

    def __init__(self, world):
        rng = world.rng
        super().__init__(world, rng.uniform(10, world.width - 10), rng.uniform(30, world.height - 10))
        self.rng = rng
        self.z = rng.uniform(4, 24)
        self.period = rng.uniform(1.8, 4.5)
        self.phase = rng.uniform(0, self.period)
        self.flash = rng.uniform(0.5, 1.1)
        self.heading = rng.uniform(0, 2 * math.pi)
        self.speed = rng.uniform(3, 8)
        self.fade = 0.0
        self.leaving = False
        self.t = 0.0

    def leave(self):
        self.leaving = True

    def brightness(self):
        p = (self.t + self.phase) % self.period
        if p > self.flash:
            return 0.0
        return math.sin(math.pi * p / self.flash) * self.fade

    def update(self, dt):
        self.t += dt
        self.fade = max(0.0, self.fade - dt * 0.4) if self.leaving else min(1.0, self.fade + dt * 0.3)
        if self.leaving and self.fade <= 0:
            self.alive = False
            return
        self.heading += self.rng.uniform(-1, 1) * 1.8 * dt
        w, h = self.world.width, self.world.height
        if not (16 < self.x < w - 16 and 30 < self.y < h - 12):
            centre = math.atan2(h / 2 - self.y, w / 2 - self.x)
            self.heading += _angle_diff(centre, self.heading) * min(1.0, dt * 2.0)
        self.x += math.cos(self.heading) * self.speed * dt
        self.y += math.sin(self.heading) * self.speed * 0.6 * dt
        self.z = clamp(self.z + math.sin(self.t * 0.8 + self.phase) * 3.0 * dt, 2.0, 30.0)

    def sprite(self):
        return None

    def glow(self):
        b = self.brightness()
        if b < 0.05:
            return None
        return 13, (int(170 * b), int(180 * b), int(80 * b))

    def draw_glow(self, r):
        b = self.brightness()
        if b < 0.05:
            return
        r.blit_px(r.glow_sprite_scaled(4, (int(140 * b), int(150 * b), int(50 * b))), self.x - 4, self.y - self.z - 4, add=True)
        r.blit_px(r.dot((255, 250, 170), int(255 * b), 1, 1), self.x, self.y - self.z, add=True)

    @property
    def airborne(self):
        return True


# ==========================================================================
# Ladybird

class Ladybug(Entity):
    kind = "ladybug"

    def __init__(self, world):
        rng = world.rng
        t = world.terrain
        for _ in range(20):
            x, y = rng.uniform(20, world.width - 20), rng.uniform(36, world.height - 10)
            if t.free_ground(x, y):
                break
        super().__init__(world, x, y)
        self.rng = rng
        self.frames = art()["ladybug"]
        self.heading = rng.choice(("up", "down", "left", "right"))
        self.state = "crawl"
        self.timer = rng.uniform(2, 6)
        self.life = rng.uniform(40, 120)
        self.vx = self.vy = 0.0
        self.leaving = False
        self.z = 0.0

    def interest(self, cat):
        if self.state != "crawl" and self.state != "rest":
            return 0.0
        d = self.distance_to(cat)
        return 0.0 if d > 55 else 0.3

    def on_pounce(self, cat):
        self._fly()

    def startle(self, cat):
        self._fly()

    def notices_crouch(self, cat):
        pass

    def leave(self):
        self.leaving = True

    def _fly(self):
        if self.state == "fly":
            return
        self.state = "fly"
        angle = self.rng.uniform(0, 2 * math.pi)
        self.vx, self.vy = math.cos(angle) * 28, math.sin(angle) * 16

    def update(self, dt):
        rng = self.rng
        self.life -= dt
        if (self.life <= 0 or self.leaving) and self.state != "fly":
            self._fly()
        if self.state == "fly":
            self.z = min(26.0, self.z + 30 * dt)
            self.x += self.vx * dt
            self.y += self.vy * dt
            if not (-10 < self.x < self.world.width + 10 and -10 < self.y < self.world.height + 10):
                self.alive = False
            return
        self.timer -= dt
        if self.timer <= 0:
            if self.state == "crawl" and rng.random() < 0.4:
                self.state = "rest"
                self.timer = rng.uniform(1, 4)
            else:
                self.state = "crawl"
                self.heading = rng.choice(("up", "down", "left", "right"))
                self.timer = rng.uniform(2, 6)
        if self.state == "crawl":
            vx, vy = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}[self.heading]
            nx, ny = self.x + vx * 3.5 * dt, self.y + vy * 3.5 * dt
            if self.world.terrain.free_ground(nx, ny) and 8 < nx < self.world.width - 8 and 30 < ny < self.world.height - 6:
                self.x, self.y = nx, ny
            else:
                self.timer = 0.0

    def sprite(self):
        return self.frames[self.heading], (2, 3), False

    def shadow(self):
        if self.z > 1:
            return 1.5, 0.8, 40
        return None

    @property
    def airborne(self):
        return self.state == "fly"


# ==========================================================================
# Dragonfly

class Dragonfly(Entity):
    kind = "dragonfly"

    def __init__(self, world):
        rng = world.rng
        pond = world.terrain.pond
        side = rng.choice((-1, 1))
        super().__init__(world, -8 if side < 0 else world.width + 8, pond.cy + rng.uniform(-30, 30))
        self.rng = rng
        self.pond = pond
        self.frames = art()["dragonfly"]
        self.z = rng.uniform(10, 20)
        self.state = "dart"
        self.timer = 0.0
        self.heading = "right" if side < 0 else "left"
        self.target = self._spot()
        self.leaving = False
        self.wing = 0.0

    def _spot(self):
        p = self.pond
        a = self.rng.uniform(0, 2 * math.pi)
        r = self.rng.uniform(0.3, 1.25)
        return p.cx + math.cos(a) * p.rx * r, p.cy + math.sin(a) * p.ry * r

    def interest(self, cat):
        return 0.0

    def leave(self):
        self.leaving = True
        self.state = "dart"
        self.target = (-30 if self.x < self.world.width / 2 else self.world.width + 30, self.y)

    def update(self, dt):
        rng = self.rng
        self.wing += dt * 22
        if self.state == "dart":
            tx, ty = self.target
            dx, dy = tx - self.x, ty - self.y
            dist = math.hypot(dx, dy)
            if abs(dx) >= abs(dy):
                self.heading = "right" if dx > 0 else "left"
            else:
                self.heading = "down" if dy > 0 else "up"
            if dist < 2:
                if self.leaving:
                    self.alive = False
                    return
                self.state = "hover"
                self.timer = rng.uniform(0.8, 3.2)
            else:
                step = min(dist, 110 * dt)
                self.x += dx / dist * step
                self.y += dy / dist * step
        else:
            self.timer -= dt
            self.x += rng.uniform(-6, 6) * dt
            self.y += rng.uniform(-4, 4) * dt
            if self.world.terrain.is_water(self.x, self.y) and rng.random() < dt * 0.25:
                self.world.water.ripple(self.x, self.y, small=True)
            if self.timer <= 0:
                self.state = "dart"
                self.target = self._spot()
                self.z = rng.uniform(8, 20)

    def sprite(self):
        frames = self.frames[self.heading]
        return frames[int(self.wing) % 2], (frames[0].get_width() / 2, frames[0].get_height() / 2), False

    def shadow(self):
        if self.world.terrain.is_water(self.x, self.y):
            return None
        return 2.5, 1.0, 40

    @property
    def airborne(self):
        return True


# ==========================================================================
# Frog

def bank_points(terrain):
    """Dry spots right at the water's edge, with the side the water is on."""
    cached = getattr(terrain, "_bank_points", None)
    if cached is not None:
        return cached
    points = []
    water = terrain.water
    h, w = water.shape
    reeds = [(p.x, p.y) for p in terrain.props if p.kind == "reeds"]
    ys, xs = water.nonzero()
    for y, x in zip(ys[::7], xs[::7]):
        for dx in (-4, 4):
            nx = x + dx
            if not (0 <= nx < w) or water[y, nx] or terrain.solid[y, nx]:
                continue
            if any(abs(nx - rx) < 12 and -4 < ry - y < 14 for rx, ry in reeds):
                continue  # it would sit hidden in the reeds
            points.append((float(nx), float(y), 1 if dx < 0 else -1))
    terrain._bank_points = points
    return points


class Frog(Entity):
    """Sits on the bank, croaks at dusk and in the rain, hops along the edge,
    and plops into the pond when the cat comes too close."""

    kind = "frog"
    watch_only = True

    def __init__(self, world):
        rng = world.rng
        self.rng = rng
        self.banks = bank_points(world.terrain)
        x, y, facing = rng.choice(self.banks)
        super().__init__(world, x, y)
        self.frames = art()["frog"]
        self.facing = facing
        self.state = "swim"
        self.timer = rng.uniform(1.0, 4.0)
        self.hop_from = self.hop_to = None
        self.hop_t = 0.0
        self.leaving = False
        self._water_spot()

    def _water_spot(self):
        p = self.world.terrain.pond
        for _ in range(12):
            wx = self.x + self.facing * self.rng.uniform(6, 16)
            wy = self.y + self.rng.uniform(-3, 3)
            if self.world.terrain.is_water(wx, wy) and self.world.terrain.is_water(wx + 4, wy) \
                    and self.world.terrain.is_water(wx - 4, wy):
                self.swim_spot = (wx, wy)
                return
        self.swim_spot = (p.cx, p.cy)

    @property
    def hidden(self):
        return self.state in ("swim", "under")

    def interest(self, cat):
        if self.state != "sit":
            return 0.0
        d = self.distance_to(cat)
        return 0.0 if d > 110 else 0.5 * (1.0 - d / 110.0)

    def on_pounce(self, cat):
        self._dive()

    startle = on_pounce

    def notices_crouch(self, cat):
        if self.distance_to(cat) < 40:
            self._dive()

    def leave(self):
        self.leaving = True

    def _hop(self, to, then, facing=None):
        self.land_facing = facing
        self.hop_from = (self.x, self.y)
        self.hop_to = to
        self.hop_t = 0.0
        self.after_hop = then
        self.state = "hop"
        self.facing = 1 if to[0] > self.x else -1 if to[0] < self.x else self.facing

    def _dive(self):
        if self.state in ("sit", "croak"):
            self._water_spot()
            self._hop(self.swim_spot, "splash")

    def update(self, dt):
        rng = self.rng
        world = self.world
        cat = world.cat
        env = world.env
        if self.state == "hop":
            self.hop_t += dt / 0.45
            f = min(1.0, self.hop_t)
            (x0, y0), (x1, y1) = self.hop_from, self.hop_to
            self.x = x0 + (x1 - x0) * f
            self.y = y0 + (y1 - y0) * f
            self.z = 7.0 * 4 * f * (1 - f)
            self.anim.play("hop", self.frames["hop"], fps=0.0)
            self.anim.phase = 0.0 if f < 0.12 else 1.0 if f < 0.55 else 2.0 if f < 0.9 else 3.0
            if f >= 1.0:
                self.z = 0.0
                if self.after_hop == "splash":
                    world.water.ripple(self.x, self.y)
                    world.particles.splash(self.x, self.y)
                    self.state = "under"
                    self.timer = rng.uniform(2.0, 6.0)
                else:
                    self.state = "sit"
                    self.timer = rng.uniform(4.0, 14.0)
                    if self.land_facing:
                        self.facing = self.land_facing
            return
        if self.state == "under":
            self.timer -= dt
            if self.timer <= 0:
                if self.leaving:
                    self.alive = False
                    return
                self.state = "swim"
                self.timer = rng.uniform(4.0, 12.0)
                self.x, self.y = self.swim_spot
                world.water.ripple(self.x, self.y, small=True)
            return
        if self.state == "swim":
            self.timer -= dt
            sx, sy = self.swim_spot
            self.x += (sx - self.x) * min(1.0, dt * 0.5)
            self.y += (sy - self.y) * min(1.0, dt * 0.5)
            if rng.random() < dt * 0.3:
                world.water.ripple(self.x, self.y, small=True)
            self.anim.play("swim", self.frames["swim"], fps=0.0)
            if self.timer <= 0:
                if self.leaving:
                    self.state = "under"
                    self.timer = 0.0
                    world.water.ripple(self.x, self.y, small=True)
                    return
                near = [b for b in self.banks if math.hypot(b[0] - self.x, b[1] - self.y) < 40]
                if near and cat.distance_to(self) > 70:
                    bx, by, facing = rng.choice(near)
                    world.water.ripple(self.x, self.y, small=True)
                    self._hop((bx, by), "land", facing)
                else:
                    self.timer = rng.uniform(3.0, 8.0)
            return
        # on the bank
        d = self.distance_to(cat)
        if d < 30 or (d < 50 and _cat_speed(cat) > 20) or self.leaving:
            self._dive()
            return
        self.timer -= dt
        evening = env.clock.between(19.0, 6.0) or env.rain > 0.15
        if self.state == "croak":
            if self.anim.done:
                self.state = "sit"
                self.timer = rng.uniform(1.0, 3.0) if evening else rng.uniform(6, 14)
        else:
            self.anim.play("sit", self.frames["sit"], fps=1.2)
            if self.timer <= 0:
                roll = rng.random()
                if roll < (0.6 if evening else 0.15):
                    self.state = "croak"
                    self.anim.play("croak", self.frames["croak"], fps=5, loop=False, restart=True)
                elif roll < 0.8:
                    near = [b for b in self.banks if 6 < math.hypot(b[0] - self.x, b[1] - self.y) < 30]
                    if near:
                        bx, by, facing = rng.choice(near)
                        self._hop((bx, by), "land", facing)
                    else:
                        self.timer = rng.uniform(3.0, 8.0)
                else:
                    self._dive()
        self.anim.update(dt)

    def sprite(self):
        if self.state == "under":
            return None
        return self.anim.frame or self.frames["sit"][0], critter_art.FROG_ANCHOR, self.facing < 0

    def shadow(self):
        if self.state in ("swim", "under"):
            return None
        return 4.0, 1.2, 60

    @property
    def airborne(self):
        return self.z > 3.0


# ==========================================================================
# Hedgehog

class Hedgehog(Entity):
    """A night visitor: snuffles across the meadow, nose to the ground, and
    rolls into a prickly ball if the cat comes close."""

    kind = "hedgehog"
    watch_only = True

    def __init__(self, world):
        rng = world.rng
        self.rng = rng
        side = rng.choice((-1, 1))
        y = rng.uniform(world.height * 0.35, world.height - 20)
        super().__init__(world, -12 if side < 0 else world.width + 12, y)
        self.frames = art()["hedgehog"]
        self.facing = -side
        self.state = "walk"
        self.timer = 0.0
        self.target = self._pick()
        self.leaving = False
        self.life = rng.uniform(90, 220)
        self.speed = 0.0

    def _pick(self):
        t = self.world.terrain
        for _ in range(12):
            x = self.rng.uniform(30, self.world.width - 30)
            y = self.rng.uniform(self.world.height * 0.3, self.world.height - 16)
            if t.free_ground(x, y) and abs(x - self.x) > 30:
                return x, y
        return self.world.width / 2, self.world.height * 0.6

    @property
    def hidden(self):
        return False

    def interest(self, cat):
        if self.state == "ball":
            return 0.0
        d = self.distance_to(cat)
        return 0.0 if d > 120 else 0.6 * (1.0 - d / 120.0) + 0.1

    def on_pounce(self, cat):
        self._curl()

    startle = on_pounce

    def notices_crouch(self, cat):
        self._curl()

    def leave(self):
        self.leaving = True

    def _curl(self):
        if self.state != "ball":
            self.state = "ball"
            self.timer = self.rng.uniform(6.0, 12.0)

    def update(self, dt):
        rng = self.rng
        world = self.world
        cat = world.cat
        self.life -= dt
        if self.life <= 0 and not self.leaving:
            self.leaving = True
            self.target = (-20 if self.x < world.width / 2 else world.width + 20, self.y)
        d = self.distance_to(cat)
        if self.state == "ball":
            self.speed = 0.0
            self.timer -= dt
            if d < 26:
                self.timer = max(self.timer, 2.0)
            if self.timer <= 0:
                self.state = "sniff"
                self.timer = rng.uniform(1.0, 2.0)
            self.anim.play("ball", self.frames["ball"], fps=0.0)
            return
        if d < 22 or (d < 40 and _cat_speed(cat) > 30):
            self._curl()
            return
        if self.state == "sniff":
            self.speed = 0.0
            self.timer -= dt
            self.anim.play("sniff", self.frames["sniff"], fps=5)
            if self.timer <= 0:
                self.state = "walk"
        else:
            tx, ty = self.target
            dx, dy = tx - self.x, ty - self.y
            dist = math.hypot(dx, dy)
            if dist < 2:
                if self.leaving:
                    self.alive = False
                    return
                self.state = "sniff"
                self.timer = rng.uniform(1.5, 4.0)
                self.target = self._pick()
            else:
                self.speed = min(7.0, self.speed + 10 * dt)
                step = min(dist, self.speed * dt)
                self.x += dx / dist * step
                self.y += dy / dist * step
                if abs(dx) > 0.5:
                    self.facing = 1 if dx > 0 else -1
                self.anim.play("walk", self.frames["walk"], stride=3.0)
                self.anim.update(dt, step)
                if rng.random() < dt * 0.15:
                    self.state = "sniff"
                    self.timer = rng.uniform(1.0, 2.5)
                return
        self.anim.update(dt)

    def sprite(self):
        return self.anim.frame or self.frames["walk"][0], critter_art.HOG_ANCHOR, self.facing < 0

    def shadow(self):
        return 6.0, 1.6, 64


# ==========================================================================
# Snail

class Snail(Entity):
    """Out after the rain: creeps along leaving a glistening trail, and
    pulls into its shell if anything comes near."""

    kind = "snail"

    def __init__(self, world):
        rng = world.rng
        self.rng = rng
        t = world.terrain
        for _ in range(20):
            x, y = rng.uniform(30, world.width - 30), rng.uniform(40, world.height - 14)
            if t.free_ground(x, y):
                break
        super().__init__(world, x, y)
        self.frames = art()["snail"]
        self.heading = rng.uniform(0, 2 * math.pi)
        self.trail = []
        self.state = "crawl"
        self.timer = rng.uniform(4, 10)
        self.leaving = False
        self.life = rng.uniform(120, 300)

    def interest(self, cat):
        return 0.0

    def leave(self):
        self.leaving = True

    def update(self, dt):
        rng = self.rng
        world = self.world
        self.life -= dt
        if self.life <= 0:
            self.leaving = True
        self.trail = [(x, y, age + dt) for x, y, age in self.trail if age + dt < 45.0]
        d = self.distance_to(world.cat)
        if d < 24:
            self.state = "tucked"
            self.timer = rng.uniform(4.0, 8.0)
        if self.state == "tucked":
            self.timer -= dt
            if self.timer <= 0 and d > 30:
                self.state = "crawl"
            return
        if self.leaving and world.env.sun < 0.2 or self.leaving and self.life < -60:
            self.alive = False
            return
        self.heading += rng.uniform(-1, 1) * 0.6 * dt
        speed = 1.3
        nx = self.x + math.cos(self.heading) * speed * dt
        ny = self.y + math.sin(self.heading) * speed * 0.6 * dt
        if world.terrain.free_ground(nx, ny) and 10 < nx < world.width - 10 and 30 < ny < world.height - 6:
            self.x, self.y = nx, ny
        else:
            self.heading += math.pi * 0.5
        if not self.trail or math.hypot(self.trail[-1][0] - self.x, self.trail[-1][1] - self.y) > 1.5:
            self.trail.append((self.x, self.y, 0.0))
        self.anim.play("crawl", self.frames["crawl"], fps=1.5)
        self.anim.update(dt)

    def sprite(self):
        frame = self.frames["tucked"][0] if self.state == "tucked" else self.anim.frame or self.frames["crawl"][0]
        return frame, critter_art.SNAIL_ANCHOR, math.cos(self.heading) < 0

    def shadow(self):
        return 3.0, 1.0, 50

    def draw_glow(self, r):
        # The slime trail catches the light: a faint silver line that fades.
        light = max(0.3, self.world.env.sun)
        for x, y, age in self.trail[::2]:
            k = (1.0 - age / 45.0) * light
            if k > 0.05:
                r.blit_px(r.dot((int(60 * k), int(64 * k), int(70 * k)), 255), x, y, add=True)


# ==========================================================================
# Bee

class Bee(Entity):
    """Visits flowers on sunny days with a buzzing, jittery flight."""

    kind = "bee"

    def __init__(self, world):
        rng = world.rng
        self.rng = rng
        side = rng.choice((-1, 1))
        super().__init__(world, -4 if side < 0 else world.width + 4, rng.uniform(40, world.height - 20))
        self.frames = art()["bee"]
        self.z = rng.uniform(8, 16)
        self.state = "fly"
        self.flower = None
        self.timer = 0.0
        self.leaving = False
        self.life = rng.uniform(60, 160)
        self.t = rng.random() * 10
        self.vx = self.vy = 0.0
        self._choose()

    def interest(self, cat):
        return 0.0

    def leave(self):
        self.leaving = True
        self.flower = None
        self.state = "fly"

    def _choose(self):
        perches = self.world.terrain.perches
        if perches and not self.leaving:
            near = [p for p in perches if abs(p[0] - self.x) < 120 and abs(p[1] - self.y) < 90] or perches
            self.flower = self.rng.choice(near)
        else:
            self.flower = None

    def update(self, dt):
        rng = self.rng
        world = self.world
        self.t += dt
        self.life -= dt
        if self.life <= 0 or world.env.rain > 0.1:
            if not self.leaving:
                self.leave()
        if self.state == "visit":
            self.timer -= dt
            px, py, ph = self.flower
            self.x = px + math.sin(self.t * 7) * 0.6
            self.y = py
            self.z = ph + 0.5
            if self.timer <= 0:
                self.state = "fly"
                self._choose()
            return
        if self.flower is None:
            tx = -20 if self.x < world.width / 2 else world.width + 20
            ty, tz = self.y, 18.0
        else:
            tx, ty, tz = self.flower[0], self.flower[1], self.flower[2] + 0.5
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if self.flower is not None and dist < 1.5 and abs(self.z - tz) < 1.5:
            self.state = "visit"
            self.timer = rng.uniform(1.5, 4.0)
            return
        if self.flower is None and (self.x < -10 or self.x > world.width + 10):
            self.alive = False
            return
        speed = min(34.0, dist * 2.5 + 6)
        jitter = 30.0
        self.vx += ((dx / (dist or 1)) * speed - self.vx) * min(1.0, dt * 5) + rng.uniform(-jitter, jitter) * dt
        self.vy += ((dy / (dist or 1)) * speed * 0.8 - self.vy) * min(1.0, dt * 5) + rng.uniform(-jitter, jitter) * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += (tz + math.sin(self.t * 9) * 1.2 - self.z) * min(1.0, dt * 4)

    def sprite(self):
        return self.frames[int(self.t * 30) % 2], (2, 2), self.vx < 0

    @property
    def airborne(self):
        return True


# ==========================================================================
# Birds passing high overhead: only their shadows cross the meadow.

class BirdFlock:
    def __init__(self, world):
        rng = world.rng
        self.world = world
        self.frames = art()["bird_shadow"]
        count = rng.choice((1, 1, 2, 3, 3, 5))
        direction = rng.choice((-1, 1))
        speed = rng.uniform(70, 115)
        self.vx = direction * speed
        self.vy = rng.uniform(-0.25, 0.25) * speed
        start_x = -20 if direction > 0 else world.width + 20
        start_y = rng.uniform(world.height * 0.15, world.height * 0.85)
        self.birds = []
        for i in range(count):
            rank = (i + 1) // 2
            side = -1 if i % 2 else 1
            self.birds.append([start_x - direction * rank * 10, start_y + side * rank * 6, rng.random() * 4])
        self.alive = True

    def update(self, dt):
        w, h = self.world.width, self.world.height
        inside = False
        for b in self.birds:
            b[0] += self.vx * dt
            b[1] += self.vy * dt
            b[2] += dt * 5
            if -30 < b[0] < w + 30 and -30 < b[1] < h + 30:
                inside = True
        self.alive = inside

    def draw_shadow(self, light):
        import pygame
        for x, y, flap in self.birds:
            frame = self.frames[int(flap) % 2]
            light.blit(frame, (round(x), round(y)), special_flags=pygame.BLEND_MULT)


# ==========================================================================
# Rare visitors

class GoldenButterfly(Butterfly):
    """Seen once in a long while: a butterfly that glints like a coin and
    leaves a trail of sparkles.  It lingers, and Mochi follows it."""

    kind = "golden_butterfly"

    def __init__(self, world):
        super().__init__(world, species="golden")
        self.life = world.rng.uniform(150, 220)
        self.trail = []           # [x, y, age]
        self._sparkle = 0.0

    def update(self, dt):
        super().update(dt)
        self._sparkle -= dt
        if self._sparkle <= 0 and self.state != "perched":
            self._sparkle = 0.08
            self.trail.append([self.x + self.rng.uniform(-1, 1), self.y - self.z + self.rng.uniform(-1, 1), 0.0])
        for sp in self.trail:
            sp[2] += dt
        self.trail = [sp for sp in self.trail if sp[2] < 1.4]

    def interest(self, cat):
        return 0.0 if self.leaving else 1.0

    def draw_glow(self, r):
        for x, y, age in self.trail:
            a = int(220 * (1.0 - age / 1.4))
            if a > 20:
                r.blit_px(r.dot((255, 220, 120), a, 1, 1), x, y, add=True)
        twinkle = 0.6 + 0.4 * math.sin(self.t * 7.0)
        r.blit_px(r.dot((120, 96, 40), int(255 * twinkle), 1, 1), self.x, self.y - self.z - 3, add=True)


class Bat(Entity):
    """A bat hawking for insects at dusk: quick, jinking, never still."""

    kind = "bat"
    ANCHOR = (3, 2)

    def __init__(self, world):
        rng = world.rng
        side = rng.choice((-1, 1))
        super().__init__(world, -8 if side < 0 else world.width + 8, rng.uniform(30, world.height - 40))
        self.rng = rng
        self.frames = art()["bat"]
        self.home = (rng.uniform(world.width * 0.25, world.width * 0.75), rng.uniform(50, world.height - 50))
        self.heading = 0.0 if side < 0 else math.pi
        self.speed = rng.uniform(42, 58)
        self.z = rng.uniform(24, 40)
        self.t = rng.random() * 10
        self.life = rng.uniform(80, 160)
        self.leaving = False

    def leave(self):
        self.leaving = True

    def update(self, dt):
        rng = self.rng
        world = self.world
        self.t += dt
        self.life -= dt
        if self.life <= 0 or world.env.sun > 0.35 or world.env.rain > 0.2:
            self.leaving = True
        if self.leaving:
            ex = -20 if self.home[0] < world.width / 2 else world.width + 20
            want = math.atan2(self.home[1] - self.y, ex - self.x)
            if self.x < -12 or self.x > world.width + 12:
                self.alive = False
        else:
            # Loop around a slowly wandering hunting ground, jinking after moths.
            hx, hy = self.home
            self.home = (clamp(hx + rng.uniform(-8, 8) * dt, 40, world.width - 40),
                         clamp(hy + rng.uniform(-6, 6) * dt, 40, world.height - 40))
            want = math.atan2(hy - self.y, hx - self.x) + math.sin(self.t * 1.3) * 1.4
        self.heading += _angle_diff(want, self.heading) * min(1.0, dt * 3.0) + rng.uniform(-5, 5) * dt
        self.x += math.cos(self.heading) * self.speed * dt
        self.y += math.sin(self.heading) * self.speed * 0.7 * dt
        self.z = clamp(self.z + math.sin(self.t * 2.1) * 6 * dt, 16, 46)

    def sprite(self):
        return self.frames[int(self.t * 16) % 3], self.ANCHOR, False

    def shadow(self):
        return None

    @property
    def airborne(self):
        return True


class Pumpkin(Entity):
    """A carved pumpkin left by the bowl at the end of October; its face
    glows after dark."""

    kind = "pumpkin"
    ANCHOR = (4, 7)

    def __init__(self, world, x, y):
        super().__init__(world, x, y)
        self.frames = art()["pumpkin"]
        self.flicker = world.rng.random() * 10

    def update(self, dt):
        self.flicker += dt
        today = self.world.env.clock.date
        if not halloween(today):
            self.alive = False

    def lit(self):
        return self.world.env.sun < 0.35

    def sprite(self):
        return self.frames[1 if self.lit() else 0], self.ANCHOR, False

    def shadow(self):
        return 4.5, 1.6, 70

    def glow(self):
        if not self.lit():
            return None
        f = 0.85 + 0.15 * math.sin(self.flicker * 9.0) * math.sin(self.flicker * 2.3)
        return 13, (int(150 * f), int(96 * f), int(36 * f))


def halloween(date):
    return (date.month == 10 and date.day >= 24) or (date.month == 11 and date.day <= 1)


class Fox(Entity):
    """A red fox passing through at dawn or dusk: it trots in from one
    side, stops halfway to sniff the air and look about, and trots off the
    other side.  It gives the cat a wide berth."""

    kind = "fox"
    watch_only = True
    watch_distance = 85.0     # Mochi keeps well back
    TROT = 34.0
    WALK = 17.0

    def __init__(self, world):
        rng = world.rng
        self.rng = rng
        self.lib = art()["fox"]
        side = rng.choice((-1, 1))
        self.route, self.after_pause = plan_crossing(world, side)
        start = (-30.0 if side < 0 else world.width + 30.0, self.route[0][1] if self.route else 0.0)
        super().__init__(world, *start)
        self.exit_x = world.width + 30.0 if side < 0 else -30.0
        self.facing = 1 if side < 0 else -1
        self.state = "trot"
        self.timer = 0.0
        self.paused = False
        self.fleeing = False

    @property
    def ok(self):
        return self.route is not None

    def interest(self, cat):
        return 0.0 if self.state == "gone" else 1.0

    @property
    def hidden(self):
        return self.x < -10 or self.x > self.world.width + 10

    def _play(self, name, **kw):
        key = f"{name}_{'right' if self.facing > 0 else 'left'}"
        self.anim.play(key, self.lib[key], **kw)

    def update(self, dt):
        world = self.world
        if not self.fleeing and not self.hidden and self.distance_to(world.cat) < 50:
            # Too close for comfort: bolt for the edge.
            self.fleeing = True
            self.paused = True
            self.state = "trot"
            t = world.terrain
            side = -1 if world.cat.x > self.x else 1
            edge = _edge_point(t, side, self.y)
            path = find_path(t.blocked, (self.x, self.y), edge, wide=t.blocked_wide) if edge else None
            off = -30.0 if side < 0 else world.width + 30.0
            if path:
                self.route = [tuple(p) for p in path] + [(off, edge[1])]
            elif not t.walkable(self.x, self.y):
                self.route = [(off, self.y)]   # still off the meadow's edge
            # (no way out from here: hurry on along the planned route)
        if self.state in ("sniff", "look"):
            self.timer -= dt
            self._play(self.state, fps=6, loop=self.state == "sniff")
            if self.timer <= 0:
                if self.state == "sniff":
                    self.state, self.timer = "look", self.rng.uniform(2.0, 3.5)
                    cat = world.cat
                    if abs(cat.x - self.x) > 6:
                        self.facing = 1 if cat.x > self.x else -1
                else:
                    self.state = "trot"
                    self.route = list(self.after_pause) + [(self.exit_x, self.after_pause[-1][1])]
                    self.paused = True
            self.anim.update(dt)
            return
        if not self.route:
            self.alive = False
            return
        tx, ty = self.route[0]
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy)
        cat = world.cat
        near_cat = self.distance_to(cat) < 70
        speed = self.TROT if (near_cat or not self.paused) else self.WALK
        if self.fleeing:
            speed = self.TROT * 2.0
        step = min(d, speed * dt)
        if d > 0.01:
            self.x += dx / d * step
            self.y += dy / d * step
            if abs(dx) > 1.0:
                self.facing = 1 if dx > 0 else -1
        if d - step < 0.5:
            self.route.pop(0)
            if not self.route and not self.paused:
                self.state, self.timer = "sniff", self.rng.uniform(2.5, 4.0)
        gait = "trot" if speed == self.TROT else "walk"
        self._play(gait, stride=fox_art.STRIDES[gait])
        self.anim.update(dt, step)
        if self.paused and not self.route:
            self.alive = False

    def sprite(self):
        return self.anim.frame, fox_art.ANCHOR, False

    def shadow(self):
        return 17.0, 3.4, 70, -1


def plan_crossing(world, side, mids=None, keep_off=85.0):
    """A route in from one edge to a stopping point, and on out the other
    edge, planned around the cat as if she were a rock.  ``mids`` are
    preferred stopping points (a deer heads for the pond).  Returns
    (route in, route out) or (None, None)."""
    rng = world.rng
    t = world.terrain
    avoid = t.blocked.copy()
    cx, cy = world.cat.x, world.cat.y
    yy, xx = np.ogrid[:t.height, :t.width]
    avoid |= ((xx - cx) / 55.0) ** 2 + ((yy - cy) / 40.0) ** 2 < 1.0
    wide = widen(avoid, 2)
    for _ in range(80):
        y0 = rng.uniform(world.height * 0.25, world.height * 0.9)
        y1 = clamp(y0 + rng.uniform(-60, 60), world.height * 0.2, world.height * 0.92)
        a = _edge_point(t, side, y0)
        b = _edge_point(t, -side, y1)
        if a is None or b is None:
            continue
        if mids:
            mid = rng.choice(mids)
        else:
            mid = (rng.uniform(0.25, 0.75) * world.width, (y0 + y1) / 2 + rng.uniform(-30, 30))
        if math.hypot(mid[0] - cx, mid[1] - cy) < min(keep_off, world.width * 0.25):
            continue   # it stops well away from the cat
        if not t.walkable(*mid) or avoid[int(mid[1]), int(mid[0])]:
            continue
        first = find_path(avoid, a, mid, wide=wide)
        second = find_path(avoid, mid, b, wide=wide) if first else None
        if first and second:
            return [a] + [tuple(p) for p in first], [tuple(p) for p in second]
    return None, None


def _edge_point(t, side, y):
    """The first open ground in from the left (side -1) or right edge."""
    xs = range(2, t.width // 3) if side < 0 else range(t.width - 3, t.width * 2 // 3, -1)
    x = next((x for x in xs if t.walkable(x, y)), None)
    return None if x is None else (float(x), y)


# ==========================================================================
# Small common visitors

class Moth(Butterfly):
    """Summer nights: a pale moth fluttering low over the grass."""

    kind = "moth"

    def __init__(self, world):
        super().__init__(world, species="moth")
        rng = world.rng
        self.speed = rng.uniform(9, 14)
        self.z = self.cruise = rng.uniform(6, 16)
        self.life = rng.uniform(60, 140)
        self.flap_rate = rng.uniform(16, 20)

    def update(self, dt):
        if self.world.env.sun > 0.3:
            self.leave()
        super().update(dt)
        if self.state != "perched" and not self.leaving:
            self.cruise = min(self.cruise, 18.0)


class Grasshopper(Entity):
    """A grasshopper sunning in the grass: it sits, then springs off in a
    long arc, and springs further when a cat comes creeping."""

    kind = "grasshopper"
    ANCHOR = (3, 2)

    def __init__(self, world, x, y):
        super().__init__(world, x, y)
        self.rng = world.rng
        self.frames = art()["grasshopper"]
        self.facing = self.rng.choice((-1, 1))
        self.timer = self.rng.uniform(2, 5)
        self.hop = None          # (x0, y0, x1, y1, t, duration, height)
        self.life = self.rng.uniform(70, 140)
        self.leaving = False

    def interest(self, cat):
        if self.hop or self.leaving:
            return 0.0
        d = self.distance_to(cat)
        return 0.0 if d > 140 else 0.9 - d / 300.0

    def notices_crouch(self, cat):
        if self.distance_to(cat) < 28 and self.rng.random() < self.world.dt_hint * 0.5:
            self.spring(away_from=cat, far=True)

    def on_pounce(self, cat):
        self.spring(away_from=cat, far=True)

    startle = on_pounce

    def leave(self):
        self.leaving = True

    @property
    def hidden(self):
        return False

    def spring(self, away_from=None, far=False):
        if self.hop:
            return
        rng = self.rng
        t = self.world.terrain
        for _ in range(12):
            if away_from is not None:
                a = math.atan2(self.y - away_from.y, self.x - away_from.x) + rng.uniform(-0.7, 0.7)
            elif self.leaving:
                a = 0.0 if self.x > self.world.width / 2 else math.pi
            else:
                a = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(30, 46) if far else rng.uniform(10, 22)
            x1, y1 = self.x + math.cos(a) * dist, self.y + math.sin(a) * dist * 0.6
            off = not (0 < x1 < self.world.width and 0 < y1 < self.world.height)
            if off and self.leaving:
                break
            if not off and t.free_ground(x1, y1):
                break
        else:
            return
        self.facing = 1 if x1 > self.x else -1
        self.hop = (self.x, self.y, x1, y1, 0.0, 0.32 + dist / 160, 4 + dist * 0.18)

    def update(self, dt):
        world = self.world
        self.life -= dt
        if self.life <= 0 or world.env.rain > 0.1 or world.env.sun < 0.4:
            self.leaving = True
        if self.hop:
            x0, y0, x1, y1, t, dur, height = self.hop
            t += dt
            f = min(1.0, t / dur)
            self.x, self.y = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            self.z = 4 * height * f * (1 - f)
            self.hop = (x0, y0, x1, y1, t, dur, height) if f < 1.0 else None
            if not self.hop:
                self.z = 0.0
                self.timer = self.rng.uniform(1.5, 5.0) if not self.leaving else 0.3
                if not (-4 < self.x < world.width + 4 and -4 < self.y < world.height + 4):
                    self.alive = False
            return
        cat = world.cat
        if self.distance_to(cat) < 20 and _cat_speed(cat) > 8:
            self.spring(away_from=cat, far=True)
            return
        self.timer -= dt
        if self.timer <= 0:
            self.spring()

    def sprite(self):
        frame = self.frames[1 if self.hop else 0]
        return frame, self.ANCHOR, self.facing < 0

    def shadow(self):
        return 1.8, 0.7, 50


class PeekingMouse(Mouse):
    """A mouse that only peeks out from under a bush, whiskers going, and
    ducks back in."""

    def __init__(self, world, bush):
        super().__init__(world, bush)
        side = self.rng.choice((-1, 1))
        self.x = bush.x + side * bush.rx * 0.85
        self.y = bush.y + bush.ry * 0.3
        self.facing = side
        self.state = "peek"
        self.timer = self.rng.uniform(3.0, 6.0)
        self.anim.play("idle", self.frames["idle"], fps=5.0)

    def update(self, dt):
        if self.state != "peek":
            super().update(dt)
            return
        cat = self.world.cat
        self.timer -= dt
        self.anim.update(dt)
        if self.distance_to(cat) < 40 and _cat_speed(cat) > 10:
            self.flee(cat)
        elif self.timer <= 0:
            self.hidden = True
            self.alive = False


class Deer(Entity):
    """A roe deer, seen once in a long while at dawn: she steps out of the
    mist, walks to the pond, drinks and grazes with an ear always turning,
    and walks on.  If the cat comes close she bounds away, white rump
    flashing."""

    kind = "deer"
    watch_only = True
    watch_distance = 120.0
    WALK = 13.0
    BOUND = 90.0

    def __init__(self, world):
        rng = world.rng
        self.rng = rng
        self.lib = art()["deer"]
        side = rng.choice((-1, 1))
        t = world.terrain
        mids = [tuple(s.approach) for s in t.spots["drink"]] or None
        self.route, self.after = plan_crossing(world, side, mids=mids, keep_off=100.0)
        if self.route is None:      # the pond is out of reach today: graze out in the meadow
            self.route, self.after = plan_crossing(world, side, keep_off=100.0)
        start = (-40.0 if side < 0 else world.width + 40.0, self.route[0][1] if self.route else 0.0)
        super().__init__(world, *start)
        self.exit_x = world.width + 40.0 if side < 0 else -40.0
        self.facing = 1 if side < 0 else -1
        self.state = "walk"
        self.timer = 0.0
        self.bouts = rng.randint(2, 4)
        self.leaving = False
        self.fleeing = False

    @property
    def ok(self):
        return self.route is not None

    def interest(self, cat):
        return 0.0 if self.hidden else 1.0

    @property
    def hidden(self):
        return self.x < -20 or self.x > self.world.width + 20

    def _play(self, name, **kw):
        key = f"{name}_{'right' if self.facing > 0 else 'left'}"
        self.anim.play(key, self.lib[key], **kw)

    def _bolt(self):
        world = self.world
        t = world.terrain
        side = -1 if world.cat.x > self.x else 1
        edge = _edge_point(t, side, self.y)
        path = find_path(t.blocked, (self.x, self.y), edge, wide=t.blocked_wide) if edge else None
        off = -40.0 if side < 0 else world.width + 40.0
        self.route = ([tuple(p) for p in path] + [(off, edge[1])]) if path else [(off, self.y)]
        self.fleeing = True
        self.leaving = True
        self.state = "walk"

    def update(self, dt):
        world = self.world
        cat = world.cat
        d = self.distance_to(cat)
        asleep = getattr(cat, "posture", "") == "sleep"
        close = d < (28 if asleep else 60) or (d < 110 and _cat_speed(cat) > 30)
        if close and not self.fleeing and not self.hidden and self.state != "startled":
            self.state, self.timer = "startled", 0.6      # a heartbeat of stillness, then away
        if self.state in ("graze", "look", "startled"):
            self.timer -= dt
            key = self.anim.key or ""
            moving_head = ("graze_start" in key or "graze_end" in key) and not self.anim.done
            if not moving_head:
                self._play("graze" if self.state == "graze" else "alert", fps=4 if self.state == "graze" else 6,
                           loop=self.state == "graze")
            if self.timer <= 0:
                if self.state == "startled":
                    self._bolt()
                elif self.state == "graze":
                    self.state, self.timer = "look", self.rng.uniform(2.0, 4.0)
                    self._play("graze_end", fps=5, loop=False)
                else:
                    self._next()
            self.anim.update(dt)
            return
        if not self.route:
            if self.leaving:
                self.alive = False
                return
            self.state, self.timer = "graze", self.rng.uniform(8, 16)
            self._play("graze_start", fps=5, loop=False)
            return
        tx, ty = self.route[0]
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        speed = self.BOUND if self.fleeing else self.WALK
        step = min(dist, speed * dt)
        if dist > 0.01:
            self.x += dx / dist * step
            self.y += dy / dist * step
            if abs(dx) > 1.0:
                self.facing = 1 if dx > 0 else -1
        if dist - step < 0.5:
            self.route.pop(0)
        gait = "bound" if self.fleeing else "walk"
        self._play(gait, stride=deer_art.STRIDES[gait])
        self.anim.update(dt, step)

    def _next(self):
        """After looking about: graze again, or move on."""
        self.bouts -= 1
        if self.bouts > 0:
            self.state, self.timer = "graze", self.rng.uniform(8, 16)
            self._play("graze_start", fps=5, loop=False)
        else:
            self.leaving = True
            self.state = "walk"
            self.route = list(self.after or []) + [(self.exit_x, (self.after or [(0, self.y)])[-1][1])]

    def sprite(self):
        return self.anim.frame, deer_art.ANCHOR, False

    def shadow(self):
        return 22.0, 4.2, 70, -1


# ==========================================================================
# Pond visitors

class Heron(Entity):
    """A grey heron: it glides in to the bank and stands like a post,
    leans out over the water, strikes, now and then swallows a fish, and
    flaps away slowly when it has had enough (or the cat comes close)."""

    kind = "heron"
    watch_only = True
    watch_distance = 90.0

    def __init__(self, world):
        rng = world.rng
        self.rng = rng
        self.lib = art()["heron"]
        spots = bank_points(world.terrain)
        cat = world.cat
        spots = [s for s in spots if math.hypot(s[0] - cat.x, s[1] - cat.y) > 90] or spots
        self.spot = rng.choice(spots) if spots else None
        side = rng.choice((-1, 1))
        start_x = -40.0 if side < 0 else world.width + 40.0
        super().__init__(world, start_x, self.spot[1] - 30 if self.spot else 0.0)
        self.z = 70.0
        self.state = "fly_in"
        self.timer = 0.0
        self.rounds = rng.randint(3, 5)
        self.facing = self.spot[2] if self.spot else 1     # toward the water
        self.flight_facing = 1 if side < 0 else -1

    @property
    def ok(self):
        return self.spot is not None

    @property
    def airborne(self):
        return self.z > 3.0

    @property
    def hidden(self):
        return self.x < -30 or self.x > self.world.width + 30

    def interest(self, cat):
        return 0.0 if self.airborne else 0.9

    def _play(self, name, facing, **kw):
        key = f"{name}_{'right' if facing > 0 else 'left'}"
        self.anim.play(key, self.lib[key], **kw)

    def update(self, dt):
        world = self.world
        rng = self.rng
        cat = world.cat
        if self.state == "fly_in":
            tx, ty = self.spot[0], self.spot[1]
            dx, dy = tx - self.x, ty - self.y
            d = math.hypot(dx, dy)
            step = min(d, 42.0 * dt)
            if d > 0.01:
                self.x += dx / d * step
                self.y += dy / d * step
                self.flight_facing = 1 if dx > 0 else -1
            self.z = max(0.0, min(self.z, d * 0.55))
            self._play("glide" if d < 60 else "fly", self.flight_facing, fps=7)
            if d < 0.6:
                self.z = 0.0
                self.state, self.timer = "stand", rng.uniform(5, 10)
            self.anim.update(dt)
            return
        if self.state == "leave":
            self.x += self.flight_facing * 46.0 * dt
            self.z = min(80.0, self.z + 24.0 * dt)
            self._play("fly", self.flight_facing, fps=6)
            self.anim.update(dt)
            if self.hidden:
                self.alive = False
            return
        d = self.distance_to(cat)
        if cat.posture != "sleep" and (d < 45 or (d < 80 and _cat_speed(cat) > 20)):
            self._leave()
            return
        self.timer -= dt
        if self.state == "stand":
            self._play("stand", self.facing, fps=1.5)
            if self.timer <= 0:
                self.state, self.timer = "hunt", rng.uniform(8, 18)
        elif self.state == "hunt":
            self._play("hunt", self.facing, fps=5, loop=False)
            if self.timer <= 0:
                self.state, self.timer = "strike", 0.9
                self._play("strike", self.facing, fps=8, loop=False, restart=True)
        elif self.state == "strike":
            if self.timer <= 0.5 and not getattr(self, "_splashed", False):
                self._splashed = True
                bx = self.x + self.facing * 18
                world.water.ripple(bx, self.y + 1)
                world.particles.splash(bx, self.y + 1)
            if self.timer <= 0:
                self._splashed = False
                if rng.random() < 0.4:
                    self.state, self.timer = "swallow", 1.6
                    self._play("swallow", self.facing, fps=5, loop=False, restart=True)
                else:
                    self._next_round()
        elif self.state == "swallow":
            if self.timer <= 0:
                self._next_round()
        self.anim.update(dt)

    def _next_round(self):
        self.rounds -= 1
        if self.rounds <= 0:
            self._leave()
        else:
            self.state, self.timer = "stand", self.rng.uniform(4, 9)

    def _leave(self):
        self.state = "leave"
        self.flight_facing = -1 if self.x < self.world.width / 2 else 1
        self.z = max(self.z, 1.0)

    def sprite(self):
        return self.anim.frame, pond_art.HERON_ANCHOR, False

    def shadow(self):
        k = 1.0 / (1.0 + self.z * 0.012)
        return 10.0 * k, 2.6 * k, int(70 * k)


class Duck(Entity):
    """A mallard hen leading her ducklings to the pond in a line: they
    swim in her wake, she up-ends now and then to feed, and in the end she
    leads them off again."""

    kind = "duck"
    watch_only = True
    watch_distance = 70.0
    WALK = 11.0
    SWIM = 7.0

    def __init__(self, world, brood=4):
        rng = world.rng
        self.rng = rng
        self.lib = art()["ducks"]
        t = world.terrain
        side = rng.choice((-1, 1))
        drinks = [tuple(s.approach) for s in t.spots["drink"]] or None
        self.route, self.after = None, None
        banks = [(x - 6 * w, y) for x, y, w in bank_points(t) if t.walkable(x - 6 * w, y)]
        for mids, keep_off in ((drinks, 90.0), (drinks, 50.0), (banks, 50.0)):
            if mids and self.route is None:
                self.route, self.after = plan_crossing(world, side, mids=mids, keep_off=keep_off)
        start = (-20.0 if side < 0 else world.width + 20.0, self.route[0][1] if self.route else 0.0)
        super().__init__(world, *start)
        self.exit_x = world.width + 20.0 if side < 0 else -20.0
        self.facing = 1 if side < 0 else -1
        self.state = "walk_in"
        self.timer = 0.0
        self.trail = [(self.x, self.y)]       # breadcrumbs the ducklings follow
        self.swim_for = rng.uniform(120, 240)
        self.target = None
        self.ducklings = []
        if self.route:
            for i in range(brood):
                d = Duckling(world, self, i)
                self.ducklings.append(d)

    @property
    def ok(self):
        return self.route is not None

    @property
    def on_water(self):
        return self.world.terrain.is_water(self.x, self.y)

    @property
    def hidden(self):
        return self.x < -15 or self.x > self.world.width + 15

    def interest(self, cat):
        return 0.0 if self.hidden else 0.8

    def _play(self, name, **kw):
        key = f"duck_{name}_{'right' if self.facing > 0 else 'left'}"
        self.anim.play(key, self.lib[key], **kw)

    def _move_to(self, tx, ty, speed, dt):
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy)
        step = min(d, speed * dt)
        if d > 0.01:
            self.x += dx / d * step
            self.y += dy / d * step
            if abs(dx) > 0.3:
                self.facing = 1 if dx > 0 else -1
        last = self.trail[-1]
        if math.hypot(self.x - last[0], self.y - last[1]) > 1.0:
            self.trail.append((self.x, self.y))
            del self.trail[:-200]
        return d - step < 0.4, step

    def _water_point(self, near=None):
        pond = self.world.terrain.pond
        cells = pond.open_cells
        for _ in range(20):
            x, y = cells[self.rng.randrange(len(cells))]
            if near is None or math.hypot(x - near[0], y - near[1]) < 40:
                if all(self.world.terrain.is_water(x + dx, y + dy) for dx, dy in ((-6, 0), (6, 0), (0, -3), (0, 3))):
                    return float(x), float(y)
        return float(pond.cx), float(pond.cy)

    def update(self, dt):
        world = self.world
        rng = self.rng
        if self.state in ("walk_in", "walk_out"):
            if not self.route:
                if self.state == "walk_out":
                    self.alive = False
                    return
                self.state = "enter"
                self.target = self._water_point(near=(self.x, self.y))
                return
            arrived, step = self._move_to(*self.route[0], self.WALK, dt)
            if arrived:
                self.route.pop(0)
            self._play("walk", stride=3.0)
            self.anim.update(dt, step)
            return
        if self.state in ("enter", "swim"):
            self.swim_for -= dt
            if self.timer > 0:              # up-ended, feeding
                self.timer -= dt
                self._play("upend", fps=4, loop=False)
                self.anim.update(dt)
                return
            arrived, step = self._move_to(*self.target, self.SWIM if self.on_water else self.WALK, dt)
            self._play("swim" if self.on_water else "walk", fps=4)
            self.anim.update(dt, step)
            if self.on_water:
                self.state = "swim"
                if rng.random() < dt * 0.6:
                    world.water.ripple(self.x - self.facing * 4, self.y, small=True)
            if arrived:
                if self.swim_for <= 0:
                    self.state = "leave_water"
                    spot = self.after[0] if self.after else (self.exit_x, self.y)
                    self.target = spot
                elif rng.random() < 0.3:
                    self.timer = rng.uniform(2.0, 4.0)
                else:
                    self.target = self._water_point()
            return
        if self.state == "leave_water":
            arrived, step = self._move_to(*self.target, self.SWIM if self.on_water else self.WALK, dt)
            self._play("swim" if self.on_water else "walk", fps=4)
            self.anim.update(dt, step)
            if arrived:
                self.state = "walk_out"
                self.route = list(self.after or []) + [(self.exit_x, self.y)]

    def sprite(self):
        return self.anim.frame, pond_art.DUCK_ANCHOR, False

    def shadow(self):
        return None if self.on_water else (5.0, 1.4, 60)


class Duckling(Entity):
    kind = "duckling"

    def __init__(self, world, hen, place):
        super().__init__(world, hen.x, hen.y)
        self.hen = hen
        self.place = place            # 0 = right behind her
        self.lib = hen.lib
        self.facing = hen.facing
        self.bob = world.rng.random() * 6

    def update(self, dt):
        hen = self.hen
        if not hen.alive and (self.x < -10 or self.x > self.world.width + 10):
            self.alive = False
            return
        # Follow the breadcrumbs a little way behind, in line.
        gap = 9 + self.place * 7
        trail = hen.trail
        if hen.state == "walk_out" and hen.hidden:
            gap = 0                       # she's through the hedge: hurry after her
        idx = max(0, len(trail) - 1 - gap)
        tx, ty = trail[idx]
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy)
        speed = max(4.0, d * 3.0)
        step = min(d, speed * dt)
        if d > 0.01:
            self.x += dx / d * step
            self.y += dy / d * step
            if abs(dx) > 0.2:
                self.facing = 1 if dx > 0 else -1
        on_water = self.world.terrain.is_water(self.x, self.y)
        name = "swim" if on_water else ("walk" if step > 0.01 else "stand")
        key = f"duckling_{name}_{'right' if self.facing > 0 else 'left'}"
        self.anim.play(key, self.lib[key], fps=6 if name != "walk" else None, stride=2.0 if name == "walk" else None)
        self.anim.update(dt, step)
        leaving = hen.state == "walk_out"
        if leaving and (self.x < -10 or self.x > self.world.width + 10):
            self.alive = False

    def sprite(self):
        return self.anim.frame, pond_art.DUCK_ANCHOR, False

    def shadow(self):
        return None if self.world.terrain.is_water(self.x, self.y) else (2.4, 0.8, 50)


class Gift(Entity):
    """Something Mochi brought and left by the bowl for you.  It stays
    until the bowl is next filled."""

    kind = "gift"

    def __init__(self, world, x, y, what):
        super().__init__(world, x, y)
        self.what = what
        self.frame = art()["gifts"][what]
        self.fill_seen = world.bowl_fill

    def update(self, dt):
        world = self.world
        if world.bowl_fill > self.fill_seen + 0.3:
            self.alive = False         # someone came out with dinner, and took it in
        self.fill_seen = min(self.fill_seen, world.bowl_fill)

    def sprite(self):
        w, h = self.frame.get_size()
        return self.frame, (w // 2, h - 1), False

    def shadow(self):
        return 2.0, 0.7, 50
