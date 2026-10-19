"""Animator behaviour.

Frames are opaque objects to the animator, so plain strings stand in for
sprites here; no pygame needed.
"""
import unittest

from habitat.anim import Animator

WALK = ["w0", "w1", "w2", "w3"]
WALK6 = ["a0", "a1", "a2", "a3", "a4", "a5"]
DOWN4 = ["d0", "d1", "d2", "d3"]
YAWN = ["y0", "y1", "y2"]


class TimeDrivenPlayback(unittest.TestCase):
    def test_frame_follows_elapsed_time_at_clip_fps(self):
        a = Animator()
        a.play("walk", WALK, fps=8.0)
        a.update(0.3)  # 0.3 s * 8 fps = 2.4 frames
        self.assertEqual(a.frame, "w2")

    def test_looping_clip_wraps_around(self):
        a = Animator()
        a.play("walk", WALK, fps=8.0)
        a.update(0.6)  # 4.8 frames -> wraps to index 0
        self.assertEqual(a.frame, "w0")

    def test_one_shot_holds_last_frame_and_reports_done(self):
        a = Animator()
        a.play("yawn", YAWN, fps=10.0, loop=False)
        a.update(0.25)  # 2.5 frames: on the last frame but not past it
        self.assertEqual(a.frame, "y2")
        self.assertFalse(a.done)
        a.update(1.0)
        self.assertEqual(a.frame, "y2")
        self.assertTrue(a.done)


class DistanceDrivenPlayback(unittest.TestCase):
    def test_frame_advances_with_distance_travelled(self):
        a = Animator()
        a.play("walk", WALK, stride=16.0)  # 16 px per 4-frame cycle -> 4 px per frame
        a.update(0.1, distance=9.0)        # 9 / 4 = 2.25 frames
        self.assertEqual(a.frame, "w2")

    def test_standing_still_freezes_the_frame_however_much_time_passes(self):
        # This is what keeps paws planted: no distance, no frame change.
        a = Animator()
        a.play("walk", WALK, stride=16.0)
        a.update(0.1, distance=9.0)
        a.update(5.0, distance=0.0)
        self.assertEqual(a.frame, "w2")


class SwitchingClips(unittest.TestCase):
    def test_replaying_the_current_clip_does_not_restart_it(self):
        a = Animator()
        a.play("walk", WALK, fps=8.0)
        a.update(0.3)
        a.play("walk", WALK, fps=8.0)
        self.assertEqual(a.frame, "w2")

    def test_restart_flag_rewinds_the_current_clip(self):
        a = Animator()
        a.play("walk", WALK, fps=8.0)
        a.update(0.3)
        a.play("walk", WALK, fps=8.0, restart=True)
        self.assertEqual(a.frame, "w0")

    def test_new_clip_starts_from_its_first_frame(self):
        a = Animator()
        a.play("walk", WALK, fps=8.0)
        a.update(0.3)
        a.play("yawn", YAWN, fps=10.0, loop=False)
        self.assertEqual(a.frame, "y0")
        self.assertFalse(a.done)

    def test_keep_phase_carries_gait_position_across_a_turn(self):
        # Turning from walk_right to walk_down mid-stride must not snap the
        # legs back to frame 0.  Halfway through a 6-frame cycle is frame 3;
        # halfway through a 4-frame cycle is frame 2.
        a = Animator()
        a.play("walk_right", WALK6, stride=18.0)
        a.update(0.1, distance=9.0)  # 9 px of an 18 px cycle = phase 0.5
        self.assertEqual(a.frame, "a3")
        a.play("walk_down", DOWN4, stride=12.0, keep_phase=True)
        self.assertEqual(a.frame, "d2")


if __name__ == "__main__":
    unittest.main()
