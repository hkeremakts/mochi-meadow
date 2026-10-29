"""Testing mode: the meadow on a clock of its own.

Switched on with X in a window (or ``--testing``), the meadow stops
following the wall clock and the real calendar, and runs on its own clock:

    T        its pace: the real one, an hour a minute, a day in two
             minutes, a week a minute, or a day a second with the hour
             held still (the seasons and the stories sweep by without the
             light flickering day-night-day)
    arrows   an hour back or on (up, down), a day back or on (left, right)
    [ ]      back to the last step of a seasonal story, on to the next one
    X        back to the real clock

The sun and the moon, the seasons and the stories all follow the testing
clock, so a whole day, a month of moons or a spring of nesting can be
watched in minutes.

Nothing is remembered.  Testing mode works on a scratch copy of the journal
(the same Mochi and the same meadow, but no notices given yet, so each
caption shows again), never saved; leaving throws the copy away and puts
the real clock and journal back, so a test run never changes the cat or
the saved meadow.  A badge at the top of the screen says it's on.
"""

import copy
import datetime

from .environment import Clock
from .journal import Journal

# What T steps through in testing mode: (what it's called, clock speed,
# days a second with the hour held).
PACES = [
    ("real pace", 1.0, 0.0),
    ("an hour a minute", 60.0, 0.0),
    ("a day in two minutes", 720.0, 0.0),
    ("a week a minute", 10080.0, 0.0),
    ("a day a second, the hour held", 86400.0, 1.0),
]
# The hour to arrive at a story's next step, to see it happening.
GOOD_HOURS = {"nest": 10.0, "spawn": 11.0, "tadpoles": 13.0, "froglets": 19.5, "storks": 12.5, "geese": 8.5}


class TestClock(Clock):
    """A clock of its own: any pace, jumps, and at its fastest whole days
    at a time with the hour held still."""

    def __init__(self, moment, place=None, utc_offset=None):
        hour = moment.hour + moment.minute / 60 + moment.second / 3600
        super().__init__(hour, date=moment.date(), place=place, utc_offset=utc_offset)
        self.days_per_second = 0.0
        self._days = 0.0

    def set_pace(self, speed, days_per_second=0.0):
        self.set_speed(speed)
        self.days_per_second = days_per_second
        self._days = 0.0

    def update(self, dt):
        if not self.days_per_second:
            super().update(dt)
            return
        self._days += dt * self.days_per_second
        whole = int(self._days)
        if whole:
            self._days -= whole
            self.moment += datetime.timedelta(days=whole)
        self.sky.update(self.moment)

    def jump(self, delta):
        self.moment += delta
        self.sky.invalidate()
        self.sky.update(self.moment)


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


def badge(clock, pace, stories):
    """The lines of the testing badge."""
    lines = [f"TESTING MODE  ·  its own clock  ·  {pace}",
             clock.moment.strftime("%a %d %b %Y   %H:%M").replace(" 0", " ")]
    season = stories.describe() if stories is not None else []
    if season:
        lines.append("  ·  ".join(season))
    lines.append("T pace   left/right a day   up/down an hour   [ ] story steps   X leave")
    return lines
