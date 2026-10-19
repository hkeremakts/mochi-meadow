"""The application shell: keys, screensaver exit, scripted runs."""
import os
import tempfile
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat.app import App, parse_args


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0)


def motion(dx, dy):
    return pygame.event.Event(pygame.MOUSEMOTION, rel=(dx, dy), pos=(100, 100), buttons=(0, 0, 0))


def make(*extra):
    return App(parse_args(["--size", "640x400", "--seed", "3", "--time", "12:00", *extra]))


class Lite(unittest.TestCase):
    def test_the_lite_zoom_is_always_even(self):
        from habitat.app import even_zoom
        for h in (600, 800, 982, 1080, 1440, 1964, 2160):
            self.assertEqual(even_zoom(h) % 2, 0, h)

    def test_without_a_gpu_renderer_it_falls_back_to_full_drawing(self):
        app = make("--lite")           # the dummy video driver has no renderer
        self.assertFalse(app.lite)
        self.assertGreater(app.renderer.S, 0)

    def test_a_screensaver_runs_at_the_saver_frame_rate(self):
        from habitat.app import SAVER_FPS
        self.assertEqual(make("--screensaver").fps, SAVER_FPS)
        self.assertEqual(make("--screensaver", "--fps", "24").fps, 24)


class Keys(unittest.TestCase):
    def test_t_cycles_time_lapse(self):
        app = make()
        app.handle(key(pygame.K_t))
        self.assertEqual(app.clock.speed, 60)
        app.handle(key(pygame.K_t))
        self.assertEqual(app.clock.speed, 600)
        app.handle(key(pygame.K_t))
        self.assertEqual(app.clock.speed, 1)

    def test_w_moves_to_the_next_weather(self):
        app = make()
        before = app.world.env.weather.state
        app.handle(key(pygame.K_w))
        self.assertNotEqual(app.world.env.weather.state, before)

    def test_n_grows_a_new_meadow(self):
        app = make()
        old_world, old_seed = app.world, app.seed
        app.handle(key(pygame.K_n))
        self.assertIsNot(app.world, old_world)
        self.assertNotEqual(app.seed, old_seed)

    def test_i_toggles_the_info_panel(self):
        app = make()
        app.handle(key(pygame.K_i))
        self.assertTrue(app.show_info)

    def test_escape_quits(self):
        app = make()
        app.handle(key(pygame.K_ESCAPE))
        self.assertFalse(app.running)


class Screensaver(unittest.TestCase):
    def test_input_during_the_grace_period_is_ignored(self):
        app = make("--screensaver")
        app.elapsed = 0.5
        app.handle(motion(20, 0))
        app.handle(key(pygame.K_a))
        self.assertTrue(app.running)

    def test_a_jittery_mouse_does_not_end_it(self):
        app = make("--screensaver")
        app.elapsed = 5.0
        app.handle(motion(1, -1))
        self.assertTrue(app.running)

    def test_moving_the_mouse_ends_it(self):
        app = make("--screensaver")
        app.elapsed = 5.0
        app.handle(motion(25, 4))
        self.assertFalse(app.running)

    def test_any_key_ends_it(self):
        app = make("--screensaver")
        app.elapsed = 5.0
        app.handle(key(pygame.K_SPACE))
        self.assertFalse(app.running)


class ScriptedRun(unittest.TestCase):
    def setUp(self):
        # Start from a fresh display: SDL's dummy driver keeps fullscreen
        # state from the screensaver tests otherwise.
        pygame.display.quit()
        pygame.display.init()

    def test_runs_a_number_of_frames_and_saves_the_last(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "shot.png")
            app = make("--frames", "30", "--screenshot", path, "--info")
            app.run()
            self.assertTrue(os.path.exists(path))
            pygame.init()
            self.assertEqual(pygame.image.load(path).get_size(), (640, 400))


if __name__ == "__main__":
    unittest.main()
