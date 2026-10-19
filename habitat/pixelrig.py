"""A tiny toolkit for drawing posable pixel-art creatures.

Creatures are described as shapes (ellipses, tapered capsules, polygons)
in art-pixel coordinates.  Shapes are rasterised on a supersampled grid of
palette indices, then each art pixel takes the colour that covers most of
it.  That keeps the result on a strict palette with crisp edges (no
anti-aliasing mush), and because poses are just numbers, any in-between
frame can be drawn: sitting down, standing up, a stretch, a wing beat.

Finally the silhouette gets a one-pixel outline and simple form shading
(a lit top edge, a shaded underside), the way pixel artists shade by hand.
"""

import math

import numpy as np
import pygame
from PIL import Image, ImageDraw

SS = 8  # supersampling factor


class Canvas:
    """``scale`` enlarges everything about ``pivot`` (a creature's feet), so
    a puppet can be sized without touching its pose numbers; ``shift``
    then moves the drawing on the canvas (to make headroom, say)."""

    def __init__(self, width, height, ss=SS, scale=1.0, pivot=(0.0, 0.0), shift=(0.0, 0.0)):
        self.w, self.h, self.ss = width, height, ss
        self.k = scale
        self.pivot = pivot
        self.shift = shift
        self.idx = np.zeros((height * ss, width * ss), np.uint8)
        # Sample positions expressed in pose space.
        px, py = pivot
        sx, sy = shift
        self.ys = py + ((np.arange(height * ss, dtype=np.float32) + 0.5) / ss - sy - py) / scale
        self.xs = px + ((np.arange(width * ss, dtype=np.float32) + 0.5) / ss - sx - px) / scale

    def to_art(self, x, y):
        """Pose-space point -> art pixel position."""
        px, py = self.pivot
        return px + (x - px) * self.k + self.shift[0], py + (y - py) * self.k + self.shift[1]

    def to_pose(self, ax, ay):
        """Art pixel position -> pose-space point."""
        px, py = self.pivot
        return px + (ax - self.shift[0] - px) / self.k, py + (ay - self.shift[1] - py) / self.k

    # --- shapes -> boolean masks ------------------------------------------

    def _window(self, x0, y0, x1, y1):
        ss = self.ss
        x0, y0 = self.to_art(x0, y0)
        x1, y1 = self.to_art(x1, y1)
        c0 = max(0, int(math.floor(x0 * ss)) - 1)
        c1 = min(self.w * ss, int(math.ceil(x1 * ss)) + 2)
        r0 = max(0, int(math.floor(y0 * ss)) - 1)
        r1 = min(self.h * ss, int(math.ceil(y1 * ss)) + 2)
        return r0, r1, c0, c1

    def ellipse(self, cx, cy, rx, ry, angle=0.0):
        """Mask of an ellipse; ``angle`` in degrees, counter-clockwise on screen."""
        mask = np.zeros(self.idx.shape, bool)
        if rx <= 0 or ry <= 0:
            return mask
        reach = max(rx, ry)
        r0, r1, c0, c1 = self._window(cx - reach, cy - reach, cx + reach, cy + reach)
        if r0 >= r1 or c0 >= c1:
            return mask
        X = self.xs[c0:c1][None, :] - cx
        Y = self.ys[r0:r1][:, None] - cy
        a = math.radians(angle)
        ca, sa = math.cos(a), math.sin(a)
        u = X * ca - Y * sa
        v = X * sa + Y * ca
        mask[r0:r1, c0:c1] = (u / rx) ** 2 + (v / ry) ** 2 <= 1.0
        return mask

    def capsule(self, x0, y0, x1, y1, r0, r1=None):
        """Mask of a segment swept by a circle whose radius goes r0 -> r1."""
        if r1 is None:
            r1 = r0
        mask = np.zeros(self.idx.shape, bool)
        reach = max(r0, r1)
        w = self._window(min(x0, x1) - reach, min(y0, y1) - reach, max(x0, x1) + reach, max(y0, y1) + reach)
        ra, rb, ca, cb = w
        if ra >= rb or ca >= cb:
            return mask
        X = self.xs[ca:cb][None, :]
        Y = self.ys[ra:rb][:, None]
        dx, dy = x1 - x0, y1 - y0
        length2 = dx * dx + dy * dy
        if length2 < 1e-9:
            t = np.zeros_like(X + Y)
        else:
            t = np.clip(((X - x0) * dx + (Y - y0) * dy) / length2, 0.0, 1.0)
        px = x0 + t * dx
        py = y0 + t * dy
        radius = r0 + (r1 - r0) * t
        mask[ra:rb, ca:cb] = (X - px) ** 2 + (Y - py) ** 2 <= radius ** 2
        return mask

    def chain(self, points, radii):
        """A smooth limb or tail through ``points`` with per-point radii."""
        mask = np.zeros(self.idx.shape, bool)
        for (a, ra), (b, rb) in zip(zip(points, radii), zip(points[1:], radii[1:])):
            mask |= self.capsule(a[0], a[1], b[0], b[1], ra, rb)
        return mask

    def polygon(self, points):
        ss = self.ss
        img = Image.new("L", (self.w * ss, self.h * ss), 0)
        art = [self.to_art(x, y) for x, y in points]
        ImageDraw.Draw(img).polygon([(x * ss, y * ss) for x, y in art], fill=1)
        return np.asarray(img, dtype=bool)

    def grow(self, mask, amount=1.0):
        """``mask`` dilated by ``amount`` art pixels (square kernel)."""
        r = max(1, int(round(amount * self.ss)))
        out = mask.copy()
        for axis in (0, 1):
            src = out.copy()
            for k in range(1, r + 1):
                if axis == 0:
                    out[k:] |= src[:-k]
                    out[:-k] |= src[k:]
                else:
                    out[:, k:] |= src[:, :-k]
                    out[:, :-k] |= src[:, k:]
        return out

    # --- painting -----------------------------------------------------------

    def paint(self, mask, color, within=None, over=None):
        """Fill ``mask`` with palette index ``color``.

        ``within`` restricts painting to another mask; ``over`` restricts it
        to pixels that currently hold one of the given indices (handy for
        shading only the fur of a body part)."""
        m = mask
        if within is not None:
            m = m & within
        if over is not None:
            m = m & np.isin(self.idx, over)
        self.idx[m] = color

    def below(self, y):
        """Mask of everything lower than pose-space row ``y``."""
        return np.broadcast_to((self.ys > y)[:, None], self.idx.shape)

    def part(self, mask, color, crease=None, width=0.9, over=None, within=None):
        """Paint a body part that sits in front of what is already drawn;
        where it overlaps, it gets a ``crease`` line so a leg in front of
        the body, or a tail across the paws, still reads as separate."""
        if crease is not None:
            ring = self.grow(mask, width) & ~mask & (self.idx > 0)
            if over is not None:
                ring &= np.isin(self.idx, over)
            if within is not None:
                ring &= within
            self.idx[ring] = crease
        self.idx[mask] = color

    def covered(self):
        return self.idx > 0

    # --- down to art resolution -----------------------------------------------

    def resolve(self, palette_size, coverage=0.5):
        """Majority colour per art pixel; empty where less than ``coverage``
        of it is covered."""
        ss, h, w = self.ss, self.h, self.w
        blocks = self.idx.reshape(h, ss, w, ss)
        counts = np.stack([(blocks == k).sum(axis=(1, 3)) for k in range(palette_size)], axis=-1)
        empty = counts[..., 0] > ss * ss * (1.0 - coverage)
        colour = counts[..., 1:].argmax(axis=-1) + 1
        return np.where(empty, 0, colour).astype(np.uint8)


def shade(grid, rules):
    """Form shading: ``rules`` maps a base index to (lit, shaded); a base
    pixel with empty space above becomes lit, one with empty space below
    becomes shaded."""
    out = grid.copy()
    empty = grid == 0
    above = np.zeros_like(empty)
    above[1:] = empty[:-1]
    above[0] = True
    below = np.zeros_like(empty)
    below[:-1] = empty[1:]
    below[-1] = True
    for base, (lit, shaded) in rules.items():
        is_base = grid == base
        if lit is not None:
            out[is_base & above] = lit
        if shaded is not None:
            out[is_base & below & ~above] = shaded
    return out


def outline(grid, color, diagonal=False):
    """One-pixel outline around the silhouette."""
    filled = grid > 0
    edge = np.zeros_like(filled)
    edge[1:] |= filled[:-1]
    edge[:-1] |= filled[1:]
    edge[:, 1:] |= filled[:, :-1]
    edge[:, :-1] |= filled[:, 1:]
    if diagonal:
        edge[1:, 1:] |= filled[:-1, :-1]
        edge[1:, :-1] |= filled[:-1, 1:]
        edge[:-1, 1:] |= filled[1:, :-1]
        edge[:-1, :-1] |= filled[1:, 1:]
    out = grid.copy()
    out[edge & ~filled] = color
    return out


def to_surface(grid, palette):
    """Palette-index grid -> 32-bit RGBA pygame surface (index 0 = clear)."""
    h, w = grid.shape
    lut = np.zeros((len(palette), 4), np.uint8)
    for i, c in enumerate(palette):
        if i == 0 or c is None:
            continue
        lut[i, :3] = c[:3]
        lut[i, 3] = c[3] if len(c) > 3 else 255
    rgba = lut[grid]
    return pygame.image.frombuffer(np.ascontiguousarray(rgba).tobytes(), (w, h), "RGBA").copy()


# --- geometry helpers -----------------------------------------------------------

def lerp(a, b, t):
    return a + (b - a) * t


def rot(dx, dy, degrees):
    """Rotate a vector counter-clockwise on screen (y points down)."""
    a = math.radians(degrees)
    return dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)


def two_bone(root, target, upper, lower, bend):
    """Joint position for a two-segment limb reaching from ``root`` to
    ``target``; ``bend`` (+1/-1) picks which side the joint bulges to."""
    rx, ry = root
    tx, ty = target
    dx, dy = tx - rx, ty - ry
    d = math.hypot(dx, dy)
    d = max(1e-6, min(d, upper + lower - 1e-3))
    ux, uy = dx / max(1e-6, math.hypot(dx, dy)), dy / max(1e-6, math.hypot(dx, dy))
    a = (upper * upper - lower * lower + d * d) / (2 * d)
    hgt = math.sqrt(max(0.0, upper * upper - a * a))
    # Perpendicular to the reach direction, picked by ``bend``.
    px, py = -uy * bend, ux * bend
    return rx + ux * a + px * hgt, ry + uy * a + py * hgt


class Pose(dict):
    """A bag of named numbers (or tuples of numbers) that can be blended."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def with_(self, **changes):
        p = Pose(self)
        p.update(changes)
        return p

    def blend(self, other, t):
        out = Pose(self)
        for k, b in other.items():
            a = self.get(k, b)
            if isinstance(b, (int, float)) and isinstance(a, (int, float)) and not isinstance(b, bool):
                out[k] = lerp(a, b, t)
            elif isinstance(b, tuple) and isinstance(a, tuple) and len(a) == len(b):
                out[k] = tuple(lerp(x, y, t) for x, y in zip(a, b))
            else:
                out[k] = b if t >= 0.5 else a
        return out


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)
