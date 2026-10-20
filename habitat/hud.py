"""On-screen text: an optional info panel and a fading key guide."""

import pygame

MOON_NAMES = ((0.03, "new moon"), (0.22, "waxing crescent"), (0.28, "first quarter"), (0.47, "waxing gibbous"),
              (0.53, "full moon"), (0.72, "waning gibbous"), (0.78, "last quarter"), (0.97, "waning crescent"),
              (1.01, "new moon"))
PLURALS = {"butterfly": "butterflies", "mouse": "mice", "firefly": "fireflies", "ladybug": "ladybirds",
           "dragonfly": "dragonflies", "pigeon": "pigeons", "sparrow": "sparrows", "frog": "frogs",
           "bee": "bees", "snail": "snails", "hedgehog": "hedgehogs", "crow": "crows", "bat": "bats",
           "fox": "foxes", "golden_butterfly": "golden butterflies", "visitor": "visiting cats", "deer": "deer",
           "heron": "herons", "duck": "ducks", "duckling": "ducklings", "moth": "moths",
           "grasshopper": "grasshoppers"}
SINGULAR = {"ladybug": "ladybird", "golden_butterfly": "golden butterfly", "visitor": "visiting cat"}
KEYS = [
    ("I", "info panel"),
    ("F", "fullscreen"),
    ("T", "time speed"),
    ("W", "next weather"),
    ("J", "journal"),
    ("D", "event odds"),
    ("N", "new meadow"),
    ("S", "screenshot"),
    ("Esc", "quit"),
]


def moon_name(age):
    for limit, name in MOON_NAMES:
        if age < limit:
            return name
    return "new moon"


def _hm(hours):
    if hours is None:
        return "--:--"
    minutes = int(round(hours * 60)) % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# Caption colours by rarity, and the mark that goes before them.
TIER_STYLE = {           # colour, number of stars drawn before the text
    "uncommon": ((226, 232, 238), 0),
    "rare": ((255, 214, 120), 1),
    "legendary": ((236, 190, 255), 2),
}


def _star(surface, cx, cy, r, color):
    """A four-pointed sparkle (the default font has no star glyph)."""
    k = r * 0.32
    pts = [(cx, cy - r), (cx + k, cy - k), (cx + r, cy), (cx + k, cy + k),
           (cx, cy + r), (cx - k, cy + k), (cx - r, cy), (cx - k, cy - k)]
    pygame.draw.polygon(surface, color, pts)


class Hud:
    def __init__(self, screen_height):
        self.resize(screen_height)
        self.guide_time = 7.0

    def resize(self, screen_height):
        size = max(14, int(screen_height / 44))
        self.font = pygame.font.Font(None, int(size * 1.25))
        self.small = pygame.font.Font(None, int(size * 1.05))
        self.caption_font = pygame.font.Font(None, int(size * 1.6))
        self.pad = max(8, size // 2)
        self._caption_cache = {}

    def update(self, dt):
        self.guide_time = max(0.0, self.guide_time - dt)

    def show_guide(self):
        self.guide_time = 6.0

    def _panel(self, screen, lines, anchor, alpha=150):
        rendered = [(font.render(text, True, color)) for text, font, color in lines]
        w = max(r.get_width() for r in rendered) + self.pad * 2
        h = sum(r.get_height() for r in rendered) + self.pad * 2 + (len(rendered) - 1) * 3
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (12, 16, 22, alpha), panel.get_rect(), border_radius=self.pad)
        y = self.pad
        for r in rendered:
            panel.blit(r, (self.pad, y))
            y += r.get_height() + 3
        sw, sh = screen.get_size()
        margin = self.pad * 2
        if anchor == "bottomleft":
            pos = (margin, sh - h - margin)
        elif anchor == "topleft":
            pos = (margin, margin)
        else:
            pos = (sw - w - margin, margin)
        screen.blit(panel, pos)

    def draw_info(self, screen, world, speed):
        env = world.env
        cat = world.cat
        light = (236, 238, 240)
        dim = (176, 186, 196)
        sky = env.sky
        time_line = f"{env.clock.label}   {env.weather_name}   {env.temperature:.0f}°C   {env.season}"
        if speed != 1:
            time_line += f"   time x{speed:g}"
        counts = []
        for kind in ("golden_butterfly", "deer", "visitor", "fox", "heron", "duck", "duckling", "butterfly", "bee", "dragonfly", "ladybug", "frog", "snail",
                     "mouse", "hedgehog", "pigeon", "sparrow", "crow", "bat", "grasshopper", "moth", "firefly"):
            n = world.count(kind)
            if n:
                name = PLURALS[kind] if n > 1 else SINGULAR.get(kind, kind)
                counts.append(f"{n} {name}")
        n = cat.needs
        needs = f"energy {n.energy:.0%}   hunger {n.hunger:.0%}   thirst {n.thirst:.0%}"
        day = sky.day
        sun_line = f"sunrise {_hm(day.sunrise)}   sunset {_hm(day.sunset)}   {moon_name(sky.moon_age)}"
        p = cat.p
        quirks = ", ".join(p.quirks)
        who = f"{cat.name}: {p.describe()}" + (f"; {quirks}" if quirks else "") + f"; feeling {p.mood_word}"
        lines = [
            (time_line, self.font, light),
            (sun_line, self.small, dim),
            (f"{cat.name} is {cat.label}", self.font, light),
            (who, self.small, dim),
            ("  ·  ".join(counts) if counts else "the meadow is quiet", self.small, dim),
            (needs, self.small, dim),
        ]
        self._panel(screen, lines, "bottomleft")

    def draw_captions(self, screen, captions, total):
        """The newest caption, low and centred: it fades in, holds, fades
        out, and drifts up a little so nothing sits still on the screen."""
        if not captions:
            return
        c = captions[-1]
        color, stars = TIER_STYLE.get(c.tier, TIER_STYLE["uncommon"])
        key = (c.text, c.tier)
        img = self._caption_cache.get(key)
        if img is None:
            if len(self._caption_cache) > 32:
                self._caption_cache.clear()
            text = self.caption_font.render(c.text, True, color)
            shadow = self.caption_font.render(c.text, True, (10, 12, 16))
            h = text.get_height()
            r = h * 0.3
            lead = int(stars * r * 2.4 + (r if stars else 0))
            img = pygame.Surface((lead + text.get_width() + 2, h + 2), pygame.SRCALPHA)
            for i in range(stars):
                cx = r * 1.2 + i * r * 2.4
                _star(img, cx + 2, h / 2 + 2, r, (10, 12, 16))
                _star(img, cx, h / 2, r, color)
            img.blit(shadow, (lead + 2, 2))
            img.blit(text, (lead, 0))
            self._caption_cache[key] = img
        fade_in, fade_out = 1.5, 2.5
        alpha = min(1.0, c.age / fade_in, (total - c.age) / fade_out)
        if alpha <= 0:
            return
        img.set_alpha(int(255 * alpha))
        sw, sh = screen.get_size()
        rise = int(c.age * 2)
        screen.blit(img, ((sw - img.get_width()) // 2, int(sh * 0.86) - img.get_height() - rise))

    def draw_journal(self, screen, events):
        """Every event, rarest first; the ones not yet seen are '???'."""
        from .events import ALL, TIERS
        light, dim = (236, 238, 240), (150, 160, 172)
        lines = [("Journal", self.font, light)]
        p = events.world.cat.p
        from .personality import QUIRKS
        lines.append((f"{events.world.cat.name} is {p.describe()}", self.small, light))
        for q in p.quirks:
            lines.append((f"   {QUIRKS[q]}", self.small, dim))
        level = p.friendship("ginger")
        if events.journal_count("the ginger cat"):
            bond = "best friends" if level >= 4 else "friends" if level >= 2 else "getting to know each other" \
                if level >= 0 else "not on speaking terms"
            lines.append((f"   and the ginger cat: {bond}", self.small, dim))
        for tier in reversed(TIERS):
            names = [n for n, e in ALL.items() if e.tier == tier]
            color, _ = TIER_STYLE.get(tier, ((200, 206, 212), 0))
            lines.append((f"{tier}", self.small, color))
            for name in sorted(names):
                n = events.journal_count(name)
                text = f"   {name}  \u00d7{n}" if n else "   ???"
                lines.append((text, self.small, light if n else dim))
        self._panel(screen, lines, "topright")

    def draw_debug(self, screen, world):
        """Behind the scenes, for tuning: each tier's wait and odds, what
        could happen right now, and what is running."""
        from .events import MEAN, ROLLED, TIERS
        ev = world.events
        light, dim = (236, 238, 240), (150, 160, 172)
        lines = [("Events", self.font, light)]
        now = world.time
        for tier in reversed(TIERS):
            wait = ev.since[tier] / MEAN[tier]
            per_hour = ev.chance(tier) * 3600 / 4.0
            ready = [e.name for e in ROLLED if e.tier == tier and now >= ev.ready_at.get(e.name, 0.0)
                     and e.ready(world)]
            color = TIER_STYLE.get(tier, ((200, 206, 212), 0))[0]
            lines.append((f"{tier}: {wait:.0%} of the usual wait, ~{per_hour:.1f}/h", self.small, color))
            lines.append(("   " + (", ".join(ready) if ready else "nothing possible now"), self.small, dim))
        running = [type(fx).__name__ for fx in world.effects]
        if ev.pending:
            running.append(f"omen for {ev.pending[0].name}")
        lines.append(("running: " + (", ".join(running) if running else "-"), self.small, dim))
        recent = [n for _, n in ev.history[-4:]]
        lines.append(("recent: " + (", ".join(recent) if recent else "-"), self.small, dim))
        p = world.cat.p
        lines.append((f"{world.cat.name}: mood {p.mood:+.2f} ({p.mood_word}), activity {world.cat.activity_name}",
                      self.small, dim))
        self._panel(screen, lines, "topleft")

    def draw_guide(self, screen):
        if self.guide_time <= 0:
            return
        alpha = int(min(1.0, self.guide_time / 1.5) * 255)
        lines = [(f"{key:>4}   {what}", self.small, (230, 234, 238)) for key, what in KEYS]
        surf_alpha = min(150, alpha)
        rendered = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        self._panel(rendered, lines, "topright", alpha=surf_alpha)
        rendered.set_alpha(alpha)
        screen.blit(rendered, (0, 0))
