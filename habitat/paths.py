"""Any-angle route planning.

``blocked`` is a boolean grid indexed ``[y, x]``; True marks ground a
walker may not enter.  Routes come from A* over a coarse copy of the grid
(8-connected, no corner cutting), then are pulled tight: each waypoint is
dropped when a straight line past it is clear.  The result is a few
straight segments the cat can follow with gentle steering, instead of a
staircase.
"""

import heapq
import math

import numpy as np

CELL = 3          # coarse grid spacing in art pixels
SQRT2 = math.sqrt(2.0)


def clear_line(blocked, a, b):
    """True if the straight segment a->b touches no blocked cell.  A point
    (x, y) lies in cell (int(x), int(y)), exactly as the walker sees it."""
    (x0, y0), (x1, y1) = a, b
    n = int(math.hypot(x1 - x0, y1 - y0) * 4) + 2
    xs = np.floor(np.linspace(x0, x1, n)).astype(np.int32)
    ys = np.floor(np.linspace(y0, y1, n)).astype(np.int32)
    h, w = blocked.shape
    if xs.min() < 0 or ys.min() < 0 or xs.max() >= w or ys.max() >= h:
        return False
    return not blocked[ys, xs].any()


def widen(blocked, radius):
    """``blocked`` grown by ``radius`` pixels: planning on it keeps routes
    that far from obstacles."""
    out = blocked.copy()
    for axis in (0, 1):
        src = out.copy()
        for k in range(1, radius + 1):
            if axis == 0:
                out[k:] |= src[:-k]
                out[:-k] |= src[k:]
            else:
                out[:, k:] |= src[:, :-k]
                out[:, :-k] |= src[:, k:]
    return out


def find_path(blocked, start, goal, wide=None):
    """Waypoints after ``start`` ending at ``goal``; [] if already there,
    None if there is no way.  A walker standing inside an obstacle (tucked
    under a bush) may cross that obstacle to get out, but no other.

    With ``wide`` (``blocked`` grown by a margin, see widen()) the route
    keeps that margin from obstacles wherever there is room, so a walker
    that steers along it on a curve does not clip corners.  Only where the
    margin closes a passage is the tight route used."""
    h, w = blocked.shape
    sx, sy = int(start[0]), int(start[1])
    inside = not (0 <= sx < w and 0 <= sy < h) or blocked[sy, sx]
    if wide is not None and not inside:
        # Near the two ends the margin is lifted, so a walker standing (or
        # heading) close to an edge can still start and arrive.
        carved = wide.copy()
        for px, py in (start, goal):
            x0, y0 = int(px), int(py)
            ys = slice(max(0, y0 - 4), min(h, y0 + 5))
            xs = slice(max(0, x0 - 4), min(w, x0 + 5))
            carved[ys, xs] = blocked[ys, xs]
        route = _plan(carved, start, goal)
        if route is not None:
            return route
    return _plan(blocked, start, goal)


def _plan(blocked, start, goal):
    fx, fy = float(start[0]), float(start[1])
    sx, sy = int(fx), int(fy)
    gx, gy = int(goal[0]), int(goal[1])
    h, w = blocked.shape
    if math.hypot(goal[0] - fx, goal[1] - fy) < 0.5:
        return []
    if not (0 <= gx < w and 0 <= gy < h) or blocked[gy, gx]:
        return None
    if not (0 <= sx < w and 0 <= sy < h):
        return None
    grid = blocked
    if blocked[sy, sx]:
        grid = blocked.copy()
        grid[component(blocked, sx, sy)] = False
    if clear_line(grid, (fx, fy), goal):
        return [tuple(goal)]
    cells = _astar(grid, (fx, fy), goal)
    if cells is None:
        return None
    points = ([(fx, fy)] + [(cx * CELL + CELL / 2, cy * CELL + CELL / 2) for cx, cy in cells[1:-1]]
              + [tuple(goal)])
    return _pull(grid, points)[1:]


def _coarse(grid):
    """A coarse cell is blocked if any pixel in it is."""
    h, w = grid.shape
    ch, cw = -(-h // CELL), -(-w // CELL)
    padded = np.ones((ch * CELL, cw * CELL), bool)
    padded[:h, :w] = grid
    return padded.reshape(ch, CELL, cw, CELL).any(axis=(1, 3))


def _nearest_free(grid, coarse, x, y):
    """A free coarse cell near fine point (x, y), reachable in a straight line."""
    ch, cw = coarse.shape
    cx0, cy0 = int(x // CELL), int(y // CELL)
    for r in range(0, 4):
        best = None
        for cy in range(cy0 - r, cy0 + r + 1):
            for cx in range(cx0 - r, cx0 + r + 1):
                if 0 <= cx < cw and 0 <= cy < ch and not coarse[cy, cx]:
                    px, py = cx * CELL + CELL / 2, cy * CELL + CELL / 2
                    d = (px - x) ** 2 + (py - y) ** 2
                    if (best is None or d < best[0]) and clear_line(grid, (x, y), (px, py)):
                        best = (d, (cx, cy))
        if best:
            return best[1]
    return None


def _astar(grid, start, goal):
    coarse = _coarse(grid)
    ch, cw = coarse.shape
    s = _nearest_free(grid, coarse, *start)
    g = _nearest_free(grid, coarse, *goal)
    if s is None or g is None:
        return None
    gx, gy = g
    open_heap = [(0.0, 0.0, s)]
    came = {s: None}
    cost = {s: 0.0}
    steps = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
             (1, 1, SQRT2), (1, -1, SQRT2), (-1, 1, SQRT2), (-1, -1, SQRT2))
    while open_heap:
        _, c, cur = heapq.heappop(open_heap)
        if cur == g:
            path = []
            while cur is not None:
                path.append(cur)
                cur = came[cur]
            return path[::-1]
        if c > cost.get(cur, math.inf):
            continue
        x, y = cur
        for dx, dy, step in steps:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < cw and 0 <= ny < ch) or coarse[ny, nx]:
                continue
            if dx and dy and (coarse[y, nx] or coarse[ny, x]):
                continue  # no squeezing between two blocked corners
            nc = c + step
            if nc < cost.get((nx, ny), math.inf):
                cost[(nx, ny)] = nc
                came[(nx, ny)] = cur
                ddx, ddy = abs(gx - nx), abs(gy - ny)
                heur = max(ddx, ddy) + (SQRT2 - 1) * min(ddx, ddy)
                heapq.heappush(open_heap, (nc + heur, nc, (nx, ny)))
    return None


def _pull(grid, points):
    """Drop waypoints a straight line can skip."""
    out = [points[0]]
    i = 0
    n = len(points)
    while i < n - 1:
        j = i + 1
        while j + 1 < n and clear_line(grid, points[i], points[j + 1]):
            j += 1
        out.append(points[j])
        i = j
    return out


def component(grid, x, y):
    """Boolean mask of the blocked region containing (x, y)."""
    height, width = grid.shape
    mask = np.zeros_like(grid)
    stack = [(x, y)]
    mask[y, x] = True
    while stack:
        cx, cy = stack.pop()
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if 0 <= nx < width and 0 <= ny < height and grid[ny, nx] and not mask[ny, nx]:
                mask[ny, nx] = True
                stack.append((nx, ny))
    return mask


class Regions:
    """Which open ground connects to which, for quick 'can I get there?'
    checks without planning a route."""

    def __init__(self, blocked):
        self.blocked = blocked
        self.coarse = coarse = _coarse(blocked)
        ch, cw = coarse.shape
        labels = np.full((ch, cw), -1, np.int32)
        label = 0
        for y0 in range(ch):
            for x0 in range(cw):
                if coarse[y0, x0] or labels[y0, x0] >= 0:
                    continue
                labels[y0, x0] = label
                stack = [(x0, y0)]
                while stack:
                    x, y = stack.pop()
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if 0 <= nx < cw and 0 <= ny < ch and not coarse[ny, nx] and labels[ny, nx] < 0:
                            labels[ny, nx] = label
                            stack.append((nx, ny))
                label += 1
        self.labels = labels

    def label(self, x, y):
        c = _nearest_free(self.blocked, self.coarse, int(round(x)), int(round(y)))
        return None if c is None else int(self.labels[c[1], c[0]])

    def connected(self, a, b):
        la, lb = self.label(*a), self.label(*b)
        return la is not None and la == lb
