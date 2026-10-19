"""Shared test helpers."""
import datetime

from habitat.environment import Clock

# Tests run on one fixed spring day in Istanbul, so results don't depend on
# when or where they run.  On this day the real sun keeps close to the
# standard day (sunrise ~6:10, sunset ~20:00 local).
TEST_DATE = datetime.date(2026, 5, 1)
TEST_PLACE = (41.0, 29.0)
TEST_OFFSET = 3


def fixed_clock(hour=12.0, speed=1.0, date=TEST_DATE, place=TEST_PLACE):
    return Clock(hour, speed=speed, date=date, place=place, utc_offset=TEST_OFFSET)
