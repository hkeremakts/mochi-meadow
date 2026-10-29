"""Testing mode: the meadow fast-forwarded, on a clock of its own.

Switched on with X in a window (or ``--testing``), the meadow stops
following the wall clock and the real calendar and runs on its own clock,
and everything runs at the testing pace: Mochi, the creatures, the
weather, the events and the stories, not just the sun.

    T        the pace: real, ten times as fast, an hour a minute, a day in
             two minutes, or a day a second with the hour held still (the
             seasons sweep by without the light flickering day-night-day)
    arrows   an hour back or on (up, down), a day back or on (left, right)
    [ ]      back to the last step of a seasonal story, on to the next one
    X        back to the real clock

Fast-forwarding is done in short steps of meadow time, as many as a frame
can spare.  If that isn't enough for the pace (heavy rain, a busy meadow,
a slow computer), the clock alone jumps the rest of the way, so the day
still passes on time and the badge says how fast the meadow kept up.
Captions still last their usual real seconds, so they can be read.

Nothing is remembered.  Testing mode works on a scratch copy of the journal
(the same Mochi and the same meadow, but no notices given yet, so each
caption shows again), never saved; leaving throws the copy away and puts
the real clock and journal back, so a test run never changes the cat or
the saved meadow.  A badge at the top of the screen says it's on.
"""

import copy
import datetime
import time

from .environment import Clock
from .journal import Journal

# What T steps through in testing mode: (what it's called, how many times
# as fast as real time, whether the hour is held while whole days go by).
PACES = [
    ("real pace", 1.0, False),
    ("ten times as fast", 10.0, False),
    ("an hour a minute", 60.0, False),
    ("a day in two minutes", 720.0, False),
    ("a day a second, the hour held", 86400.0, True),
]
BUDGET = 0.014            # seconds of computing a frame may spend fast-forwarding
FINE_STEP = 0.05          # meadow seconds a step, up to an hour a minute...
COARSE_STEP = 0.1         # ...and faster (the longest step the meadow ever takes)
DAY_STEPS = 288           # a skipped day's weather and cold, played through in five-minute steps
# The hour to arrive at a story's next step, to see it happening.
GOOD_HOURS = {"nest": 10.0, "spawn": 11.0, "tadpoles": 13.0, "froglets": 19.5, "storks": 12.5, "geese": 8.5}


class TestClock(Clock):
    """A clock of its own, started where the real one was.  It runs at the
    meadow's own pace (fast-forwarding runs the meadow faster) and can be
    jumped."""

    def __init__(self, moment, place=None, utc_offset=None):
        hour = moment.hour + moment.minute / 60 + moment.second / 3600
        super().__init__(hour, date=moment.date(), place=place, utc_offset=utc_offset)

    def jump(self, delta):
        self.moment += delta
        self.sky.invalidate()
        self.sky.update(self.moment)


class FastForward:
    """Runs a meadow at the testing pace."""

    def __init__(self, custom=None):
        self.index = 0
        self.custom = custom      # a pace given with --speed, until T picks another
        self.kept_up = self.pace[1]   # how many times as fast the meadow itself ran, lately
        self._days = 0.0

    @property
    def pace(self):
        """(name, how many times as fast, hour held)."""
        if self.custom:
            return f"{self.custom:g} times as fast", float(self.custom), False
        return PACES[self.index]

    def next_pace(self):
        if self.custom:
            self.custom = None
            self.index = 0
        self.index = (self.index + 1) % len(PACES)
        self.kept_up = self.pace[1]
        self._days = 0.0
        return self.pace[0]

    @property
    def lagging(self):
        """The meadow is running slower than the pace (the clock makes up the rest)."""
        name, speed, held = self.pace
        return not held and self.kept_up < speed * 0.9

    def advance(self, world, clock, dt):
        """One frame: ``dt`` real seconds."""
        name, speed, held = self.pace
        if held:
            self._skip_days(world, dt)
            return
        if speed <= 1.0:
            world.update(dt)
            return
        want = dt * speed
        step = FINE_STEP if speed <= 60 else COARSE_STEP
        deadline = time.perf_counter() + BUDGET
        done = 0.0
        while done < want - 1e-9:
            s = min(step, want - done)
            world.update(s, real=dt * s / want)
            done += s
            if time.perf_counter() > deadline:
                break
        if done < want - 1e-9:
            clock.jump(datetime.timedelta(seconds=want - done))
        self.kept_up += (done / dt - self.kept_up) * 0.1

    def _skip_days(self, world, dt):
        """The hour held: the meadow lives at its own pace while whole days
        go by, a second each.  Each skipped day's weather and cold are
        played through, coarsely, so a snowy night leaves snow lying and a
        hard frost a frozen pond."""
        world.update(dt)
        self._days += dt
        env = world.env
        while self._days >= 1.0:
            self._days -= 1.0
            for _ in range(DAY_STEPS):
                env.update(86400.0 / DAY_STEPS)
            world.stories.timer = 0.0
            world._scenery_check = 0.0


def scratch_copy(journal):
    """A journal to test with: the same cat and meadow (and what has been
    seen, for the J page), but no notices given yet, and never saved."""
    out = Journal(None)
    out.since = journal.since
    out.seen = copy.deepcopy(journal.seen)
    out.notes = copy.deepcopy(journal.notes)
    for key in ("done", "last_session"):
        out.notes.pop(key, None)
    return out


def story_target(moment, days_ahead, story, stage):
    """When to arrive for a story's step that begins ``days_ahead`` from
    ``moment``: on its first day at an hour for seeing it, or the next day
    if that hour comes before it begins."""
    start = moment + datetime.timedelta(days=days_ahead)
    hour = GOOD_HOURS.get(stage, GOOD_HOURS.get(story.split()[0], 10.0))
    target = datetime.datetime.combine(start.date(), datetime.time()) + datetime.timedelta(hours=hour)
    if target < start:
        target += datetime.timedelta(days=1)
    return target


def badge(clock, fast, world):
    """The lines of the testing badge."""
    name, speed, held = fast.pace
    pace = name
    if fast.lagging:
        pace += f" (the meadow keeping up at {fast.kept_up:.0f} times)"
    env = world.env
    lines = [f"TESTING MODE  ·  its own clock  ·  {pace}",
             clock.moment.strftime("%a %d %b %Y   %H:%M").replace(" 0", " ")
             + f"   ·   {env.weather_name}, {env.temperature:.0f}°C"]
    season = world.stories.describe() if getattr(world, "stories", None) is not None else []
    if season:
        lines.append("  ·  ".join(season))
    lines.append("T pace   left/right a day   up/down an hour   [ ] story steps   X leave")
    return lines
