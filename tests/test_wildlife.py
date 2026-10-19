"""Wildlife edge cases found in long runs."""
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from tests.support import fixed_clock
from habitat.entities.wildlife import Pigeon
from habitat.world import World

pygame.init()
pygame.display.set_mode((64, 64))


class Pigeons(unittest.TestCase):
    def test_a_delayed_flock_member_has_a_frame_the_moment_it_sets_off(self):
        # Regression: the waiting -> arriving switch returned before choosing
        # an animation, so the bird was drawn with no frame for one tick.
        world = World(320, 200, seed=9, clock=fixed_clock(12.0))
        bird = Pigeon(world, 150, 120, delay=0.05)
        for _ in range(10):
            bird.update(1 / 60)
            spr = bird.sprite()
            if spr is not None:
                self.assertIsNotNone(spr[0], f"no frame in state {bird.state}")


if __name__ == "__main__":
    unittest.main()
