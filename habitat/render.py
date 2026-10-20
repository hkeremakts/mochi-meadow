"""Drawing the meadow.

All art shares one integer zoom ``S`` so every sprite sits on the same pixel
grid, but moving things are placed at screen-pixel precision so motion
stays smooth.  Static ground is upscaled once; sprites are cropped to their
visible pixels and upscaled once each, then cached.

Lighting is a single multiply pass: an art-resolution light map holding the
time-of-day colour, cloud shadows, the vignette and glows, upscaled and
multiplied over the frame.
"""

import math

import numpy as np
import pygame

from .util import BAYER4, smoothstep

# Small generated sprites (dots, glows) are cached by colour; colours are
# quantised, and this cap guarantees the caches stay bounded in a
# screensaver that runs for days.
CACHE_LIMIT = 1024


class Renderer:
    def __init__(self, screen, zoom):
        self.screen = screen
        self.S = zoom
        self.world = None
        self._sprites = {}
        self._dots = {}
        self._rings = {}
        self._shadows = {}
        self._streaks = {}
        self._splashes = None
        self._glows = {}

    # --- setup ------------------------------------------------------------

    def bind(self, world, screen=None):
        if screen is not None:
            self.screen = screen
        self.world = world
        S = self.S
        w, h = world.width, world.height
        self._bake_ground(world)
        self._prop_frames = self._scenery_frames(world)
        self.light_small = pygame.Surface((w, h)).convert()
        self.light_big = pygame.Surface((w * S, h * S)).convert()
        self.vignette = self._vignette(w, h)
        for frame in self._prop_frames:
            self.sprite(frame)

    def _bake_ground(self, world):
        S = self.S
        self.ground = pygame.transform.scale(world.terrain.ground, (world.width * S, world.height * S)).convert()
        self.scenery_version = world.scenery_version

    def _refresh_scenery(self, world):
        """The season moved on: new ground, new prop frames."""
        self._bake_ground(world)
        old = self._prop_frames
        self._prop_frames = self._scenery_frames(world)
        for key in [k for k in self._sprites if k[0] in old and k[0] not in self._prop_frames]:
            del self._sprites[key]
        for frame in self._prop_frames:
            self.sprite(frame)

    @staticmethod
    def _scenery_frames(world):
        t = world.terrain
        return {f for prop in t.props + t.canopies for f in prop.frames}

    def clear_caches(self):
        for cache in (self._sprites, self._dots, self._rings, self._shadows, self._streaks, self._glows):
            cache.clear()
        self._splashes = None

    def _vignette(self, w, h):
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / math.sqrt(2)
        t = np.clip((d - 0.42) / 0.58, 0.0, 1.0)
        v = 1.0 - 0.36 * t * t * (3 - 2 * t)
        bayer = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w]
        values = np.clip(v * 255.0 + (bayer - 0.5) * 5.0, 0, 255).astype(np.uint8)
        rgb = np.dstack([values, values, values])
        return pygame.surfarray.make_surface(np.ascontiguousarray(rgb.swapaxes(0, 1))).convert()

    # --- cached art ---------------------------------------------------------

    def sprite(self, surf, flip=False):
        """(scaled surface, crop_x, crop_y) for an art-res surface."""
        key = (surf, flip)
        hit = self._sprites.get(key)
        if hit is None:
            src = pygame.transform.flip(surf, True, False) if flip else surf
            box = src.get_bounding_rect()
            if box.width == 0 or box.height == 0:
                box = pygame.Rect(0, 0, 1, 1)
            cropped = src.subsurface(box)
            S = self.S
            scaled = pygame.transform.scale(cropped, (box.width * S, box.height * S)).convert_alpha()
            hit = (scaled, box.x, box.y)
            self._sprites[key] = hit
        return hit

    def dot(self, color, alpha, w=1, h=1):
        alpha = max(0, min(255, (int(alpha) // 16) * 16 + 15))
        color = tuple((int(c) // 8) * 8 for c in color)
        key = (color, alpha, w, h)
        hit = self._dots.get(key)
        if hit is None:
            if len(self._dots) > CACHE_LIMIT:
                self._dots.clear()
            hit = pygame.Surface((w * self.S, h * self.S), pygame.SRCALPHA)
            hit.fill((*color, alpha))
            self._dots[key] = hit
        return hit

    def ring(self, radius, alpha):
        radius = max(1, radius)
        alpha = (int(alpha) // 32) * 32 + 31
        key = (radius, alpha)
        hit = self._rings.get(key)
        if hit is None:
            small = pygame.Surface((radius * 2 + 1, radius + 1), pygame.SRCALPHA)
            pygame.draw.ellipse(small, (176, 214, 220, alpha), small.get_rect(), 1)
            hit = pygame.transform.scale(small, (small.get_width() * self.S, small.get_height() * self.S))
            self._rings[key] = hit
        return hit

    def shadow_sprite(self, rx, ry, alpha):
        rx = max(1, int(round(rx)))
        ry = max(1, int(round(ry)))
        alpha = (int(alpha) // 16) * 16
        key = (rx, ry, alpha)
        hit = self._shadows.get(key)
        if hit is None:
            small = pygame.Surface((rx * 2, ry * 2), pygame.SRCALPHA)
            pygame.draw.ellipse(small, (14, 18, 26, alpha), small.get_rect())
            hit = pygame.transform.scale(small, (rx * 2 * self.S, ry * 2 * self.S))
            self._shadows[key] = hit
        return hit

    def rain_streak(self, slant, fine=False):
        """A falling drop: a long bright streak, or (``fine``, drizzle) a
        short, faint one."""
        key = (int(round(slant * 2)), fine)
        hit = self._streaks.get(key)
        if hit is None:
            S = self.S
            length = (4 if fine else 7) * S
            dx = key[0] * S * (4 if fine else 7) // 7
            thick = max(1, S // 3) if fine else max(1, S // 2)
            w = abs(dx) + thick + 1
            hit = pygame.Surface((w, length), pygame.SRCALPHA)
            x0 = 0 if dx >= 0 else w - 1
            color = (214, 224, 238, 150) if fine else (206, 218, 236, 175)
            pygame.draw.line(hit, color, (x0 + dx, 0), (x0, length - 1), thick)
            self._streaks[key] = hit
        return hit

    def splash_sprite(self, t):
        if self._splashes is None:
            frames = []
            for pattern in (["-x-", "x-x"], ["x---x", "-x-x-"]):
                small = pygame.Surface((len(pattern[0]), 2), pygame.SRCALPHA)
                for y, row in enumerate(pattern):
                    for x, ch in enumerate(row):
                        if ch == "x":
                            small.set_at((x, y), (200, 214, 232, 170))
                frames.append(pygame.transform.scale(small, (small.get_width() * self.S, 2 * self.S)))
            self._splashes = frames
        return self._splashes[0 if t < 0.5 else 1]

    def glow_sprite(self, radius, color):
        color = tuple((c // 8) * 8 for c in color)
        key = (radius, color)
        hit = self._glows.get(key)
        if hit is None:
            if len(self._glows) > CACHE_LIMIT:
                self._glows.clear()
            size = radius * 2 + 1
            yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
            d = np.sqrt((xx - radius) ** 2 + (yy - radius) ** 2) / max(1, radius)
            k = np.clip(1.0 - d, 0.0, 1.0) ** 1.8
            rgb = np.dstack([k * color[0], k * color[1], k * color[2]]).astype(np.uint8)
            hit = pygame.surfarray.make_surface(np.ascontiguousarray(rgb.swapaxes(0, 1)))
            self._glows[key] = hit
        return hit

    def glow_sprite_scaled(self, radius, color):
        color = tuple((c // 8) * 8 for c in color)
        key = ("scaled", radius, color)
        hit = self._glows.get(key)
        if hit is None:
            small = self.glow_sprite(radius, color)
            hit = pygame.transform.scale(small, (small.get_width() * self.S, small.get_height() * self.S))
            self._glows[key] = hit
        return hit

    # --- placing art -----------------------------------------------------

    def blit_px(self, img, x, y, add=False):
        S = self.S
        if add:
            self.screen.blit(img, (round(x * S), round(y * S)), special_flags=pygame.BLEND_ADD)
        else:
            self.screen.blit(img, (round(x * S), round(y * S)))

    def draw_sprite(self, surf, x, y, anchor, flip=False):
        img, ox, oy = self.sprite(surf, flip)
        ax, ay = anchor
        if flip:
            ax = surf.get_width() - ax
        S = self.S
        self.screen.blit(img, (round((x - ax + ox) * S), round((y - ay + oy) * S)))

    # --- the frame -------------------------------------------------------

    def draw(self, world):
        if world.scenery_version != self.scenery_version:
            self._refresh_scenery(world)
        screen = self.screen
        screen.blit(self.ground, (0, 0))
        world.water.draw(self)
        for fx in world.effects:
            fx.draw_ground(self)

        for e in world.entities:
            sh = e.shadow()
            if sh:
                rx, ry, alpha = sh[0], sh[1], sh[2]
                dy = sh[3] if len(sh) > 3 else 0
                self.blit_px(self.shadow_sprite(rx, ry, alpha), e.x - round(rx), e.y + dy - round(ry))

        wind = world.env.wind
        ground_items = []
        for prop in world.terrain.props:
            if not prop.hidden:
                ground_items.append((prop.y, 0, prop))
        flying = []
        for e in world.entities:
            if e.airborne:
                flying.append(e)
            else:
                ground_items.append((e.y, 1, e))
        ground_items.sort(key=lambda item: (item[0], item[1]))
        for _, is_entity, obj in ground_items:
            if is_entity:
                self._draw_entity(obj)
            else:
                frames = obj.frames
                if len(frames) > 1:
                    lean = wind.sway(obj.x, obj.y, obj.phase) * obj.sway
                    frame = frames[int(round((lean + 1.0) * 0.5 * (len(frames) - 1)))]
                else:
                    frame = frames[0]
                self.draw_sprite(frame, obj.x, obj.y, obj.anchor)
        # Tree crowns over everything on the ground; see-through over the cat.
        for canopy in world.terrain.canopies:
            img, ox, oy = self.sprite(canopy.frames[0])
            ax, ay = canopy.anchor
            lean = wind.sway(canopy.x, canopy.y, canopy.phase) * canopy.sway
            img.set_alpha(int(255 * canopy.fade))
            self.screen.blit(img, (round((canopy.x - ax + ox + lean) * self.S), round((canopy.y - ay + oy) * self.S)))
        flying.sort(key=lambda e: e.y)
        for e in flying:
            self._draw_entity(e)

        world.particles.draw(self)
        for fx in world.effects:
            fx.draw(self)
        self._light(world)
        self._glow_pass(world)

    def _draw_entity(self, e):
        spr = e.sprite()
        if spr is not None:
            surf, anchor, flip = spr
            self.draw_sprite(surf, e.x, e.y - e.z, anchor, flip)

    def _light(self, world):
        env = world.env
        light = self.light_small
        light.fill(env.ambient())
        sun = env.sun
        if sun > 0.55 and env.rain < 0.1:  # no direct sun, no distinct cloud shadows
            for x, y, shape, _ in env.clouds.clouds:
                light.blit(shape, (round(x), round(y)), special_flags=pygame.BLEND_MULT)
        for shade in world.overhead:
            shade.draw_shadow(light)
        light.blit(self.vignette, (0, 0), special_flags=pygame.BLEND_MULT)
        if sun < 0.6:
            dark = 1.0 - smoothstep(sun / 0.6)
            for e in world.entities:
                g = e.glow()
                if g:
                    radius, color = g
                    c = (int(color[0] * dark), int(color[1] * dark), int(color[2] * dark))
                    img = self.glow_sprite(radius, c)
                    light.blit(img, (round(e.x - radius), round(e.y - e.z - radius)), special_flags=pygame.BLEND_ADD)
        pygame.transform.scale(light, self.light_big.get_size(), self.light_big)
        self.screen.blit(self.light_big, (0, 0), special_flags=pygame.BLEND_MULT)

    def _glow_pass(self, world):
        world.water.draw_glow(self)
        for fx in world.effects:
            fx.draw_glow(self)
        for e in world.entities:
            draw = getattr(e, "draw_glow", None)
            if draw is not None:
                draw(self)
