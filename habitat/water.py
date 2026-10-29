"""Life on the pond surface: sun glints, ripples, fish (and the odd jump),
night reflections."""

import math

import pygame


class WaterFX:
    def __init__(self, world):
        self.world = world
        self.sparkles = []   # [x, y, age, life, length]
        self.ripples = []    # [x, y, age, life, max_radius]
        self.fish = []
        self.stars = []      # [x, y, phase]
        self.jumps = []      # [x, y, dx, age]: a fish in mid-leap
        self._sparkle_debt = 0.0
        self._plop_timer = 0.0
        pond = world.terrain.pond
        if pond is not None and len(pond.open_cells):
            rng = world.rng
            for _ in range(rng.randint(1, 2)):
                self.fish.append(Fish(world, pond))
            for _ in range(max(3, len(pond.open_cells) // 350)):
                x, y = pond.open_cells[rng.randrange(len(pond.open_cells))]
                self.stars.append([int(x), int(y), rng.random() * 6.28])

    def ripple(self, x, y, small=False):
        if len(self.ripples) > 60 or self.world.env.frozen:      # nothing ripples on ice
            return
        rng = self.world.rng
        if small:
            self.ripples.append([x, y, 0.0, rng.uniform(0.5, 0.8), rng.uniform(2.0, 3.5)])
        else:
            self.ripples.append([x, y, 0.0, rng.uniform(1.4, 2.0), rng.uniform(5.0, 8.0)])

    def update(self, dt):
        pond = self.world.terrain.pond
        if pond is None or not len(pond.open_cells):
            return
        env = self.world.env
        rng = self.world.rng
        glint = env.sun * (1.0 - 0.8 * env.weather.cloud) * (1.0 - env.rain) * (0.2 if env.frozen else 1.0)
        self._sparkle_debt += dt * glint * len(pond.open_cells) / 260.0
        while self._sparkle_debt >= 1.0:
            self._sparkle_debt -= 1.0
            x, y = pond.open_cells[rng.randrange(len(pond.open_cells))]
            self.sparkles.append([float(x), float(y), 0.0, rng.uniform(0.5, 1.6), rng.choice((1, 2, 2, 3))])
        drift = env.wind.drift * 0.08
        for s in self.sparkles:
            s[2] += dt
            s[0] += drift * dt
        self.sparkles = [s for s in self.sparkles if s[2] < s[3]]

        for rp in self.ripples:
            rp[2] += dt
        self.ripples = [rp for rp in self.ripples if rp[2] < rp[3]]

        # Now and then something rises in the pond; sometimes a fish leaps.
        self._plop_timer -= dt
        if self._plop_timer <= 0 and not env.frozen:
            self._plop_timer = rng.uniform(14, 45)
            if env.rain < 0.3:
                if self.fish and env.sun > 0.15 and rng.random() < 0.35:
                    self._leap(rng.choice(self.fish))
                else:
                    x, y = pond.open_cells[rng.randrange(len(pond.open_cells))]
                    self.ripple(float(x), float(y))
        for j in self.jumps:
            j[3] += dt
            if j[3] >= JUMP_TIME and len(j) == 4:
                self.ripple(j[0] + j[2], j[1])
                self.world.particles.splash(j[0] + j[2], j[1])
                j.append(True)
        self.jumps = [j for j in self.jumps if j[3] < JUMP_TIME]
        for f in self.fish:
            f.update(dt)

    def _leap(self, fish):
        dx = 9.0 if math.cos(fish.heading) >= 0 else -9.0
        if not self.world.terrain.is_water(fish.x + dx, fish.y):
            dx = -dx
            if not self.world.terrain.is_water(fish.x + dx, fish.y):
                return
        self.ripple(fish.x, fish.y)
        self.world.particles.splash(fish.x, fish.y)
        self.jumps.append([fish.x, fish.y, dx, 0.0])

    def draw(self, r):
        pond = self.world.terrain.pond
        if pond is None:
            return
        if not self.world.env.frozen:       # under the ice, the fish are out of sight
            for f in self.fish:
                f.draw(r)
        stories = getattr(self.world, "stories", None)
        if stories is not None and stories.pond is not None:
            stories.pond.draw(r)            # frogspawn and tadpoles
        for flock in self.world.overhead:
            reflection = getattr(flock, "draw_reflection", None)
            if reflection is not None:
                reflection(r)               # storks and geese, high over the meadow
        for x, y, dx, age, *_ in self.jumps:
            f = min(1.0, age / JUMP_TIME)
            z = 7.0 * 4 * f * (1 - f)
            px = x + dx * f
            back = -1 if dx > 0 else 1
            tail_dy = 1 if f < 0.5 else -1                 # nose up, then nose down
            r.blit_px(r.dot((196, 208, 212), 255, 2, 1), px - 1, y - z)
            r.blit_px(r.dot((150, 166, 176), 255, 1, 1), px - 1 + back * 2, y - z + tail_dy)
        for x, y, age, life, length in self.sparkles:
            alpha = int(230 * math.sin(math.pi * age / life))
            if alpha > 16:
                r.blit_px(r.dot((214, 240, 244), alpha, length, 1), x, y)
        for x, y, age, life, radius in self.ripples:
            t = age / life
            rad = 1.0 + (radius - 1.0) * t
            alpha = int(200 * (1.0 - t))
            if alpha > 12:
                r.blit_px(r.ring(int(round(rad)), alpha), x - round(rad), y - round(rad * 0.5))

    def moon_spot(self):
        """Where the moon's reflection sits on the pond: it drifts across the
        water as the moon crosses the sky."""
        return self.sky_spot(self.world.env.sky.moon_az)

    def sky_spot(self, azimuth):
        """Where something in the sky at ``azimuth`` shows in the pond."""
        pond = self.world.terrain.pond
        a = math.radians(azimuth)
        for scale in (0.45, 0.3, 0.15, 0.0):
            x = pond.cx - math.sin(a) * pond.rx * scale
            y = pond.cy + math.cos(a) * pond.ry * scale * 0.6
            if all(self.world.terrain.is_water(x + dx, y + dy) for dx, dy in ((-5, 0), (5, 0), (0, -3), (0, 3))):
                return x, y
        return pond.cx, pond.cy

    def draw_moon(self, r):
        env = self.world.env
        sky = env.sky
        if sky.moon_alt <= 2 or env.sun > 0.3 or sky.moon_lit < 0.04:
            return
        clarity = (1.0 - env.weather.cloud) ** 1.5 * (1.0 - env.sun / 0.3) * min(1.0, sky.moon_alt / 10)
        if clarity < 0.05:
            return
        x, y = self.moon_spot()
        if self.world.terrain.behind_crown(x, y):
            return
        t = self.world.time
        # Ripples break the reflection into wobbling rows.
        rough = 0.4 + env.wind.strength + env.rain * 2
        level = int(clarity * 7) / 7
        img = moon_image(sky.moon_age, level, r.S, int(sky.eclipse * 4 + 0.5))
        for row in range(img.get_height() // r.S):
            shift = round(math.sin(t * 2.3 + row * 1.7) * rough * 0.7)
            area = (0, row * r.S, img.get_width(), r.S)
            r.screen.blit(img, (round((x - 3 + shift) * r.S), round((y - 3 + row) * r.S)), area,
                          special_flags=pygame.BLEND_ADD)

    def draw_venus(self, r):
        """The evening (or morning) star: the brightest point in the pond,
        steady where the stars twinkle, broken a little by ripples."""
        env = self.world.env
        sky = env.sky
        if not sky.venus_shows or env.weather.cloud > 0.6 or env.frozen:
            return
        clarity = (1.0 - env.weather.cloud / 0.6) * min(1.0, (-4 - sky.sun_alt) / 4) * min(1.0, sky.venus_alt / 8)
        x, y = self.sky_spot(sky.venus_az)
        x += 6
        if self.world.terrain.behind_crown(x, y):
            return
        wobble = round(math.sin(self.world.time * 2.1) * (env.wind.strength + env.rain * 2) * 0.6)
        alpha = int(255 * clarity)
        if alpha > 12:
            r.blit_px(r.dot((255, 246, 222), alpha, 2, 1), x + wobble, y, add=True)
            r.blit_px(r.dot((255, 246, 222), alpha // 3, 1, 1), x + wobble, y - 1, add=True)

    def draw_glow(self, r):
        """Stars, Venus and the moon mirrored in the water on clear nights
        (after lighting)."""
        env = self.world.env
        if self.world.terrain.pond is not None:
            self.draw_moon(r)
            self.draw_venus(r)
        if not self.stars or env.sun > 0.15 or env.weather.cloud > 0.55:
            return
        clarity = (1.0 - env.sun / 0.15) * (1.0 - env.weather.cloud / 0.55)
        t = self.world.time
        crown = self.world.terrain.behind_crown
        for x, y, phase in self.stars:
            if crown(x, y):
                continue
            tw = 0.55 + 0.45 * math.sin(t * 1.7 + phase)
            alpha = int(170 * tw * clarity)
            if alpha > 10:
                r.blit_px(r.dot((200, 210, 255), alpha, 1, 1), x, y, add=True)


JUMP_TIME = 0.6
MOON_RADIUS = 3
_MOONS = {}


def moon_image(age, level, S, shadow=0):
    """The moon's disc as the pond mirrors it, lit side and all: a pixel
    disc with the terminator cut for the phase, at zoom ``S``.  Additive
    colours.  ``shadow`` (0..4) is a lunar eclipse: the earth's shadow
    dims the moon and turns it copper."""
    key = (round(age * 32) % 32, level, S, shadow)
    hit = _MOONS.get(key)
    if hit is None:
        rad = MOON_RADIUS
        size = rad * 2 + 1
        small = pygame.Surface((size, size))
        small.fill((0, 0, 0))
        c = math.cos(2 * math.pi * key[0] / 32)
        waxing = key[0] < 16
        e = shadow / 4
        silver, copper = (150, 156, 150), (96, 40, 24)
        bright = tuple(int((s + (c - s) * e) * level) for s, c in zip(silver, copper))
        dim = (int(26 * level), int(30 * level), int(40 * level))
        for py in range(size):
            for px in range(size):
                u, v = (px - rad) / (rad + 0.5), (py - rad) / (rad + 0.5)
                if u * u + v * v > 1.0:
                    continue
                edge = c * math.sqrt(max(0.0, 1 - v * v))
                lit = u > edge if waxing else u < -edge
                small.set_at((px, py), bright if lit else dim)
        hit = pygame.transform.scale(small, (size * S, size * S))
        _MOONS[key] = hit
    return hit


class Fish:
    """A dark shape gliding under the surface."""

    def __init__(self, world, pond):
        self.world = world
        self.pond = pond
        rng = world.rng
        x, y = pond.open_cells[rng.randrange(len(pond.open_cells))]
        self.x, self.y = float(x), float(y)
        self.heading = rng.uniform(0, 2 * math.pi)
        self.speed = rng.uniform(3, 7)
        self.turn = 0.0

    def update(self, dt):
        rng = self.world.rng
        terrain = self.world.terrain
        if rng.random() < dt * 0.5:
            self.turn = rng.uniform(-1.2, 1.2)
        self.heading += self.turn * dt
        nx = self.x + math.cos(self.heading) * self.speed * dt
        ny = self.y + math.sin(self.heading) * self.speed * dt * 0.6
        ahead_x = nx + math.cos(self.heading) * 6
        ahead_y = ny + math.sin(self.heading) * 3
        if terrain.is_water(ahead_x, ahead_y) and terrain.is_water(nx, ny):
            self.x, self.y = nx, ny
        else:
            self.heading += math.pi * rng.uniform(0.6, 1.4)

    def draw(self, r):
        length = 4 if abs(math.cos(self.heading)) > 0.5 else 2
        height = 1 if length == 4 else 3
        r.blit_px(r.dot((18, 38, 52), 110, length, height), self.x - length / 2, self.y - height / 2)
