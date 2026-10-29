"""Mochi's drawn sprites and how the body uses them."""
import math
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from habitat import cat_anims, cat_art
from habitat.cat_art import GROUND, SCALE
from habitat.entities.cat import cat_library, eye_pixels, view_for
from habitat.pixelrig import despeckle
from tests.pixel_lint import orphans
from tests.support import fixed_clock
from habitat.world import World

pygame.init()
pygame.display.set_mode((64, 64))

SIDE_NEEDED = ["walk", "trot", "run", "stalk", "stand", "sit", "lie", "sleep_curl", "sleep_loaf", "sleep_flat",
               "sitdown", "standup", "liedown", "situp", "curlup", "uncurl", "doze", "undoze", "sprawl",
               "unsprawl", "stretch", "yawn_lie", "yawn_sit", "meow_sit", "groom", "groom_lie",
               "eat", "eat_start", "eat_end", "drink", "drink_start", "drink_end", "crouch", "pounce",
               "swipe_sit", "swipe_stand", "rear", "hiss", "hiss_start", "sniff", "sniff_start",
               "sit_look", "lie_look", "stand_look"]
FRONT_ONLY = ["scratch"]     # an ear scratch reads face-on: the raised leg clear of her body
FACING_NEEDED = ["walk", "trot", "run", "stalk", "stand", "sit", "sitdown", "standup", "eat", "eat_start",
                 "eat_end"]


class Library(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = cat_library()

    def test_every_side_animation_exists_both_ways(self):
        for name in SIDE_NEEDED:
            for side in ("left", "right"):
                with self.subTest(key=f"{name}_{side}"):
                    self.assertIn(f"{name}_{side}", self.lib)

    def test_front_and_back_views_cover_walking_and_sitting(self):
        for name in FACING_NEEDED:
            for view in ("front", "back"):
                with self.subTest(key=f"{name}_{view}"):
                    self.assertIn(f"{name}_{view}", self.lib)
        for name in ("meow_sit", "yawn_sit", "groom", "swipe_sit") + tuple(FRONT_ONLY):
            self.assertIn(f"{name}_front", self.lib)

    def test_scratching_an_ear_lifts_a_leg_clear_of_her_body(self):
        frames = self.lib["scratch_front"]
        sitting = self.lib["sit_front"][0].get_bounding_rect()
        raking = frames[len(frames) // 2].get_bounding_rect()
        self.assertLess(raking.left, sitting.left - 2, "the leg sticks out to the side")
        top_left = min(y for y in range(64) for x in range(raking.left, raking.left + 3)
                       if frames[len(frames) // 2].get_at((x, y)).a)
        self.assertLess(top_left, sitting.top + 14, "...with the foot up at her ear")
        self.assertNotIn("scratch_right", self.lib, "side-on, the raised leg vanishes into her: not drawn")

    def test_blink_twins_match_their_animation_frame_for_frame(self):
        twins = [k for k in self.lib if k.endswith("__blink")]
        self.assertGreater(len(twins), 20)
        for key in twins:
            self.assertEqual(len(self.lib[key]), len(self.lib[key[:-len("__blink")]]), key)

    def test_left_is_the_mirror_of_right(self):
        right = self.lib["walk_right"][2]
        left = self.lib["walk_left"][2]
        flipped = pygame.transform.flip(right, True, False)
        self.assertEqual(pygame.image.tobytes(flipped, "RGBA"), pygame.image.tobytes(left, "RGBA"))

    def test_feet_touch_the_anchor_row(self):
        # The renderer places (32, 48) on the ground; the paws must be there.
        for key in ("stand_right", "sit_right", "walk_front", "sit_back", "lie_left", "sleep_curl_right"):
            box = self.lib[key][0].get_bounding_rect()
            self.assertIn(box.bottom, (int(GROUND), int(GROUND) + 1), key)

    def test_nothing_sinks_below_the_ground(self):
        for key, frames in self.lib.items():
            for i, frame in enumerate(frames):
                self.assertLessEqual(frame.get_bounding_rect().bottom, int(GROUND) + 1, f"{key}[{i}]")


class Gait(unittest.TestCase):
    def test_planted_paws_do_not_slide(self):
        """While a paw is on the ground, body travel plus the paw's offset
        is constant: the paw stays put in the world."""
        stride = cat_anims.WALK_STRIDE
        n = 240
        for leg, offset in cat_anims.WALK_LATERAL.items():
            planted = []
            for i in range(n):
                phi = i / n
                t = (phi - offset) % 1.0
                if 0.02 < t < 0.6:
                    pose = cat_anims.side_gait(cat_anims.STAND, phi, stride, 0.62, 2.0, cat_anims.WALK_LATERAL)
                    world_x = phi * stride + pose[leg][0]
                    planted.append(world_x)
            spread = max(planted) - min(planted)
            # Allow for the wrap-around of the travelled distance.
            spread = min(spread, abs(spread - stride))
            self.assertLess(spread, 0.05, f"{leg} slides {spread:.2f} px while planted")

    def test_stride_constants_match_the_drawn_cycle(self):
        self.assertAlmostEqual(cat_anims.STRIDES["walk"], cat_anims.WALK_STRIDE * SCALE)
        self.assertAlmostEqual(cat_anims.STRIDES["run"], cat_anims.RUN_STRIDE * SCALE)


class Views(unittest.TestCase):
    def test_headings_map_to_views(self):
        self.assertEqual(view_for(0.0), "right")
        self.assertEqual(view_for(math.pi), "left")
        self.assertEqual(view_for(math.pi / 2), "front")
        self.assertEqual(view_for(-math.pi / 2), "back")

    def test_diagonals_use_the_three_quarter_views(self):
        self.assertEqual(view_for(math.radians(45)), "fr")       # down and to the right: coming toward you
        self.assertEqual(view_for(math.radians(135)), "fl")
        self.assertEqual(view_for(math.radians(-45)), "br")      # up and to the right: going away
        self.assertEqual(view_for(math.radians(-135)), "bl")

    def test_eight_views_round_the_compass(self):
        seen = [view_for(math.radians(a)) for a in range(0, 360, 45)]
        self.assertEqual(seen, ["right", "fr", "front", "fl", "left", "bl", "back", "br"])

    def test_the_current_view_holds_near_a_boundary(self):
        just_past = math.radians(29)
        self.assertEqual(view_for(just_past), "fr")
        self.assertEqual(view_for(just_past, current="right"), "right")
        self.assertEqual(view_for(math.radians(40), current="right"), "fr")

    def test_a_turn_from_side_on_to_face_on_passes_through_three_quarters(self):
        views, current = [], "right"
        for a in range(0, 91, 2):
            current = view_for(math.radians(a), current)
            if not views or views[-1] != current:
                views.append(current)
        self.assertEqual(views, ["right", "fr", "front"])


def run(world, seconds):
    for _ in range(int(seconds * 30)):
        world.update(1 / 30)


class Body(unittest.TestCase):
    def test_getting_up_from_sleep_passes_through_every_posture(self):
        world = World(427, 266, seed=5, clock=fixed_clock(12.0), weather="clear", weather_locked=True)
        cat = world.cat
        keys = []
        for _ in range(int(25 * 30)):
            world.update(1 / 30)
            if not keys or keys[-1] != cat.anim.key:
                keys.append(cat.anim.key)
            if cat.posture == "stand":
                break
        names = [k.rsplit("_", 1)[0] for k in keys]
        for step in ("uncurl", "situp", "standup"):
            self.assertIn(step, names)
        self.assertLess(names.index("uncurl"), names.index("situp"))
        self.assertLess(names.index("situp"), names.index("standup"))

    def test_the_cat_blinks(self):
        world = World(427, 266, seed=5, clock=fixed_clock(12.0), weather="clear", weather_locked=True)
        cat = world.cat
        lib = cat_library()
        blinked = False
        for _ in range(int(40 * 30)):
            world.update(1 / 30)
            frame = cat.sprite()[0]
            if cat.anim.key and frame is not cat.anim.frame and frame in lib.get(cat.anim.key + "__blink", ()):
                blinked = True
                break
        self.assertTrue(blinked)


class Craft(unittest.TestCase):
    """The look holds up as pixel art, and the storybook design is there."""

    @classmethod
    def setUpClass(cls):
        cls.lib = cat_library()

    def colours(self, frame):
        w, h = frame.get_size()
        return {tuple(frame.get_at((x, y)))[:3] for y in range(h) for x in range(w) if frame.get_at((x, y)).a}

    def test_no_stray_pixels(self):
        nose = cat_art.PALETTE[cat_art.PINK]      # a nose is one pixel on purpose
        for key, frames in self.lib.items():
            if key.endswith("_left") or "__blink" in key:
                continue
            for i, frame in enumerate(frames):
                strays = [p for p in orphans(frame) if tuple(frame.get_at(p))[:3] != nose]
                self.assertEqual(strays, [], f"{key}[{i}]")

    def test_she_has_her_own_marks_and_the_visitor_does_not(self):
        from habitat.entities.visitor import ginger_library
        mark = cat_art.PALETTE[cat_art.MARK]
        for key in ("stand_right", "sit_front", "sit_back", "hiss_right"):
            self.assertIn(mark, self.colours(self.lib[key][0]), f"{key}: blaze or tail tip")
            self.assertNotIn(mark, self.colours(ginger_library()[key][0]), key)

    def test_big_eyes_with_a_glint(self):
        frame = self.lib["sit_front"][0]
        shine = cat_art.PALETTE[cat_art.SHINE]
        pupils = [(x, y) for y in range(64) for x in range(64)
                  if frame.get_at((x, y)).a and tuple(frame.get_at((x, y)))[:3] == cat_art.PALETTE[cat_art.PUPIL]]
        self.assertGreaterEqual(len(pupils), 6, "three dark pixels an eye")
        self.assertEqual(len(eye_pixels(frame)), 2)
        self.assertEqual(cat_art.EYE_SHINE, shine)

    def test_despeckle_merges_crumbs_and_keeps_what_it_is_told(self):
        grid = np.full((5, 5), 4, dtype=np.uint8)
        grid[2, 2] = 3
        self.assertEqual(despeckle(grid)[2, 2], 4)
        self.assertEqual(despeckle(grid, keep=(3,))[2, 2], 3)
        grid[2, 3] = 3                            # two together are a shape, not a crumb
        self.assertEqual(despeckle(grid)[2, 2], 3)


class Scratching(unittest.TestCase):
    def test_she_turns_to_you_to_scratch_an_ear(self):
        import random
        w = World(427, 266, seed=5, clock=fixed_clock(12.0), weather="clear", weather_locked=True)
        cat = w.cat
        w.entities = [cat]
        cat.posture, cat.view, cat.heading = "stand", "right", 0.0
        cat.idle_pose()
        cat.rng = random.Random(0)
        seen = set()
        for attempt in range(6):                  # grooming scratches about half the time
            cat._start("groom", cat.act_groom())
            for _ in range(int(25 * 30)):
                w.update(1 / 30)
                seen.add(cat.anim.key)
                if cat.activity_name != "groom":
                    break
            if "scratch_front" in seen:
                break
        self.assertIn("scratch_front", seen)


if __name__ == "__main__":
    unittest.main()
