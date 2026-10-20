"""Window, input and the main loop."""

import argparse
import datetime
import os
import random
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from .config import ART_ROWS_TARGET, DEFAULT_WINDOW, FPS, MAX_ZOOM, MIN_ZOOM
from .environment import WEATHER_STATES, Clock
from .events import ALL, CAPTION_TIME, recap
from .journal import Journal, default_path
from .personality import Personality
from .hud import Hud
from .render import Renderer
from .sky import parse_place
from .world import World

TIME_SPEEDS = (1, 60, 600)
SAVER_FPS = 30            # slow, ambient motion needs no more, and it halves the work
CALM_FPS = 15             # ...and when nothing is moving fast, half that again
SAVE_EVERY = 300.0        # seconds between journal saves of the session
LITE_ZOOM = 2             # in lite mode the scene is drawn at this zoom, the GPU does the rest
SCREENSAVER_GRACE = 1.5   # seconds before input ends a screensaver session
RESIZE_SETTLE = 0.25      # rebuild once the window has stopped changing size
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pick_zoom(screen_height, override=None):
    if override:
        return max(1, int(override))
    return int(max(MIN_ZOOM, min(MAX_ZOOM, round(screen_height / ART_ROWS_TARGET))))


def even_zoom(screen_height):
    """The pixel zoom for the GPU-scaled mode: even, so drawing at zoom 2
    and letting the GPU double it up keeps every art pixel the same size."""
    return max(2, 2 * round(screen_height / ART_ROWS_TARGET / 2))


def parse_hour(text):
    if text is None:
        return None
    if ":" in text:
        h, m = text.split(":", 1)
        return int(h) + int(m) / 60.0
    return float(text)


def parse_date(text):
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a date: {text} (use YYYY-MM-DD)")


def parse_place_arg(text):
    try:
        return parse_place(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a latitude,longitude: {text}")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="A cat's meadow: a living pixel-art habitat to watch.")
    p.add_argument("--fullscreen", action="store_true", help="start fullscreen (toggle with F)")
    p.add_argument("--screensaver", action="store_true",
                   help="fullscreen, hidden cursor, and any key or mouse movement quits")
    p.add_argument("--time", dest="hour", metavar="HH:MM", help="start at this time of day (default: now)")
    p.add_argument("--date", type=parse_date, metavar="YYYY-MM-DD", help="pretend it is this date (season, moon)")
    p.add_argument("--place", type=parse_place_arg, metavar="LAT,LON",
                   help="where the sun and moon are worked out for (default: guessed from the time zone)")
    p.add_argument("--speed", type=float, default=1.0, help="time multiplier, e.g. 60 = one hour per minute")
    p.add_argument("--weather", choices=sorted(WEATHER_STATES), default="clear", help="starting weather")
    p.add_argument("--lock-weather", action="store_true", help="keep the starting weather")
    p.add_argument("--seed", type=int, help="meadow layout seed")
    p.add_argument("--zoom", type=int, help="pixel zoom (default: picked from window height)")
    p.add_argument("--size", metavar="WxH", help="window size")
    p.add_argument("--fps", type=int, help=f"frames per second (default: {FPS}, or {SAVER_FPS} as a screensaver)")
    p.add_argument("--lite", action="store_true",
                   help="draw small and let the graphics card scale it up: much less CPU (default as a screensaver)")
    p.add_argument("--full-render", action="store_true", help="as a screensaver, draw at full resolution anyway")
    p.add_argument("--info", action="store_true", help="show the info panel (toggle with I)")
    p.add_argument("--event", choices=sorted(ALL), metavar="NAME",
                   help="make an event happen right away: " + ", ".join(sorted(ALL)))
    p.add_argument("--no-journal", action="store_true",
                   help="don't remember anything between runs (a new cat and meadow each time)")
    p.add_argument("--name", help="what the cat is called (remembered)")
    p.add_argument("--debug-events", action="store_true", help="show event odds and timers (toggle with D)")
    p.add_argument("--frames", type=int, help=argparse.SUPPRESS)        # run N frames then exit
    p.add_argument("--screenshot", help=argparse.SUPPRESS)              # save the last frame here
    return p.parse_args(argv)


class App:
    def __init__(self, args):
        self.args = args
        pygame.init()
        pygame.display.set_caption("Meadow")
        self.screensaver = args.screensaver
        self.fps = args.fps or (SAVER_FPS if args.screensaver else FPS)
        self.adaptive = args.screensaver and not args.fps
        self.lite = args.lite or (args.screensaver and not args.full_render)
        self.fullscreen = args.fullscreen or args.screensaver
        self.windowed_size = self._initial_window_size(args.size)
        remembering = not (args.no_journal or args.frames)
        self.journal = Journal(default_path() if remembering else None)
        # Her meadow: the same layout every run, unless asked for another.
        stored = self.journal.notes.get("meadow_seed")
        self.seed = args.seed if args.seed is not None else (stored if stored is not None else random.randrange(1 << 30))
        if remembering and args.seed is None and stored is None:
            self.journal.note("meadow_seed", self.seed)
        if remembering:
            self.personality = Personality.from_journal(self.journal, args.name)
        else:
            self.personality = Personality.roll(random.Random(self.seed), args.name or "Mochi")
        self.clock = Clock(parse_hour(args.hour), speed=args.speed, date=args.date, place=args.place)
        self.speed_index = TIME_SPEEDS.index(int(args.speed)) if args.speed in TIME_SPEEDS else None
        self.screen = self._set_mode()
        self.world = None
        self.renderer = None
        self.hud = Hud(self.screen.get_height())
        self.show_info = args.info
        self.show_journal = False
        self.show_debug = args.debug_events
        if self.screensaver:
            self.hud.guide_time = 0.0
        self._build_world(args.weather, args.lock_weather)
        if args.event:
            self.world.events.force(args.event)
        if self.journal.path:
            line = recap(self.journal.notes.get("last_session"), self.world.cat.name, self.clock.moment)
            if line:
                self.world.say_later(10.0 if self.world.captions else 2.0, *line)
        self._saved_at = 0.0
        self.running = True
        self.paused_render = False
        self.pending_resize = None
        self.elapsed = 0.0

    # --- window ---------------------------------------------------------

    def _initial_window_size(self, text):
        if text:
            w, h = text.lower().split("x")
            return int(w), int(h)
        try:
            dw, dh = pygame.display.get_desktop_sizes()[0]
        except (pygame.error, IndexError):
            return DEFAULT_WINDOW
        return min(DEFAULT_WINDOW[0], int(dw * 0.85)), min(DEFAULT_WINDOW[1], int(dh * 0.85))

    def _set_mode(self):
        if self.lite:
            return self._set_lite_mode()
        if self.fullscreen:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            pygame.mouse.set_visible(False)
        else:
            screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
            pygame.mouse.set_visible(True)
        return screen

    def _set_lite_mode(self):
        """A small drawing surface the GPU scales to the screen (pygame's
        SCALED mode, nearest-neighbour, so pixels stay crisp)."""
        if self.fullscreen:
            try:
                size = pygame.display.get_desktop_sizes()[0]
            except (pygame.error, IndexError):
                size = DEFAULT_WINDOW
        else:
            size = self.windowed_size
        zoom = int(self.args.zoom) if self.args.zoom else even_zoom(size[1])
        self.lite_scale = max(1, zoom // LITE_ZOOM)
        logical = (-(-size[0] // zoom) * LITE_ZOOM, -(-size[1] // zoom) * LITE_ZOOM)
        flags = pygame.SCALED | (pygame.FULLSCREEN if self.fullscreen else 0)
        try:
            screen = pygame.display.set_mode(logical, flags)
        except pygame.error:
            # No GPU renderer here (a headless or very old system): draw
            # at full size instead.
            self.lite = False
            return self._set_mode()
        pygame.mouse.set_visible(not self.fullscreen)
        return screen

    def _build_world(self, weather=None, lock=None):
        w, h = self.screen.get_size()
        zoom = LITE_ZOOM if self.lite else pick_zoom(h, self.args.zoom)
        old = self.world
        if old is not None:
            weather = old.env.weather.state
            lock = old.env.weather.locked
        world = World(-(-w // zoom), -(-h // zoom), seed=self.seed, clock=self.clock,
                      weather=weather or "clear", weather_locked=bool(lock), journal=self.journal,
                      personality=self.personality)
        if old is not None:
            # Same cat, same day: carry the cat's state of mind across.
            for need in old.cat.needs.__slots__:
                setattr(world.cat.needs, need, getattr(old.cat.needs, need))
            weather_now = old.env.weather
            world.env.weather.cloud = weather_now.cloud
            world.env.weather.wind = weather_now.wind
            world.env.weather.rain = weather_now.rain
            world.env.weather.hold = weather_now.hold
            world.bowl_fill = old.bowl_fill
        self.world = world
        if self.renderer is None or self.renderer.S != zoom:
            self.renderer = Renderer(self.screen, zoom)
        else:
            self.renderer.clear_caches()
        self.renderer.bind(world, self.screen)
        self.hud.resize(h)

    def toggle_fullscreen(self):
        if self.lite:
            pygame.display.toggle_fullscreen()   # the GPU rescales; nothing to rebuild
            self.fullscreen = not self.fullscreen
            pygame.mouse.set_visible(not self.fullscreen)
            return
        if not self.fullscreen:
            self.windowed_size = self.screen.get_size()
        self.fullscreen = not self.fullscreen
        self.screen = self._set_mode()
        self._build_world()

    # --- input --------------------------------------------------------------

    def handle(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return
        if self.screensaver and self.elapsed > SCREENSAVER_GRACE:
            if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                self.running = False
                return
            if event.type == pygame.MOUSEMOTION and max(abs(event.rel[0]), abs(event.rel[1])) > 3:
                self.running = False
                return
        if event.type == pygame.KEYDOWN:
            key = event.key
            if key in (pygame.K_ESCAPE, pygame.K_q):
                self.running = False
            elif key in (pygame.K_f, pygame.K_F11):
                self.toggle_fullscreen()
            elif key == pygame.K_i:
                self.show_info = not self.show_info
            elif key == pygame.K_j:
                self.show_journal = not self.show_journal
            elif key == pygame.K_d:
                self.show_debug = not self.show_debug
            elif key in (pygame.K_h, pygame.K_SLASH):
                self.hud.show_guide()
            elif key == pygame.K_t:
                self.speed_index = 0 if self.speed_index is None else (self.speed_index + 1) % len(TIME_SPEEDS)
                self.clock.set_speed(TIME_SPEEDS[self.speed_index])
            elif key == pygame.K_w:
                self.world.env.weather.cycle()
            elif key == pygame.K_n:
                self.seed = random.randrange(1 << 30)
                if self.journal.path:
                    self.journal.note("meadow_seed", self.seed)
                self.world = None
                self._build_world("clear", False)
            elif key == pygame.K_s:
                self.save_screenshot()
        elif event.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED) and not self.fullscreen and not self.lite:
            self.pending_resize = 0.0
        elif event.type in (pygame.WINDOWMINIMIZED, pygame.WINDOWHIDDEN):
            self.paused_render = True
        elif event.type in (pygame.WINDOWRESTORED, pygame.WINDOWSHOWN, pygame.WINDOWEXPOSED):
            self.paused_render = False

    def save_screenshot(self, path=None):
        if path is None:
            folder = os.path.join(PROJECT_ROOT, "screenshots")
            os.makedirs(folder, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            path = os.path.join(folder, f"meadow-{stamp}.png")
        pygame.image.save(self.screen, path)
        return path

    # --- loop -----------------------------------------------------------

    def run(self):
        ticker = pygame.time.Clock()
        frames = 0
        while self.running:
            fps = 5 if self.paused_render else self.fps
            if self.adaptive and not self.args.frames and self.world.calm():
                fps = CALM_FPS
            dt = min(ticker.tick(fps) / 1000.0, 0.1)
            if self.args.frames:
                dt = 1.0 / self.fps  # deterministic steps for scripted runs
            self.elapsed += dt
            for event in pygame.event.get():
                self.handle(event)
            if self.pending_resize is not None:
                self.pending_resize += dt
                if self.pending_resize >= RESIZE_SETTLE:
                    self.pending_resize = None
                    self.screen = pygame.display.get_surface()
                    self._build_world()
            self.world.update(dt)
            self.hud.update(dt)
            if self.journal.path and self.elapsed - self._saved_at > SAVE_EVERY:
                self._save_session()
            if not self.paused_render:
                self.renderer.draw(self.world)
                self.hud.draw_captions(self.screen, self.world.captions, CAPTION_TIME)
                if self.show_info:
                    self.hud.draw_info(self.screen, self.world, self.clock.speed)
                if self.show_debug:
                    self.hud.draw_debug(self.screen, self.world)
                elif self.show_journal:
                    self.hud.draw_journal(self.screen, self.world.events)
                self.hud.draw_guide(self.screen)
                pygame.display.flip()
            frames += 1
            if self.args.frames and frames >= self.args.frames:
                break
        if self.args.screenshot:
            self.save_screenshot(self.args.screenshot)
        if self.journal.path:
            self._save_session()
        pygame.quit()

    def _save_session(self):
        """Keep this session's story for the next run's recap (and the cat's
        mood): now and then, in case the screensaver is simply killed."""
        self._saved_at = self.elapsed
        self.journal.notes["last_session"] = self.world.summary()
        self.personality.save()


def main(argv=None):
    App(parse_args(argv)).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
