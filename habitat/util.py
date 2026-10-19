"""Small math helpers and noise."""

import math

import numpy as np

# 4x4 ordered-dither thresholds in [0, 1): used to blend terrain tones the
# way pixel artists do by hand, instead of with smooth gradients.
BAYER4 = (np.array([[0, 8, 2, 10],
                    [12, 4, 14, 6],
                    [3, 11, 1, 9],
                    [15, 7, 13, 5]], dtype=np.float32) + 0.5) / 16.0


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def smoothstep(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def approach(value, target, max_step):
    if value < target:
        return min(target, value + max_step)
    return max(target, value - max_step)


def lerp_color(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def value_noise(width, height, cell, rng):
    """Smooth 2-D noise in [0, 1] with features roughly ``cell`` px across."""
    gw = width // cell + 3
    gh = height // cell + 3
    lattice = rng.random((gh, gw), dtype=np.float32)
    xs = np.arange(width, dtype=np.float32) / cell
    ys = np.arange(height, dtype=np.float32) / cell
    x0 = xs.astype(np.int32)
    y0 = ys.astype(np.int32)
    tx = xs - x0
    ty = ys - y0
    tx = tx * tx * (3 - 2 * tx)
    ty = ty * ty * (3 - 2 * ty)
    rows0 = lattice[y0]
    rows1 = lattice[y0 + 1]
    top = rows0[:, x0] + (rows0[:, x0 + 1] - rows0[:, x0]) * tx
    bottom = rows1[:, x0] + (rows1[:, x0 + 1] - rows1[:, x0]) * tx
    return top + (bottom - top) * ty[:, None]


def fbm(width, height, cell, rng, octaves=4, gain=0.5):
    total = np.zeros((height, width), dtype=np.float32)
    amplitude = 1.0
    norm = 0.0
    for _ in range(octaves):
        total += amplitude * value_noise(width, height, max(2, int(cell)), rng)
        norm += amplitude
        amplitude *= gain
        cell /= 2.0
    return total / norm


def dither_mask(height, width):
    """Bayer thresholds tiled over a height x width grid."""
    reps = (height // 4 + 1, width // 4 + 1)
    return np.tile(BAYER4, reps)[:height, :width]


class Noise1D:
    """Smooth 1-D value noise in [0, 1], used for wind gusts and drift."""

    def __init__(self, rng, size=256):
        self.values = [rng.random() for _ in range(size)]
        self.size = size

    def __call__(self, t):
        i = math.floor(t)
        f = t - i
        f = f * f * (3 - 2 * f)
        a = self.values[i % self.size]
        b = self.values[(i + 1) % self.size]
        return a + (b - a) * f
