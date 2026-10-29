"""Testing mode: the meadow on a clock of its own, and nothing remembered."""
import datetime
import os
import tempfile
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat.app import App, parse_args
from habitat.testing import PACES, TestClock, badge
from tests.support import TEST_PLACE
from tests.test_app import key


def make(*extra):
    return App(parse_args(["--size", "640x400", "--seed", "3", "--date", "2027-03-20", "--time", "09:00", *extra]))


class Testing(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.folder.name, "journal.json")
        self.old = os.environ.get("MEADOW_JOURNAL")
        os.environ["MEADOW_JOURNAL"] = self.path

    def tearDown(self):
        if self.old is None:
            os.environ.pop("MEADOW_JOURNAL", None)
        else:
            os.environ["MEADOW_JOURNAL"] = self.old
        self.folder.cleanup()

    def real_meadow(self):
        """A meadow that has been run for real: a cat and a layout kept."""
        app = make()
        app._save_session()
        with open(self.path) as f:
            return app, f.read()

    def test_x_puts_the_meadow_on_its_own_clock_and_back(self):
        app, _ = self.real_meadow()
        real_clock, name = app.clock, app.personality.name
        app.handle(key(pygame.K_x))
        self.assertIsNotNone(app.testing)
        self.assertIsInstance(app.clock, TestClock)
        self.assertIsNone(app.journal.path, "a scratch journal, never saved")
        self.assertEqual(app.world.cat.name, name, "the same Mochi")
        app.handle(key(pygame.K_x))
        self.assertIsNone(app.testing)
        self.assertIs(app.clock, real_clock)
        self.assertEqual(app.journal.path, self.path)

    def test_nothing_reaches_the_real_journal(self):
        _, before = self.real_meadow()
        app = make()
        app.handle(key(pygame.K_x))
        for k in (pygame.K_t, pygame.K_t, pygame.K_RIGHT, pygame.K_RIGHTBRACKET, pygame.K_n):
            app.handle(key(k))
        for _ in range(90):
            app.world.update(1 / 30)
        app.personality.feel(0.5)
        app.personality.save()
        app.world.marks.save()
        app.world.places.save()
        app.journal.note("meadow_seed", 12345)
        with open(self.path) as f:
            self.assertEqual(f.read(), before)

    def test_a_new_meadow_while_testing_is_only_for_testing(self):
        app, _ = self.real_meadow()
        seed = app.seed
        app.handle(key(pygame.K_x))
        app.handle(key(pygame.K_n))
        self.assertNotEqual(app.seed, seed)
        app.handle(key(pygame.K_x))
        self.assertEqual(app.seed, seed)
        self.assertEqual(app.world.seed, seed)

    def test_started_in_testing_mode_with_no_journal_yet_it_makes_none(self):
        app = make("--testing")
        for _ in range(30):
            app.world.update(1 / 30)
        self.assertFalse(os.path.exists(self.path))
        app.handle(key(pygame.K_x))            # leaving: now the real cat is met, and kept
        self.assertTrue(os.path.exists(self.path))

    def test_captions_show_afresh(self):
        self.real_meadow()
        app = make("--testing")
        self.assertNotIn("done", app.journal.notes)

    def test_t_steps_through_the_paces(self):
        app = make("--testing")
        seen = []
        for _ in PACES:
            app.handle(key(pygame.K_t))
            seen.append((app.clock.speed, app.clock.days_per_second))
        self.assertEqual(seen, [(speed, days) for _, speed, days in PACES[1:] + PACES[:1]])
        self.assertEqual(app.pace_name, PACES[0][0])

    def test_at_its_fastest_the_days_go_by_and_the_hour_holds(self):
        clock = TestClock(datetime.datetime(2027, 4, 1, 12, 0), place=TEST_PLACE, utc_offset=3)
        clock.set_pace(86400.0, 1.0)
        for _ in range(92):                     # three seconds (and a frame or two over)
            clock.update(1 / 30)
        self.assertEqual(clock.moment.date(), datetime.date(2027, 4, 4))
        self.assertEqual((clock.moment.hour, clock.moment.minute), (12, 0))

    def test_arrows_jump_an_hour_or_a_day(self):
        app = make("--testing")
        t0 = app.clock.moment
        app.handle(key(pygame.K_RIGHT))
        app.handle(key(pygame.K_UP))
        app.handle(key(pygame.K_UP))
        app.handle(key(pygame.K_DOWN))
        self.assertEqual(app.clock.moment - t0, datetime.timedelta(days=1, hours=1))
        app.handle(key(pygame.K_LEFT))
        self.assertEqual(app.clock.moment - t0, datetime.timedelta(hours=1))

    def test_brackets_go_from_one_step_of_a_story_to_the_next(self):
        app = make("--testing")
        stages = []
        for _ in range(6):
            app.handle(key(pygame.K_RIGHTBRACKET))
            app.world.update(1 / 30)
            stories = app.world.stories
            stages.append((app.clock.moment, stories.nest_stage and stories.nest_stage.name,
                           stories.frog_stage and stories.frog_stage.name))
        moments = [m for m, *_ in stages]
        self.assertEqual(moments, sorted(moments))
        self.assertTrue(any(nest or frogs for _, nest, frogs in stages), stages)
        back = app.clock.moment
        app.handle(key(pygame.K_LEFTBRACKET))
        self.assertLess(app.clock.moment, back)

    def test_a_jump_into_summer_leaves_no_winter_behind(self):
        app = make("--testing", "--date", "2027-01-15")
        env = app.world.env
        env.snow_cover, env.ice, env.frost = 1.0, 1.0, 1.0
        app.jump(datetime.timedelta(days=170), "On")
        self.assertEqual((env.snow_cover, env.ice, env.frost), (0.0, 0.0, 0.0))
        self.assertEqual(env.season, "summer")

    def test_the_badge_says_so(self):
        app = make("--testing")
        lines = badge(app.clock, app.pace_name, app.world.stories)
        self.assertIn("TESTING MODE", lines[0])
        self.assertIn("Sat 20 Mar 2027", lines[1])
        app.hud.draw_testing(app.screen, lines)
        app.renderer.draw(app.world)
        before = pygame.surfarray.array3d(app.screen).copy()
        app.hud.draw_testing(app.screen, lines)
        self.assertFalse((pygame.surfarray.array3d(app.screen) == before).all())


if __name__ == "__main__":
    unittest.main()
