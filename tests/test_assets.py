"""Sprite loading: stray-pixel cleanup and frame ordering."""
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

import tempfile

from habitat.assets import generated_library, load_animation_folders, load_frames, remove_islands

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def blank(w, h):
    s = pygame.Surface((w, h), pygame.SRCALPHA, 32)
    s.fill((0, 0, 0, 0))
    return s


class IslandRemoval(unittest.TestCase):
    def test_tiny_detached_speck_is_erased(self):
        s = blank(20, 20)
        s.fill((200, 0, 0, 255), pygame.Rect(8, 8, 8, 8))  # 64 px body
        s.set_at((0, 0), (200, 0, 0, 255))                  # 2 px speck
        s.set_at((1, 0), (200, 0, 0, 255))
        out = remove_islands(s)
        self.assertEqual(out.get_at((0, 0)).a, 0)
        self.assertEqual(out.get_at((1, 0)).a, 0)
        self.assertEqual(tuple(out.get_at((10, 10))), (200, 0, 0, 255))

    def test_substantial_second_part_is_kept(self):
        # e.g. a tail tip drawn detached from the body is real art
        s = blank(30, 20)
        s.fill((0, 0, 200, 255), pygame.Rect(2, 2, 8, 8))    # 64 px
        s.fill((0, 0, 200, 255), pygame.Rect(20, 10, 4, 4))  # 16 px = 25 %
        out = remove_islands(s)
        self.assertEqual(out.get_at((21, 11)).a, 255)


def write_png(path, color):
    s = blank(4, 4)
    s.fill(color, pygame.Rect(1, 1, 2, 2))
    pygame.image.save(s, path)


class AnimationLibrary(unittest.TestCase):
    def test_flat_files_from_the_slicing_tool_are_loaded_in_numeric_order(self):
        # tools/slice_labeled_sheet.py writes walk_down_00.png, walk_down_01.png ...
        with tempfile.TemporaryDirectory() as root:
            for i in range(11):
                write_png(os.path.join(root, f"walk_down_{i:02d}.png"), (i * 20, 0, 0, 255))
            lib = load_animation_folders(root)
            self.assertEqual(len(lib["walk_down"]), 11)
            reds = [frame.get_at((1, 1)).r for frame in lib["walk_down"]]
            self.assertEqual(reds, [i * 20 for i in range(11)])

    def test_folders_and_flat_files_live_side_by_side(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "walk(right)"))
            write_png(os.path.join(root, "walk(right)", "a_0.png"), (0, 0, 255, 255))
            write_png(os.path.join(root, "yawn_01.png"), (0, 255, 0, 255))
            lib = load_animation_folders(root)
            self.assertEqual(sorted(lib), ["walk_right", "yawn"])


class GeneratedArt(unittest.TestCase):
    """Drawn sprites are saved once and reloaded until their code changes."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.source = os.path.join(self.dir.name, "art.py")
        with open(self.source, "w") as f:
            f.write("version 1")
        self.calls = 0

    def tearDown(self):
        self.dir.cleanup()

    def build(self):
        self.calls += 1
        s = blank(6, 6)
        s.fill((10, 200, 30, 255), pygame.Rect(1, 1, 2, 2))
        s.set_at((5, 5), (10, 200, 30, 255))   # a lone whisker pixel
        return {"walk_right": [s, s], "sit_front": [s]}

    def load(self):
        return generated_library("thing", [self.source], self.build, root=self.dir.name)

    def test_first_load_draws_and_saves(self):
        lib = self.load()
        self.assertEqual(self.calls, 1)
        self.assertEqual(len(lib["walk_right"]), 2)
        self.assertTrue(os.path.isdir(os.path.join(self.dir.name, "thing", "walk_right")))

    def test_second_load_reads_the_saved_files(self):
        self.load()
        lib = self.load()
        self.assertEqual(self.calls, 1)
        self.assertEqual(tuple(lib["sit_front"][0].get_at((1, 1))), (10, 200, 30, 255))

    def test_saved_art_keeps_single_pixel_details(self):
        self.load()
        lib = self.load()
        self.assertEqual(lib["walk_right"][0].get_at((5, 5)).a, 255)

    def test_changing_the_drawing_code_redraws(self):
        self.load()
        with open(self.source, "w") as f:
            f.write("version 2")
        self.load()
        self.assertEqual(self.calls, 2)


class RealAssets(unittest.TestCase):
    def test_label_fragment_is_gone_from_the_sliced_swipe_frame(self):
        # assets/cat/right_paw_swipe(stand_front) frame 0 carries a piece of
        # the sheet's text label at x=0..6; the cat's body starts near x=20.
        frames = load_frames(os.path.join(ROOT, "assets", "cat", "right_paw_swipe(stand_front)"))
        self.assertGreaterEqual(frames[0].get_bounding_rect().left, 10)

    def test_frames_are_in_numeric_order(self):
        # 11 frames: an alphabetical sort would put _10 straight after _1
        folder = os.path.join(ROOT, "assets", "cat", "left_paw_swipe(sit_front)")
        frames = load_frames(folder)
        self.assertEqual(len(frames), 11)
        for i, frame in enumerate(frames):
            expected = pygame.image.load(os.path.join(folder, f"cat_cropped_35_{i}.png"))
            self.assertEqual(pygame.image.tobytes(frame, "RGBA"),
                             pygame.image.tobytes(expected, "RGBA"), f"frame {i}")


if __name__ == "__main__":
    unittest.main()
