"""The clock follows the wall clock unless told otherwise."""
import datetime
import unittest

from habitat.environment import Clock


def hours(dt):
    return dt.hour + dt.minute / 60 + dt.second / 3600


class LiveClock(unittest.TestCase):
    def test_live_clock_reads_the_wall_clock_after_a_long_pause(self):
        # A laptop sleeps for an hour; the first frame after waking has its
        # dt capped, but the meadow must still show the real time.
        fake_now = [datetime.datetime(2026, 7, 1, 21, 0, 0)]
        clock = Clock(now=lambda: fake_now[0])
        fake_now[0] = datetime.datetime(2026, 7, 1, 22, 0, 0)
        clock.update(0.1)
        self.assertAlmostEqual(clock.hour, 22.0, places=3)

    def test_a_chosen_start_time_runs_on_its_own(self):
        fake_now = [datetime.datetime(2026, 7, 1, 9, 0, 0)]
        clock = Clock(start_hour=21.0, now=lambda: fake_now[0])
        clock.update(36.0)  # 36 s at 1x
        self.assertAlmostEqual(clock.hour, 21.01, places=3)

    def test_time_lapse_runs_fast_and_returning_to_live_resyncs(self):
        fake_now = [datetime.datetime(2026, 7, 1, 9, 0, 0)]
        clock = Clock(now=lambda: fake_now[0])
        clock.set_speed(600)
        clock.update(6.0)  # 6 s at 600x = one hour
        self.assertAlmostEqual(clock.hour, 10.0, places=3)
        clock.set_speed(1)
        clock.update(0.016)
        self.assertAlmostEqual(clock.hour, 9.0, places=3)


if __name__ == "__main__":
    unittest.main()
