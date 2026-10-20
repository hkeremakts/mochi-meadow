"""Tuning lives in one place, and a settings file of your own can change it."""
import os
import subprocess
import sys
import tempfile
import unittest

from habitat import settings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write(text):
    f = tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False)
    f.write(text)
    f.close()
    return f.name


class Defaults(unittest.TestCase):
    def test_the_defaults_are_the_values_the_meadow_was_tuned_with(self):
        d = settings.DEFAULTS
        self.assertEqual(d["weather"]["hold_minutes"]["clear"]["typical"], 25)
        self.assertEqual(d["meals"]["times"], [7.5, 18.0])
        self.assertEqual(d["events"]["tiers"]["rare"], 180)
        self.assertEqual(d["mochi"]["needs"]["energy_awake"], 720)

    def test_every_event_has_a_cooldown(self):
        from habitat.events import ROLLED
        cooldowns = settings.DEFAULTS["events"]["cooldown_minutes"]
        for e in ROLLED:
            self.assertIn(e.name, cooldowns)

    def test_weather_tables_cover_every_kind_of_weather(self):
        w = settings.DEFAULTS["weather"]
        kinds = set(w["states"])
        self.assertEqual(set(w["next"]), kinds)
        for follows in w["next"].values():
            self.assertLessEqual(set(follows), kinds)


class YourOwn(unittest.TestCase):
    def test_a_file_changes_only_what_it_names(self):
        path = write("[weather.hold_minutes]\nrain = { typical = 60, spread = 0.5 }\n[mochi.cooldowns]\nmeow = 30\n")
        try:
            s = settings.load(path, quiet=True)
        finally:
            os.unlink(path)
        self.assertEqual(s["weather"]["hold_minutes"]["rain"], {"typical": 60, "spread": 0.5})
        self.assertEqual(s["mochi"]["cooldowns"]["meow"], 30)
        self.assertEqual(s["weather"]["blend"], settings.DEFAULTS["weather"]["blend"])
        self.assertEqual(s["mochi"]["cooldowns"]["zoomies"], settings.DEFAULTS["mochi"]["cooldowns"]["zoomies"])

    def test_mistakes_are_ignored_not_fatal(self):
        path = write('[weather]\nquick_blend = "long"\nblend = "slow"\nfoo = 3\n[mochi]\nwalk_speed = 30\n')
        try:
            s = settings.load(path, quiet=True)
        finally:
            os.unlink(path)
        self.assertEqual(s["weather"]["quick_blend"], settings.DEFAULTS["weather"]["quick_blend"])
        self.assertEqual(s["weather"]["blend"], settings.DEFAULTS["weather"]["blend"])
        self.assertNotIn("foo", s["weather"])
        self.assertEqual(s["mochi"]["walk_speed"], 30)      # the good line still counts

    def test_a_typo_is_reported_not_taken(self):
        path = write("[mochi]\nwalk_sped = 30\n[events.cooldown_minutes]\n\"a new event\" = 5\n")
        try:
            s = settings.load(path, quiet=True)
        finally:
            os.unlink(path)
        self.assertNotIn("walk_sped", s["mochi"])
        self.assertEqual(s["events"]["cooldown_minutes"]["a new event"], 5)

    def test_a_broken_file_leaves_the_defaults(self):
        path = write("[weather\nhold = ")
        try:
            s = settings.load(path, quiet=True)
        finally:
            os.unlink(path)
        self.assertEqual(s, settings.DEFAULTS)

    def test_settings_reach_the_meadow(self):
        """--settings is read before the modules load their tuning."""
        path = write("[meals]\ntimes = [8.25, 19.0]\n")
        try:
            out = subprocess.run(
                [sys.executable, "-c",
                 "import sys; sys.argv=['main.py','--settings',sys.argv[1]]; exec(open('main.py').read().split('from habitat.app')[0]);"
                 "from habitat.config import MEAL_TIMES; print(MEAL_TIMES)", path],
                cwd=ROOT, capture_output=True, text=True, env=dict(os.environ, SDL_VIDEODRIVER="dummy"))
        finally:
            os.unlink(path)
        self.assertEqual(out.stdout.strip(), "(8.25, 19.0)", out.stderr)


if __name__ == "__main__":
    unittest.main()
