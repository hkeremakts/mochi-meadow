"""Natural randomness: the right shape of chance for each kind of thing.

Nature isn't uniform.  Different things vary in different ways:

    durations           log-normal      mostly typical, now and then much longer
    times and amounts   normal          evenly either side of the usual, clipped
    waits for arrivals  exponential     mostly short gaps, sometimes a long lull
    two kinds of thing  mixture         a catnap or a deep sleep; a shower or a soaking
    getting bored       Weibull         the longer it's gone on, the likelier it ends
    proportions         beta            between 0 and 1, bunched near a usual value
    counts              Poisson         how many ducklings, sparrows, fireflies
    rare extremes       Pareto          a very occasional huge flock (always capped)
    time of day         von Mises       smooth peaks on the 24-hour clock, no switches
    clustered arrivals  Hawkes          one flock makes another likelier soon
    smooth wandering    Ornstein-Uhlenbeck   wind, rain intensity: drift and return

Settings describe a value with a *spec*; ``sample`` turns a spec into a
number.  The forms (all take optional ``min`` and ``max``):

    7                                       always 7
    [4, 10]                                 uniform between 4 and 10
    { typical = 20, spread = 0.6 }          log-normal: median 20, spread in log units
    { mean = 7.5, sd = 0.25 }               normal
    { mean_wait = 120 }                     exponential
    { scale = 40, shape = 2.2 }             Weibull (shape > 1: boredom builds)
    { a = 8, b = 1.5 }                      beta
    { poisson = 4.5 }                       Poisson count
    { pareto = 2.5, scale = 3 }             Pareto (heavy tail; set a max!)
    { mix = [ { weight = 0.7, ... }, ... ] }   a mixture of any of the above

``spread_scale`` (from the day's character) widens or narrows the normal
and log-normal spreads: some days are steadier than others.
"""

import datetime
import math
import random

SPEC_KEYS = ("typical", "mean", "mean_wait", "scale", "shape", "a", "poisson", "pareto", "mix")


def is_spec(value):
    """Is ``value`` something ``sample`` understands?"""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, list):
        return len(value) == 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)
    if isinstance(value, dict):
        if "mix" in value:
            parts = value["mix"]
            return isinstance(parts, list) and bool(parts) and all(
                isinstance(p, dict) and is_spec({k: v for k, v in p.items() if k != "weight"}) for p in parts)
        return any(k in value for k in SPEC_KEYS)
    return False


def _clip(x, spec):
    lo, hi = spec.get("min"), spec.get("max")
    if lo is not None:
        x = max(lo, x)
    if hi is not None:
        x = min(hi, x)
    return x


def sample(rng, spec, spread_scale=1.0):
    """One value drawn according to ``spec`` (see the module docstring)."""
    if isinstance(spec, (int, float)) and not isinstance(spec, bool):
        return spec
    if isinstance(spec, list):
        return rng.uniform(spec[0], spec[1])
    if "mix" in spec:
        parts = spec["mix"]
        r = rng.uniform(0, sum(p.get("weight", 1.0) for p in parts))
        for p in parts:
            r -= p.get("weight", 1.0)
            if r <= 0:
                break
        inner = {k: v for k, v in p.items() if k != "weight"}
        return _clip(sample(rng, inner, spread_scale), spec)
    if "typical" in spec:
        return _clip(lognormal(rng, spec["typical"], spec.get("spread", 0.5) * spread_scale), spec)
    if "mean_wait" in spec:
        return _clip(rng.expovariate(1.0 / spec["mean_wait"]), spec)
    if "sd" in spec and "mean" in spec:
        return _clip(rng.gauss(spec["mean"], spec["sd"] * spread_scale), spec)
    if "shape" in spec and "scale" in spec and "pareto" not in spec:
        return _clip(rng.weibullvariate(spec["scale"], spec["shape"]), spec)
    if "a" in spec and "b" in spec:
        return _clip(rng.betavariate(spec["a"], spec["b"]), spec)
    if "poisson" in spec:
        return _clip(poisson(rng, spec["poisson"]), spec)
    if "pareto" in spec:
        return _clip(spec.get("scale", 1.0) * rng.paretovariate(spec["pareto"]), spec)
    raise ValueError(f"not a chance spec: {spec!r}")


def count(rng, spec, spread_scale=1.0):
    """``sample`` rounded to a whole number."""
    return int(round(sample(rng, spec, spread_scale)))


def lognormal(rng, typical, spread):
    """``typical`` is the median; ``spread`` the standard deviation of the
    logarithm (0.3 = fairly steady, 0.7 = wild)."""
    return typical * math.exp(rng.gauss(0.0, spread))


def poisson(rng, mean):
    """Knuth's method: fine for the small means used here."""
    if mean <= 0:
        return 0
    limit, k, p = math.exp(-mean), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


# --------------------------------------------------------------------------
# Time of day

def peak(hour, centre, width):
    """A smooth bump on the 24-hour clock (von Mises), 1 at ``centre`` and
    falling away with ``width`` (hours, roughly one standard deviation).
    It wraps past midnight: a peak at 23:00 is high at 01:00 too."""
    theta = (hour - centre) / 24.0 * 2 * math.pi
    kappa = 1.0 / (width / 24.0 * 2 * math.pi) ** 2
    return math.exp(kappa * (math.cos(theta) - 1.0))


def peaks(hour, spec):
    """``spec`` is one peak ``{ peak = 20.5, width = 1.0 }`` or a list of
    them (dawn and dusk); the strongest wins."""
    if isinstance(spec, dict):
        spec = [spec]
    return max(p.get("height", 1.0) * peak(hour, p["peak"], p["width"]) for p in spec)


def around(rng, mean, kappa):
    """An angle (radians) scattered around ``mean`` (von Mises)."""
    return rng.vonmisesvariate(mean, kappa)


# --------------------------------------------------------------------------
# Processes in time

class Hawkes:
    """Arrivals that cluster.  A steady background rate, and each arrival
    raises the rate for a while (``excite`` extra per second, fading with
    ``memory`` seconds), so busy spells and quiet spells come naturally."""

    def __init__(self, rng, mean_wait, excite=0.0, memory=300.0):
        self.rng = rng
        self.base = 1.0 / mean_wait
        self.excite = excite
        self.memory = memory
        self.extra = 0.0

    @property
    def rate(self):
        return self.base + self.extra

    def step(self, dt, scale=1.0):
        """Advance; True if something arrives now.  ``scale`` multiplies the
        rate (a busy day, or 0 when nothing can come)."""
        self.extra *= math.exp(-dt / self.memory)
        if self.rng.random() < self.rate * scale * dt:
            self.extra += self.excite
            return True
        return False


class Drift:
    """A value that wanders smoothly and keeps returning to its usual level
    (Ornstein-Uhlenbeck): ``sd`` is how far it strays, ``timescale`` how
    slowly it moves."""

    def __init__(self, rng, mean=0.0, sd=1.0, timescale=60.0, value=None):
        self.rng = rng
        self.mean, self.sd, self.timescale = mean, sd, timescale
        self.value = mean if value is None else value

    def step(self, dt):
        k = min(1.0, dt / self.timescale)
        self.value += (self.mean - self.value) * k + self.sd * math.sqrt(2.0 * k) * self.rng.gauss(0.0, 1.0)
        return self.value


# --------------------------------------------------------------------------
# A day's character

class Day:
    """Each day has its own temper, decided at the start of it and the same
    however often the meadow restarts that day:

        volatility  how changeable the weather is (weather spells last
                    ``1 / volatility`` times as long)
        busyness    how lively the wildlife is
        energy      how much get-up-and-go Mochi has
        spread      how wild the day's randomness is (scales every spread)
    """

    def __init__(self, seed, spec):
        self.seed = seed
        self.spec = spec
        self.date = None
        self.volatility = self.busyness = self.energy = self.spread = 1.0
        self.prevailing = 1.0     # the side the wind mostly comes from

    def update(self, date):
        if date == self.date:
            return False
        self.date = date
        ordinal = date.toordinal() if isinstance(date, datetime.date) else int(date)
        rng = random.Random(ordinal * 1009 + self.seed * 7919)
        s = self.spec
        self.volatility = sample(rng, s["volatility"])
        self.busyness = sample(rng, s["busyness"])
        self.energy = sample(rng, s["energy"])
        self.spread = sample(rng, s["spread"])
        self.prevailing = rng.choice((-1.0, 1.0))
        return True

    def describe(self):
        weather = "changeable" if self.volatility > 1.25 else "settled" if self.volatility < 0.8 else "ordinary"
        life = "lively" if self.busyness > 1.2 else "quiet" if self.busyness < 0.83 else "usual"
        mochi = "full of beans" if self.energy > 1.08 else "sleepy" if self.energy < 0.92 else "herself"
        article = "an" if weather[0] in "aeiou" else "a"
        return f"{article} {weather} day, {life} wildlife, Mochi {mochi}"
