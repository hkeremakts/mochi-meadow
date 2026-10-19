"""Any-angle route planning on a blocked-cell grid.

Routes are lists of waypoints joined by straight lines; the walker steers
along them, so every straight line must stay on open ground and routes
should not zig-zag where a straight line would do.
"""
import math
import unittest

import numpy as np

from habitat.paths import clear_line, find_path, widen


def length(start, path):
    pts = [start] + list(path)
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


class PlannerCase(unittest.TestCase):
    def assertValidRoute(self, grid, start, path, goal, ignore=None):
        self.assertIsNotNone(path, "expected a route")
        self.assertEqual(tuple(path[-1]), tuple(goal))
        points = [start] + [tuple(p) for p in path]
        for a, b in zip(points, points[1:]):
            self.assertTrue(clear_line(grid if ignore is None else grid & ~ignore, a, b),
                            f"segment {a}->{b} crosses blocked ground")


class OpenGround(PlannerCase):
    def test_open_field_is_one_straight_line(self):
        grid = np.zeros((60, 80), dtype=bool)
        self.assertEqual(find_path(grid, (10, 10), (70, 45)), [(70, 45)])

    def test_same_point_needs_no_route(self):
        grid = np.zeros((60, 80), dtype=bool)
        self.assertEqual(find_path(grid, (10, 10), (10, 10)), [])


class Obstacles(PlannerCase):
    def test_goes_around_a_wall_through_the_gap(self):
        grid = np.zeros((60, 80), dtype=bool)
        grid[:45, 40] = True
        path = find_path(grid, (10, 10), (70, 10))
        self.assertValidRoute(grid, (10, 10), path, (70, 10))
        self.assertGreaterEqual(len(path), 2)
        # Nearly the shortest way: down to the gap and back up, no detours.
        best = 2 * math.dist((10, 10), (40, 45))
        self.assertLess(length((10, 10), path), best * 1.1)

    def test_cuts_corners_instead_of_staircasing(self):
        grid = np.zeros((80, 80), dtype=bool)
        grid[30:50, 30:50] = True
        path = find_path(grid, (10, 10), (70, 70))
        self.assertValidRoute(grid, (10, 10), path, (70, 70))
        self.assertLessEqual(len(path), 3)

    def test_blocked_goal_has_no_route(self):
        grid = np.zeros((60, 80), dtype=bool)
        grid[38:43, 48:53] = True
        self.assertIsNone(find_path(grid, (10, 10), (50, 40)))

    def test_goal_behind_a_full_wall_has_no_route(self):
        grid = np.zeros((60, 80), dtype=bool)
        grid[:, 30] = True
        self.assertIsNone(find_path(grid, (10, 10), (50, 40)))

    def test_can_walk_out_of_the_obstacle_it_starts_in(self):
        # A cat sheltering under a bush stands inside the bush's blocked
        # zone; it must still be able to leave.
        grid = np.zeros((60, 80), dtype=bool)
        grid[6:15, 6:15] = True
        blob = np.zeros_like(grid)
        blob[6:15, 6:15] = True
        path = find_path(grid, (10, 10), (60, 10))
        self.assertValidRoute(grid, (10, 10), path, (60, 10), ignore=blob)

    def test_cannot_cross_a_second_obstacle_after_leaving_the_first(self):
        grid = np.zeros((60, 80), dtype=bool)
        grid[6:15, 6:15] = True
        grid[:, 30] = True
        self.assertIsNone(find_path(grid, (10, 10), (60, 10)))


class WalkerAgreement(unittest.TestCase):
    """The walker treats (x, y) as pixel (int(x), int(y)).  A route the
    planner calls clear must be clear for a walker starting anywhere inside
    its pixel, or the cat stalls against an edge it was told was open."""

    def test_routes_from_fractional_positions_never_touch_blocked_pixels(self):
        rng = np.random.default_rng(3)
        for trial in range(60):
            grid = np.zeros((80, 120), dtype=bool)
            for _ in range(6):
                x, y = rng.integers(10, 110), rng.integers(10, 70)
                grid[y:y + rng.integers(3, 15), x:x + rng.integers(3, 20)] = True
            start = (rng.uniform(1, 118), rng.uniform(1, 78))
            goal = (int(rng.integers(1, 118)), int(rng.integers(1, 78)))
            if grid[int(start[1]), int(start[0])] or grid[goal[1], goal[0]]:
                continue
            path = find_path(grid, start, goal)
            if not path:
                continue
            here = start
            for wp in path:
                d = math.dist(here, wp)
                steps = max(1, int(d / 0.25))
                for i in range(1, steps + 1):
                    x = here[0] + (wp[0] - here[0]) * i / steps
                    y = here[1] + (wp[1] - here[1]) * i / steps
                    self.assertFalse(grid[int(y), int(x)], f"trial {trial}: walker hits {(x, y)} on {here}->{wp}")
                here = wp


class Clearance(unittest.TestCase):
    def test_routes_keep_off_obstacle_corners_when_there_is_room(self):
        # Steering follows a route on a curve, not the exact line: routes
        # must leave a margin around corners, not shave them.
        grid = np.zeros((80, 120), dtype=bool)
        grid[20:60, 50:70] = True
        wide = widen(grid, 2)
        path = find_path(grid, (20.5, 30.5), (100, 50), wide=wide)
        points = [(20.5, 30.5)] + path
        for a, b in zip(points, points[1:]):
            n = int(math.dist(a, b) * 4) + 2
            for i in range(n + 1):
                x = a[0] + (b[0] - a[0]) * i / n
                y = a[1] + (b[1] - a[1]) * i / n
                near = grid[max(0, int(y) - 1):int(y) + 2, max(0, int(x) - 1):int(x) + 2]
                self.assertFalse(near.any(), f"route passes within a pixel of the wall at {(x, y)}")

    def test_falls_back_to_a_tight_route_through_a_narrow_gap(self):
        grid = np.zeros((60, 80), dtype=bool)
        grid[:, 40] = True
        grid[30:32, 40] = False          # a 2-pixel gap: too narrow for the margin
        path = find_path(grid, (10, 30), (70, 30), wide=widen(grid, 2))
        self.assertIsNotNone(path)

    def test_a_start_inside_the_margin_can_still_leave(self):
        grid = np.zeros((60, 80), dtype=bool)
        grid[:, 40] = True
        grid[:20, 40] = False
        path = find_path(grid, (39.5, 40.5), (10, 40), wide=widen(grid, 2))
        self.assertEqual(path, [(10, 40)])


class LineOfSight(unittest.TestCase):
    def test_line_through_a_single_blocked_cell_is_not_clear(self):
        grid = np.zeros((20, 20), dtype=bool)
        grid[10, 10] = True
        self.assertFalse(clear_line(grid, (0, 0), (19, 19)))
        self.assertTrue(clear_line(grid, (0, 5), (19, 5)))


if __name__ == "__main__":
    unittest.main()
