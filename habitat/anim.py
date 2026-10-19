"""Sprite sequence playback.

A clip is driven either by time (``fps``) or by distance travelled
(``stride`` = art pixels covered by one full cycle).  Distance-driven clips
only advance while their owner moves, which is what keeps paws planted: a
cat that stops mid-stride freezes mid-stride instead of moonwalking.

There is deliberately no cross-fading.  Alpha-blending two frames of
limited-palette pixel art produces a translucent double image, so clip
changes are clean cuts.
"""


class Animator:
    def __init__(self):
        self.key = None
        self.frames = ()
        self.fps = 0.0
        self.stride = None
        self.loop = True
        self.phase = 0.0  # position measured in frames
        self.done = False

    def play(self, key, frames, *, fps=None, stride=None, loop=True,
             keep_phase=False, restart=False):
        if key == self.key and not restart:
            # Same clip: only retune its speed so callers can call play()
            # every tick without rewinding the sequence.
            self.fps = fps or 0.0
            self.stride = stride
            return
        fraction = 0.0
        if keep_phase and self.frames:
            fraction = self.phase / len(self.frames)
        self.key = key
        self.frames = frames
        self.fps = fps or 0.0
        self.stride = stride
        self.loop = loop
        self.phase = fraction * len(frames)
        self.done = False

    def update(self, dt, distance=0.0):
        count = len(self.frames)
        if not count or self.done:
            return
        if self.stride:
            self.phase += abs(distance) / self.stride * count
        else:
            self.phase += dt * self.fps
        if self.loop:
            self.phase %= count
        elif self.phase >= count:
            self.phase = float(count)
            self.done = True

    @property
    def index(self):
        if not self.frames:
            return 0
        return min(int(self.phase), len(self.frames) - 1)

    @property
    def frame(self):
        if not self.frames:
            return None
        return self.frames[self.index]
