"""Common shape of everything that lives in the meadow."""

from ..anim import Animator


class Entity:
    kind = "thing"

    def __init__(self, world, x, y):
        self.world = world
        self.x = float(x)
        self.y = float(y)
        self.z = 0.0  # height above the ground; the shadow stays at (x, y)
        self.alive = True
        self.anim = Animator()

    def update(self, dt):
        pass

    def sprite(self):
        """(surface, (anchor_x, anchor_y), flip) or None.  The anchor is the
        point in the sprite that sits on (x, y - z)."""
        return None

    def shadow(self):
        """(radius_x, radius_y, alpha) of the contact shadow, or None."""
        return None

    def glow(self):
        """(radius, (r, g, b)) light added to the scene at night, or None."""
        return None

    @property
    def airborne(self):
        return self.z > 3.0

    def distance_to(self, other):
        dx = other.x - self.x
        dy = other.y - self.y
        return (dx * dx + dy * dy) ** 0.5
