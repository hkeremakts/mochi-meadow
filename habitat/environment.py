"""Time of day, weather, wind and cloud shadows."""

import datetime
import math
import random

import numpy as np
import pygame

from .chance import Day, Drift, around, sample
from .settings import SETTINGS
from .sky import Sky, mean_temperature
from .util import Noise1D, clamp, dither_mask, lerp_color, smoothstep, value_noise

# Ambient light as a multiply colour, by the sun's altitude in degrees.
# Mornings run cool and rosy, evenings warm and golden.  Night keeps
# enough light to make out the meadow (this is a screensaver, not a black
# screen) and brightens to silver under a high full moon.
MORNING = [
    (-18.0, None),
    (-12.0, (80, 80, 132)),
    (-6.0, (100, 88, 134)),
    (-2.0, (168, 124, 146)),
    (0.5, (206, 150, 148)),
    (4.0, (236, 196, 180)),
    (8.0, (248, 218, 194)),
    (16.0, (255, 250, 240)),
    (28.0, (255, 255, 255)),
]
EVENING = [
    (-18.0, None),
    (-10.0, (88, 86, 136)),
    (-6.0, (134, 104, 148)),
    (-2.5, (190, 124, 132)),
    (1.0, (234, 156, 128)),
    (5.0, (255, 214, 166)),
    (10.0, (255, 230, 196)),
    (20.0, (255, 247, 230)),
    (28.0, (255, 255, 255)),
]
NIGHT_DARK = (58, 66, 116)       # no moon
NIGHT_MOON = (96, 110, 156)      # a full moon high overhead


def night_color(moonlight):
    return lerp_color(NIGHT_DARK, NIGHT_MOON, clamp(moonlight, 0.0, 1.0))


def daylight_color(sun_alt, rising=True, moonlight=0.0):
    table = MORNING if rising else EVENING
    night = night_color(moonlight)
    if sun_alt <= table[0][0]:
        return night
    for (a0, c0), (a1, c1) in zip(table, table[1:]):
        if a0 <= sun_alt <= a1:
            t = (sun_alt - a0) / (a1 - a0)
            return lerp_color(c0 or night, c1, smoothstep(t))
    return table[-1][1]


def sun_level(sun_alt):
    """0 once the sun is 6 degrees down (civil dusk), 1 from 12 degrees up,
    eased in between."""
    return smoothstep((sun_alt + 6.0) / 18.0)


class Clock:
    """The local date and time, and the sky that goes with them.

    A clock started without an hour is *live*: it reads the wall clock every
    update, so the meadow shows the real time even after the computer has
    slept.  A chosen start time, or a time-lapse ``speed``, runs on its own;
    setting the speed back to 1 makes a live clock live again.

    ``hour`` is the real local hour (meals, the info panel).  ``between``
    asks about the *standard* hour, the real day mapped onto one fixed
    shape (see sky.py), so "dusk" means dusk in June and in December."""

    def __init__(self, start_hour=None, speed=1.0, now=datetime.datetime.now, date=None, place=None,
                 utc_offset=None):
        self._now = now
        self.started_live = start_hour is None and date is None
        if self.started_live:
            self.moment = now()
        else:
            day = date or now().date()
            hour = (start_hour if start_hour is not None else now().hour) % 24.0
            self.moment = datetime.datetime.combine(day, datetime.time()) + datetime.timedelta(hours=hour)
        self.speed = speed
        self.live = self.started_live and speed == 1
        self.sky = Sky(place, utc_offset)
        self.sky.update(self.moment)

    @property
    def hour(self):
        m = self.moment
        return m.hour + m.minute / 60 + (m.second + m.microsecond / 1e6) / 3600

    @property
    def date(self):
        return self.moment.date()

    def set_speed(self, speed):
        self.speed = speed
        self.live = self.started_live and speed == 1
        if self.live:
            self.moment = self._now()
            self.sky.invalidate()
            self.sky.update(self.moment)

    def update(self, dt):
        if self.live:
            self.moment = self._now()
        else:
            self.moment += datetime.timedelta(seconds=dt * self.speed)
        self.sky.update(self.moment)

    @property
    def label(self):
        minutes = int(self.hour * 60) % (24 * 60)
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    @property
    def sun(self):
        return sun_level(self.sky.sun_alt)

    @property
    def standard_hour(self):
        return self.sky.standard_hour

    def between(self, start, end):
        """True if the standard hour lies in [start, end), wrapping past
        midnight."""
        h = self.sky.standard_hour
        if start <= end:
            return start <= h < end
        return h >= start or h < end


# What each weather looks like, what tends to follow it, and how the
# seasons tilt that: all from the settings.
WEATHER_STATES = {name: dict(v) for name, v in SETTINGS["weather"]["states"].items()}
WEATHER_NEXT = {name: list(v.items()) for name, v in SETTINGS["weather"]["next"].items()}
SEASON_BIAS = {season: dict(v) for season, v in SETTINGS["weather"]["season_bias"].items()}
COLD = SETTINGS["cold"]

QUICK_BLEND = float(SETTINGS["weather"]["quick_blend"])   # seconds to ease into a weather chosen with W


class Weather:
    """Spells of weather.  Each spell lasts a time drawn for its kind (a
    rain may be a passing shower or an all-day soaking), shortened or
    lengthened by the day's volatility; its cloud cover varies a little
    from the kind's usual; and within it the rain and wind wander and
    return rather than holding still."""

    def __init__(self, rng, state="clear", locked=False, day=None):
        self.rng = rng
        self.day = day if day is not None else Day(0, SETTINGS["day"])
        self.state = state
        self.locked = locked
        self.spell = 0            # counts spells, so others can notice a change
        self.quick = 0.0          # seconds of fast blending left (after a key press)
        w = SETTINGS["weather"]
        wander = w["wander"]
        self.rain_wander = Drift(rng, 0.0, wander["rain_sd"], wander["rain_seconds"])
        self.wind_wander = Drift(rng, 0.0, wander["wind_sd"], wander["wind_seconds"])
        self._start_spell(state)
        self.cloud = self.target["cloud"]
        self.wind = self.target["wind"]
        self.rain = self.target["rain"]

    def _start_spell(self, state):
        rng = self.rng
        w = SETTINGS["weather"]
        spread = self.day.spread
        self.hold = sample(rng, w["hold_minutes"][state], spread) * 60.0 / self.day.volatility
        self.blend = sample(rng, w["blend"], spread)
        base = WEATHER_STATES[state]
        m = clamp(base["cloud"], 0.02, 0.98)
        c = w["cloud_steadiness"]
        self.target = dict(base, cloud=rng.betavariate(m * c, (1.0 - m) * c))
        self.spell += 1

    def force(self, state, locked=None):
        self.state = state
        self._start_spell(state)
        if locked is not None:
            self.locked = locked

    def cycle(self):
        """The next weather, now: asked for with a key, it arrives in a few
        seconds rather than drifting in over the better part of a minute."""
        names = list(WEATHER_STATES)
        self.force(names[(names.index(self.state) + 1) % len(names)])
        self.quick = QUICK_BLEND * 2

    def update(self, dt, season=None):
        if not self.locked:
            self.hold -= dt
            if self.hold <= 0:
                bias = SEASON_BIAS.get(season, {})
                options = [(name, w * bias.get(name, 1.0)) for name, w in WEATHER_NEXT[self.state]]
                total = sum(w for _, w in options)
                r = self.rng.uniform(0, total)
                for name, w in options:
                    r -= w
                    if r <= 0:
                        break
                self.force(name)
        target = self.target
        quick = self.quick > 0
        self.quick = max(0.0, self.quick - dt)
        k = 1.0 - math.exp(-dt * 3.0 / (QUICK_BLEND if quick else self.blend))
        gust = 1.0 + self.wind_wander.step(dt)
        heavier = 1.0 + self.rain_wander.step(dt)
        self.cloud += (target["cloud"] - self.cloud) * k
        self.wind += (clamp(target["wind"] * gust, 0.0, 1.0) - self.wind) * k
        # Rain arrives a little after the clouds and stops a little before.
        rain_target = clamp(target["rain"] * heavier, 0.0, 1.0) if (self.cloud > 0.7 or quick) else 0.0
        self.rain += (rain_target - self.rain) * k


class Wind:
    def __init__(self, rng):
        self.rng = rng
        self.gusts = Noise1D(rng)
        self.wobble = Noise1D(rng)
        self.direction = rng.choice((-1.0, 1.0))
        self.toward = self.direction
        self.t = rng.uniform(0, 100)
        self.strength = 0.2

    def veer(self, prevailing, scatter):
        """A new spell's wind: from around the day's prevailing side,
        scattered (von Mises), and always with some sideways push."""
        angle = around(self.rng, 0.0 if prevailing > 0 else math.pi, scatter)
        across = math.cos(angle)
        self.toward = math.copysign(max(0.35, abs(across)), across)

    def update(self, dt, base):
        self.t += dt
        self.direction += (self.toward - self.direction) * min(1.0, dt / 20.0)   # turns over a few seconds
        gust = self.gusts(self.t * 0.22)
        self.strength = base * (0.45 + 0.85 * gust)

    @property
    def drift(self):
        """Horizontal push on light things (leaves, butterflies), px/s."""
        return self.direction * self.strength * 26.0

    def sway(self, x, y, phase):
        """How far a plant at (x, y) leans, in [-1, 1].  Gusts travel across
        the meadow as waves; calm air leaves only a slow idle drift."""
        wave = math.sin(x * 0.05 - self.t * 2.4 * self.direction + y * 0.018)
        lean = self.direction * self.strength * (0.3 + 0.7 * (0.5 + 0.5 * wave))
        lean += 0.32 * math.sin(self.t * 0.9 + phase * 6.283) * (0.6 + self.wobble(self.t * 0.1 + phase * 20))
        return clamp(lean, -1.0, 1.0)


class CloudLayer:
    """Soft shadows of clouds drifting over the meadow (multiply surfaces)."""

    def __init__(self, rng, width, height):
        self.rng = rng
        self.width = width
        self.height = height
        self.shapes = [self._shape(rng) for _ in range(5)]
        self.clouds = []  # [x, y, shape, speed_factor]

    def _shape(self, rng):
        w = rng.randint(110, 230)
        h = int(w * rng.uniform(0.45, 0.62))
        nrng = np.random.default_rng(rng.randrange(1 << 30))
        n = value_noise(w, h, max(8, w // 6), nrng) * 0.65 + value_noise(w, h, max(4, w // 16), nrng) * 0.35
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        density = n * 1.25 - r
        d = dither_mask(h, w)
        core = density > 0.32
        inner = (density > 0.18) & ~core
        edge = (density > 0.04) & ~core & ~inner & (d < (density - 0.04) / 0.14)
        inner_edge = inner & (d < (density - 0.18) / 0.14)
        values = np.full((h, w), 255, dtype=np.uint8)
        values[edge] = 236
        values[inner] = 226
        values[inner_edge] = 214
        values[core] = 206
        rgb = np.dstack([values, values, values])
        return pygame.surfarray.make_surface(np.ascontiguousarray(rgb.swapaxes(0, 1)))

    def update(self, dt, cover, rain, wind):
        speed = 5.0 + wind.strength * 14.0
        direction = wind.direction
        for c in self.clouds:
            c[0] += direction * speed * c[3] * dt
        self.clouds = [c for c in self.clouds
                       if -c[2].get_width() - 10 < c[0] < self.width + 10]
        wanted = int(round(cover * (1.0 - rain) * 5.0))
        if len(self.clouds) < wanted and self.rng.random() < dt * 0.25:
            shape = self.rng.choice(self.shapes)
            x = -shape.get_width() if direction > 0 else self.width
            y = self.rng.uniform(-shape.get_height() * 0.4, self.height - shape.get_height() * 0.6)
            self.clouds.append([x, y, shape, self.rng.uniform(0.8, 1.2)])

    def seed_initial(self, cover, rain):
        """Start with clouds already over the meadow instead of an empty sky."""
        wanted = int(round(cover * (1.0 - rain) * 5.0))
        for _ in range(wanted):
            shape = self.rng.choice(self.shapes)
            x = self.rng.uniform(-shape.get_width() * 0.5, self.width - shape.get_width() * 0.5)
            y = self.rng.uniform(-shape.get_height() * 0.4, self.height - shape.get_height() * 0.6)
            self.clouds.append([x, y, shape, self.rng.uniform(0.8, 1.2)])


def _day_value(ordinal):
    """A fixed 0..1 value per calendar day: some days run warm, some cold."""
    return random.Random(ordinal * 7919 + 17).random()


class Environment:
    def __init__(self, rng, width, height, clock, weather_state="clear", weather_locked=False, seed=0):
        self.clock = clock
        self.day = Day(seed, SETTINGS["day"])
        self.day.update(clock.date)
        self.weather = Weather(rng, weather_state, weather_locked, self.day)
        self.wind = Wind(rng)
        self.wind.veer(self.day.prevailing, SETTINGS["weather"]["wind_scatter"])
        self.wind.direction = self.wind.toward
        self._spell = self.weather.spell
        self.clouds = CloudLayer(rng, width, height)
        self.clouds.seed_initial(self.weather.cloud, self.weather.rain)
        self.temperature = self._temperature()
        self.snow_cover = 0.0    # 0..1 of the ground under snow
        self.frost = 0.0         # 0..1 hoar frost on the grass
        if self.temperature < 0.5 and self.clock.sky.season == "winter" and rng.random() < 0.3:
            self.snow_cover = rng.uniform(0.4, 1.0)  # it snowed while nobody was watching

    @property
    def sky(self):
        return self.clock.sky

    @property
    def season(self):
        return self.clock.sky.season

    def _temperature(self):
        """Celsius: the season's mean, a day-to-day wobble, a warm
        afternoon and a cold small hours, damped by cloud."""
        date = self.clock.date
        lat = self.clock.sky.lat
        day = date.toordinal()
        f = smoothstep(self.clock.hour / 24.0)
        wobble = (_day_value(day) * (1 - f) + _day_value(day + 1) * f) * 6.0 - 3.0
        swing = 4.5 * (1.0 - 0.6 * self.weather.cloud)
        daily = swing * math.cos(2 * math.pi * (self.clock.hour - 15.0) / 24.0)
        return mean_temperature(date, lat) + wobble + daily - 2.0 * self.weather.rain

    def update(self, dt):
        self.clock.update(dt)
        self.day.update(self.clock.date)
        self.weather.update(dt, self.season)
        if self.weather.spell != self._spell:
            self._spell = self.weather.spell
            self.wind.veer(self.day.prevailing, SETTINGS["weather"]["wind_scatter"])
        self.wind.update(dt, self.weather.wind)
        self.clouds.update(dt, self.weather.cloud, self.weather.rain, self.wind)
        self.temperature = self._temperature()
        sim = dt * self.clock.speed
        t = self.temperature
        if self.snowing:
            self.snow_cover = min(1.0, self.snow_cover + sim * self.weather.rain / COLD["snow_settles"])
        elif self.snow_cover > 0:
            melt = max(0.0, t - 0.5) / COLD["snow_melts"] + self.sun * COLD["sun_melt"] * max(0.0, t + 2.0) / 3600.0
            if self.weather.rain > 0.05:
                melt *= COLD["rain_melt"]
            self.snow_cover = max(0.0, self.snow_cover - sim * melt)
        if t < COLD["frost_below"] and self.weather.cloud < 0.55 and self.sun < 0.3 and not self.snowing:
            self.frost = min(1.0, self.frost + sim / COLD["frost_forms"])
        elif self.frost > 0:
            self.frost = max(0.0, self.frost - sim * (0.2 + self.sun) * max(0.2, t) / COLD["frost_lifts"])

    @property
    def hour(self):
        return self.clock.hour

    @property
    def sun(self):
        return self.clock.sun

    @property
    def rain(self):
        """Precipitation, rain or snow."""
        return self.weather.rain

    @property
    def snowing(self):
        return self.weather.rain > 0.03 and self.temperature < COLD["snow_below"]

    @property
    def is_night(self):
        return self.clock.sun < 0.05

    @property
    def moonlight(self):
        return self.clock.sky.moonlight * (1.0 - 0.85 * self.weather.cloud)

    @property
    def weather_name(self):
        state = self.weather.state
        if self.snowing:
            return "Light snow" if state == "drizzle" else "Snow"
        return WEATHER_NAMES[state]

    def ambient(self):
        """Multiply colour for the whole scene: the sun's height, dimmed and
        greyed by cloud and rain; the moon lights the night."""
        sky = self.clock.sky
        r, g, b = daylight_color(sky.sun_alt, sky.rising, self.moonlight)
        cloud, rain = self.weather.cloud, self.weather.rain
        grey = (r + g + b) / 3.0
        sat = 1.0 - 0.3 * cloud - 0.25 * rain
        dim = 1.0 - 0.14 * cloud - 0.2 * rain
        if self.snow_cover > 0.2 and self.sun < 0.3:
            dim *= 1.0 + 0.12 * self.snow_cover   # snow holds the light at night
        r = (grey + (r - grey) * sat) * dim
        g = (grey + (g - grey) * sat) * dim
        b = (grey + (b - grey) * sat) * dim * (1.0 + 0.05 * rain)
        return (int(clamp(r, 0, 255)), int(clamp(g, 0, 255)), int(clamp(b, 0, 255)))


WEATHER_NAMES = {"clear": "Clear", "cloudy": "Cloudy", "windy": "Windy", "drizzle": "Drizzle", "rain": "Rain"}
