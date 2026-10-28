"""The whole meadow is drawn in one style: Mochi's storybook look carries
over to every creature (see the logbook, 2026-10-28)."""
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from habitat import bird_art, cat_art, critter_art, deer_art, fox_art, pond_art
from habitat.entities.wildlife import art
from tests.pixel_lint import orphans

pygame.init()
pygame.display.set_mode((64, 64))

# Each creature's palette, and the colours it may use for a single pixel on
# purpose (a nose, a beak, an eye, a wing bar, an outline's corner).
BIRD_DETAILS = (bird_art.OUT, bird_art.BAR, bird_art.NECK_G, bird_art.NECK_P, bird_art.FEET, bird_art.BEAK,
                bird_art.CERE, bird_art.EYE, bird_art.SHINE)
CREATURES = {
    "fox": (fox_art.PALETTE, (fox_art.OUT, fox_art.NOSE, fox_art.PUPIL, fox_art.SHINE, fox_art.IRIS)),
    "deer": (deer_art.PALETTE, (deer_art.OUT, deer_art.NOSE, deer_art.EYE, deer_art.SHINE, deer_art.HOOF)),
    "heron": (pond_art.HERON_PALETTE, (pond_art.H_OUT, pond_art.H_EYE, pond_art.H_PUPIL, pond_art.H_SHINE,
                                       pond_art.H_BILL)),
    "pigeon": (bird_art.PIGEON, BIRD_DETAILS),
    "sparrow": (bird_art.SPARROW, BIRD_DETAILS),
    "crow": (bird_art.CROW, BIRD_DETAILS),
    "frog": (critter_art.FROG, (1, critter_art.F_EYE, critter_art.F_SHINE, critter_art.F_SAC)),
    "hedgehog": (critter_art.HOG, (1, critter_art.H_EYE, critter_art.H_SHINE)),
    "snail": (critter_art.SNAIL, (1, critter_art.S_EYE, critter_art.S_SHELL_D)),
}


def frames(x):
    """Every frame in a library (left-facing copies are mirrors: skipped)."""
    if isinstance(x, pygame.Surface):
        yield x
    elif isinstance(x, dict):
        for key, value in x.items():
            if not (isinstance(key, str) and key.endswith("_left")):
                yield from frames(value)
    elif isinstance(x, (list, tuple)):
        for value in x:
            yield from frames(value)


def colours(frame):
    w, h = frame.get_size()
    return {tuple(frame.get_at((x, y)))[:3] for y in range(h) for x in range(w) if frame.get_at((x, y)).a}


def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


class OneStyle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.art = art()

    def test_no_stray_crumbs_of_body_colour(self):
        for name, (palette, details) in CREATURES.items():
            allowed = {tuple(palette[i]) for i in details}
            for i, frame in enumerate(frames(self.art[name])):
                strays = {tuple(frame.get_at(p))[:3] for p in orphans(frame)} - allowed
                self.assertEqual(strays, set(), f"{name}[{i}]")

    def test_outlines_are_dark_and_soft_not_black(self):
        # Like Mochi's plum: dark, but with colour in it, and a little blue.
        palettes = {"mochi": cat_art.PALETTE, "duck": pond_art.HEN, "duckling": pond_art.DUCKLING,
                    **{name: palette for name, (palette, _) in CREATURES.items()}}
        for name, palette in palettes.items():
            out = palette[1]
            self.assertLess(lum(out), 90, name)
            if name == "crow":                  # black all over: the outline only has to be darker still
                self.assertLess(lum(out), lum(palette[bird_art.BASE]), name)
                continue
            self.assertGreater(max(out), 30, f"{name}: not plain black")
            self.assertGreaterEqual(out[2], out[1], f"{name}: a cool, plum-ward outline")

    def test_eyes_catch_the_light(self):
        for name, key, shine in (("fox", "stand_right", fox_art.PALETTE[fox_art.SHINE]),
                                 ("deer", "stand_right", deer_art.PALETTE[deer_art.SHINE]),
                                 ("heron", "stand_right", pond_art.HERON_PALETTE[pond_art.H_SHINE]),
                                 ("crow", "idle", bird_art.CROW[bird_art.SHINE]),
                                 ("hedgehog", "walk", critter_art.HOG[critter_art.H_SHINE])):
            self.assertIn(shine, colours(next(frames(self.art[name][key]))), name)

    def test_shadows_cool_and_light_warm(self):
        # Down each coat's ramp the hue leans blue in the shade and toward
        # yellow in the light: the shadow has relatively more blue than the
        # light does.
        for name, palette, dark, light in (("mochi", cat_art.PALETTE, cat_art.DARK, cat_art.LIGHT),
                                           ("fox", fox_art.PALETTE, fox_art.DARK, fox_art.LIGHT),
                                           ("deer", deer_art.PALETTE, deer_art.DARK, deer_art.LIGHT),
                                           ("sparrow", bird_art.SPARROW, bird_art.DARK, bird_art.LIGHT)):
            d, li = palette[dark], palette[light]
            self.assertGreater(d[2] / max(1, d[0]), li[2] / max(1, li[0]), name)


if __name__ == "__main__":
    unittest.main()
