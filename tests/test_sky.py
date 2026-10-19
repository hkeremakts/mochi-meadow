"""The real sky: sun times, the moon, seasons, and the light they make."""
import datetime
import random
import unittest

from habitat.environment import Clock, Environment, daylight_color
from habitat.sky import DayShape, guess_place, moon_phase, parse_place, season_of

ISTANBUL = (41.0, 29.0)
UTC = datetime.timezone.utc


def hm(hours):
    return f"{int(hours):02d}:{int(round(hours % 1 * 60)):02d}"


class SunTimes(unittest.TestCase):
    def assertNear(self, hours, expected, minutes=6):
        h, m = (int(x) for x in expected.split(":"))
        self.assertLess(abs(hours - (h + m / 60)) * 60, minutes, f"{hm(hours)} vs {expected}")

    def test_istanbul_in_october(self):
        # Published times for 19 Oct 2026: sunrise 07:22, sunset 18:20.
        day = DayShape(datetime.date(2026, 10, 19), *ISTANBUL, 3)
        self.assertNear(day.sunrise, "07:22")
        self.assertNear(day.sunset, "18:20")

    def test_london_at_midsummer(self):
        # 21 Jun 2026 (BST): sunrise 04:43, sunset 21:21.
        day = DayShape(datetime.date(2026, 6, 21), 51.5, -0.1, 1)
        self.assertNear(day.sunrise, "04:43")
        self.assertNear(day.sunset, "21:21")

    def test_sydney_has_long_days_in_december(self):
        day = DayShape(datetime.date(2026, 12, 21), -33.9, 151.2, 11)
        self.assertGreater(day.sunset - day.sunrise, 14.0)

    def test_the_midnight_sun_still_gives_a_usable_day(self):
        day = DayShape(datetime.date(2026, 6, 21), 69.6, 18.9, 2)   # Tromso
        self.assertIsNone(day.sunrise)
        hours = [day.standard_hour(h) for h in range(24)]
        self.assertTrue(all(0 <= h < 24 for h in hours))


class StandardDay(unittest.TestCase):
    def test_a_december_evening_counts_as_dusk(self):
        clock = Clock(17.6, date=datetime.date(2026, 12, 21), place=ISTANBUL, utc_offset=3)
        self.assertTrue(clock.between(19.0, 21.0), clock.standard_hour)

    def test_a_june_evening_at_the_same_hour_is_still_afternoon(self):
        clock = Clock(17.6, date=datetime.date(2026, 6, 21), place=ISTANBUL, utc_offset=3)
        self.assertTrue(clock.between(14.0, 18.5), clock.standard_hour)

    def test_noon_maps_to_noon(self):
        day = DayShape(datetime.date(2026, 3, 20), *ISTANBUL, 2)
        self.assertAlmostEqual(day.standard_hour(day.noon), 12.8, places=3)

    def test_the_standard_hour_never_runs_backwards(self):
        day = DayShape(datetime.date(2026, 10, 19), *ISTANBUL, 3)
        hours = [day.standard_hour(i / 10) for i in range(int(day.anchors[0] * 10) + 1, 240)]
        steps = [(b - a) % 24 for a, b in zip(hours, hours[1:])]
        self.assertTrue(all(0 < s < 1 for s in steps))


class Moon(unittest.TestCase):
    def test_full_moon_on_26_october_2026(self):
        age, lit = moon_phase(datetime.datetime(2026, 10, 26, 4, 12, tzinfo=UTC))
        self.assertGreater(lit, 0.99)
        self.assertAlmostEqual(age, 0.5, delta=0.01)

    def test_new_moon_on_10_october_2026(self):
        _, lit = moon_phase(datetime.datetime(2026, 10, 10, 15, 50, tzinfo=UTC))
        self.assertLess(lit, 0.01)

    def test_a_full_moon_lights_the_night(self):
        dark = daylight_color(-40, moonlight=0.0)
        bright = daylight_color(-40, moonlight=1.0)
        self.assertGreater(sum(bright), sum(dark) + 60)


class Seasons(unittest.TestCase):
    def test_seasons_flip_between_hemispheres(self):
        d = datetime.date(2026, 7, 10)
        self.assertEqual(season_of(d, 41), "summer")
        self.assertEqual(season_of(d, -34), "winter")
        self.assertEqual(season_of(datetime.date(2026, 10, 19), 41), "autumn")

    def test_winter_is_colder_than_summer(self):
        def env(month):
            clock = Clock(14.0, date=datetime.date(2026, month, 15), place=ISTANBUL, utc_offset=3)
            return Environment(random.Random(1), 100, 80, clock).temperature
        self.assertLess(env(1), env(7) - 10)

    def test_cold_precipitation_falls_as_snow_and_settles(self):
        clock = Clock(9.0, date=datetime.date(2026, 1, 20), place=(60.2, 24.9), utc_offset=2)
        env = Environment(random.Random(1), 100, 80, clock, "rain", weather_locked=True)
        env.snow_cover = 0.0
        env.weather.rain = 0.85
        for _ in range(600):
            env.update(1.0)
        self.assertTrue(env.snowing)
        self.assertGreater(env.snow_cover, 0.3)
        self.assertIn("Snow", env.weather_name)


class Place(unittest.TestCase):
    def test_known_zone(self):
        self.assertEqual(guess_place("Europe/Istanbul"), ISTANBUL)

    def test_unknown_zone_uses_the_utc_offset(self):
        lat, lon = guess_place("Etc/Nowhere", utc_offset_hours=-5)
        self.assertEqual(lon, -75.0)
        self.assertGreater(lat, 0)

    def test_parse_place(self):
        self.assertEqual(parse_place("41.0,29.0"), ISTANBUL)
        with self.assertRaises(ValueError):
            parse_place("100,0")


if __name__ == "__main__":
    unittest.main()
