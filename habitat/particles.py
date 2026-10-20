"""Short-lived bits of motion: rain, splashes, dust, leaves, petals, pollen,
feathers.  Coordinates are art pixels; ``z`` is height above the ground."""

import math

from .util import clamp

LEAF_COLORS = [(96, 150, 62), (128, 170, 70), (186, 170, 74), (170, 118, 56)]
AUTUMN_LEAF_COLORS = [(196, 96, 44), (214, 146, 58), (168, 62, 38), (222, 180, 74), (150, 104, 50)]
PETAL_COLORS = [(240, 226, 236), (236, 170, 200), (250, 240, 200)]


class Particle:
    __slots__ = ("kind", "x", "y", "z", "vx", "vy", "vz", "age", "life", "color", "size", "seed")

    def __init__(self, kind, x, y, z=0.0, vx=0.0, vy=0.0, vz=0.0, life=1.0, color=(255, 255, 255), size=1, seed=0.0):
        self.kind = kind
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.age = 0.0
        self.life = life
        self.color = color
        self.size = size
        self.seed = seed


class Particles:
    MAX = 900

    def __init__(self, world):
        self.world = world
        self.items = []
        self._rain_debt = 0.0
        self._leaf_debt = 0.0
        self._pollen_debt = 0.0
        self._fall_debt = 0.0

    # --- emitters -------------------------------------------------------

    def _add(self, p):
        if len(self.items) < self.MAX:
            self.items.append(p)

    def dust(self, x, y, count=4, spread=4.0, color=(150, 136, 104)):
        rng = self.world.rng
        for _ in range(count):
            self._add(Particle("dust", x + rng.uniform(-spread, spread), y + rng.uniform(-1.5, 1.5),
                               z=rng.uniform(0, 2), vx=rng.uniform(-10, 10), vz=rng.uniform(4, 12),
                               life=rng.uniform(0.35, 0.7), color=color, size=rng.choice((1, 1, 2))))

    def splash(self, x, y):
        self._add(Particle("splash", x, y, life=0.22))

    def feathers(self, x, y, z, count=3):
        rng = self.world.rng
        for _ in range(count):
            self._add(Particle("feather", x + rng.uniform(-3, 3), y + rng.uniform(-2, 2), z=z + rng.uniform(2, 8),
                               vx=rng.uniform(-12, 12), vz=rng.uniform(2, 10), life=rng.uniform(2.5, 4.0),
                               color=rng.choice(((170, 170, 180), (130, 132, 146), (210, 210, 214))),
                               seed=rng.random() * 6.28))

    def leaf(self, x, y, z, autumn=None):
        rng = self.world.rng
        if autumn is None:
            autumn = self.world.env.season == "autumn"
        colors = AUTUMN_LEAF_COLORS if autumn else LEAF_COLORS
        self._add(Particle("leaf", x, y, z=z, vx=rng.uniform(-4, 4), vy=rng.uniform(-2, 4), vz=-rng.uniform(3, 8),
                           life=rng.uniform(7.0, 12.0), color=rng.choice(colors),
                           size=rng.choice((1, 2, 2)), seed=rng.random() * 6.28))

    def seed(self, x, y, z, direction):
        """A dandelion seed sailing across the meadow."""
        rng = self.world.rng
        self._add(Particle("seed", x, y, z=z, vx=direction * rng.uniform(5, 9), vy=rng.uniform(-1, 1),
                           life=rng.uniform(50, 80), seed=rng.random() * 6.28))

    def petal(self, x, y, z):
        rng = self.world.rng
        self._add(Particle("petal", x, y, z=z, vx=rng.uniform(-3, 3), vy=rng.uniform(-1, 2), vz=-rng.uniform(2, 5),
                           life=rng.uniform(5.0, 9.0), color=rng.choice(PETAL_COLORS), seed=rng.random() * 6.28))

    # --- simulation -----------------------------------------------------

    def update(self, dt):
        world = self.world
        env = world.env
        rng = world.rng
        w, h = world.width, world.height
        area = w * h / 230000.0

        # Rain: each drop falls from height onto a ground point.  In the
        # cold it comes down as snow: fewer flakes, falling slowly.
        rain = env.rain
        if rain > 0.02 and env.snowing:
            self._rain_debt += dt * rain * 160 * area
            while self._rain_debt >= 1.0:
                self._rain_debt -= 1.0
                self._add(Particle("snow", rng.uniform(-30, w + 30), rng.uniform(0, h + 30),
                                   z=rng.uniform(40, 90), vx=rng.uniform(-3, 3), vz=-rng.uniform(14, 22),
                                   life=9.0, size=rng.choice((1, 1, 1, 2)), seed=rng.random() * 6.28))
        elif rain > 0.02:
            # Drops thin out much faster than the rain eases: a drizzle is a
            # sprinkle of fine, slow drops, a downpour a curtain.
            self._rain_debt += dt * rain ** 2.2 * 950 * area
            fine = rain < 0.5
            while self._rain_debt >= 1.0:
                self._rain_debt -= 1.0
                speed = rng.uniform(160, 200) if fine else rng.uniform(260, 320)
                self._add(Particle("rain", rng.uniform(-10, w + 10), rng.uniform(0, h + 30),
                                   z=rng.uniform(70, 110), vz=-speed, life=2.0, size=1 if fine else 2))
        # Wind carries leaves across the meadow.
        wind = env.wind
        if wind.strength > 0.35:
            self._leaf_debt += dt * (wind.strength - 0.35) * 2.2 * area
            while self._leaf_debt >= 1.0:
                self._leaf_debt -= 1.0
                x = -6 if wind.direction > 0 else w + 6
                if rng.random() < 0.7:
                    self.leaf(x, rng.uniform(0, h), rng.uniform(25, 60))
                else:
                    self.petal(x, rng.uniform(0, h), rng.uniform(15, 40))
        # Autumn: leaves let go of the shrubs even in still air.
        if env.season == "autumn" and world.terrain.bushes:
            self._fall_debt += dt * 0.05 * len(world.terrain.bushes) * (1.0 + 2.0 * wind.strength)
            while self._fall_debt >= 1.0:
                self._fall_debt -= 1.0
                b = rng.choice(world.terrain.bushes)
                self.leaf(b.x + rng.uniform(-b.rx, b.rx), b.y + rng.uniform(-1, 2), rng.uniform(8, 16), autumn=True)
        # Pollen motes catch the light on calm, sunny days.
        if env.sun > 0.6 and rain < 0.05 and wind.strength < 0.6:
            self._pollen_debt += dt * 1.6 * area * env.sun * (1.0 - env.weather.cloud)
            while self._pollen_debt >= 1.0:
                self._pollen_debt -= 1.0
                self._add(Particle("pollen", rng.uniform(0, w), rng.uniform(0, h), z=rng.uniform(6, 30),
                                   vx=rng.uniform(-2, 2), vz=rng.uniform(-1, 1.5), life=rng.uniform(4, 8),
                                   seed=rng.random() * 6.28))

        drift = wind.drift
        alive = []
        for p in self.items:
            p.age += dt
            if p.age >= p.life:
                continue
            k = p.kind
            if k == "rain":
                p.z += p.vz * dt
                if p.z <= 0 or (p.z < 30 and world.terrain.under_roof(p.x, p.y)):
                    if p.z > 0:
                        continue          # caught by the leaves
                    if world.terrain.is_water(p.x, p.y):
                        world.water.ripple(p.x, p.y, small=True)
                    elif rng.random() < (0.5 if p.size > 1 else 0.12):
                        self.splash(p.x, p.y)
                    continue
                p.x += drift * 0.35 * dt
            elif k == "snow":
                if p.z > 0:
                    sway = math.sin(p.age * 1.7 + p.seed)
                    p.x += (drift * 0.6 + p.vx + sway * 4.0) * dt
                    p.z += p.vz * dt
                    if p.z < 30 and world.terrain.under_roof(p.x, p.y):
                        continue                      # settles on the crown instead
                    if p.z <= 0:
                        p.z = 0.0
                        if world.terrain.is_water(p.x, p.y):
                            continue
                        p.life = p.age + 1.2   # rests a moment, then melts into the white
            elif k == "dust":
                p.x += p.vx * dt
                p.z += p.vz * dt
                p.vx *= math.exp(-3.0 * dt)
                p.vz *= math.exp(-2.0 * dt)
            elif k in ("leaf", "petal", "feather"):
                flutter = math.sin(p.age * 3.1 + p.seed)
                if p.z > 0:
                    p.x += (drift + p.vx + flutter * 6.0) * dt
                    p.y += (p.vy + flutter * 1.5) * dt
                    p.z = max(0.0, p.z + (p.vz + flutter * 2.0) * dt)
                elif wind.strength > 0.6 and k != "feather":
                    p.x += drift * 0.3 * dt  # skitter along the ground
                if p.x < -12 or p.x > w + 12:
                    continue
            elif k == "seed":
                p.x += (p.vx + drift * 0.8 + math.sin(p.age * 0.8 + p.seed) * 3.0) * dt
                p.y += (p.vy + math.sin(p.age * 0.5 + p.seed) * 1.5) * dt
                p.z = max(2.0, p.z + math.sin(p.age * 1.1 + p.seed) * 3.0 * dt)
                if p.x < -12 or p.x > w + 12:
                    continue
            elif k == "pollen":
                p.x += (p.vx + drift * 0.4 + math.sin(p.age * 1.3 + p.seed) * 2.0) * dt
                p.z += (p.vz + math.sin(p.age * 0.9 + p.seed) * 1.2) * dt
            alive.append(p)
        self.items = alive

    # --- drawing --------------------------------------------------------

    def draw(self, r):
        wind_slant = clamp(self.world.env.wind.drift / 26.0, -1.0, 1.0)
        streak = r.rain_streak(wind_slant)
        fine_streak = r.rain_streak(wind_slant, fine=True)
        for p in self.items:
            k = p.kind
            fade = 1.0 - p.age / p.life
            if k == "rain":
                if p.size > 1:
                    r.blit_px(streak, p.x, p.y - p.z - 7)
                else:
                    r.blit_px(fine_streak, p.x, p.y - p.z - 4)
            elif k == "splash":
                r.blit_px(r.splash_sprite(p.age / p.life), p.x - 1.5, p.y - 1)
            elif k == "snow":
                alpha = 235 if p.z > 0 else int(235 * min(1.0, (p.life - p.age) / 1.2))
                if alpha > 20:
                    r.blit_px(r.dot((240, 244, 252), alpha, p.size, p.size), p.x, p.y - p.z)
            elif k == "dust":
                r.blit_px(r.dot((176, 160, 128), int(150 * fade), p.size, p.size), p.x, p.y - p.z)
            elif k in ("leaf", "petal"):
                alpha = 255 if fade > 0.25 else int(255 * fade / 0.25)
                tumble = int((p.age * 4 + p.seed) % 2) if p.z > 0 else 0
                if k == "leaf" and p.size > 1:
                    w, h = (2, 1) if tumble == 0 else (1, 2)
                else:
                    w, h = 1, 1
                if p.z > 0:
                    r.blit_px(r.dot((20, 24, 30), 60, w, h), p.x + 1, p.y)
                r.blit_px(r.dot(p.color, alpha, w, h), p.x, p.y - p.z)
            elif k == "feather":
                alpha = 255 if fade > 0.3 else int(255 * fade / 0.3)
                r.blit_px(r.dot(p.color, alpha, 2, 1), p.x, p.y - p.z)
            elif k == "seed":
                alpha = int(235 * min(1.0, fade * 4))
                r.blit_px(r.dot((20, 24, 30), 40, 1, 1), p.x + 1, p.y)
                r.blit_px(r.dot((246, 246, 240), alpha, 1, 1), p.x, p.y - p.z)
                r.blit_px(r.dot((246, 246, 240), alpha // 3, 1, 1), p.x + 1, p.y - p.z - 1)
            elif k == "pollen":
                twinkle = 0.5 + 0.5 * math.sin(p.age * 5.0 + p.seed)
                alpha = int(200 * twinkle * min(1.0, fade * 3) * min(1.0, p.age * 2))
                if alpha > 20:
                    r.blit_px(r.dot((255, 246, 200), alpha, 1, 1), p.x, p.y - p.z)
