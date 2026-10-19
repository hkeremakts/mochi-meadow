"""Loading sprite art from ``assets/``.

Everything is normalised to 32-bit RGBA surfaces at native art resolution.
Scaling to the screen happens once per sprite in the renderer's cache, never
here, so every piece of art is drawn at the same integer pixel size.
"""

import hashlib
import os
import shutil
import re

import pygame

ASSET_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def natural_key(name):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


def anim_key(folder_name):
    """'walk(right)' -> 'walk_right', 'tail_wag(sit_front)' -> 'tail_wag_sit_front'."""
    return folder_name.replace("(", "_").replace(")", "").replace("-", "_").replace(" ", "_")


def to_rgba(image):
    """An exact 32-bit RGBA copy; works before a display mode exists."""
    if image.get_bitsize() == 32 and image.get_flags() & pygame.SRCALPHA:
        return image.copy()
    out = pygame.Surface(image.get_size(), pygame.SRCALPHA, 32)
    out.fill((0, 0, 0, 0))
    out.blit(image, (0, 0))
    return out


def remove_islands(surface, keep_ratio=0.15):
    """Erase small specks that are detached from the main shape.

    Sheet slicing can leave fragments of neighbouring labels in a frame.
    Any connected part smaller than ``keep_ratio`` of the largest part is
    treated as debris; larger detached parts are kept as real art.
    """
    parts = pygame.mask.from_surface(surface, 0).connected_components()
    if len(parts) <= 1:
        return surface
    biggest = max(p.count() for p in parts)
    out = surface.copy()
    for part in parts:
        if part.count() >= keep_ratio * biggest:
            continue
        for rect in part.get_bounding_rects():
            for y in range(rect.top, rect.bottom):
                for x in range(rect.left, rect.right):
                    if part.get_at((x, y)):
                        out.set_at((x, y), (0, 0, 0, 0))
    return out


def load_image(path):
    return to_rgba(pygame.image.load(path))


def load_frames(folder):
    """All PNGs in ``folder`` in numeric order, cleaned of stray specks."""
    if not os.path.isdir(folder):
        return []
    names = sorted((n for n in os.listdir(folder) if n.lower().endswith(".png")), key=natural_key)
    return [remove_islands(load_image(os.path.join(folder, n))) for n in names]


FLAT_FRAME = re.compile(r"^(.+)_(\d+)\.png$", re.IGNORECASE)


def load_animation_folders(root):
    """Map each animation under ``root`` to its frames, keyed by anim_key().

    Two layouts are understood: a folder per animation (``walk(right)/``),
    and flat numbered files as written by tools/slice_labeled_sheet.py
    (``walk_right_01.png``).  A folder wins if both exist."""
    library = {}
    if not os.path.isdir(root):
        return library
    flat = {}
    for entry in sorted(os.listdir(root)):
        path = os.path.join(root, entry)
        if os.path.isdir(path):
            frames = load_frames(path)
            if frames:
                library[anim_key(entry)] = frames
        else:
            match = FLAT_FRAME.match(entry)
            if match:
                flat.setdefault(anim_key(match.group(1)), []).append((int(match.group(2)), path))
    for key, numbered in flat.items():
        if key not in library:
            library[key] = [remove_islands(load_image(p)) for _, p in sorted(numbered)]
    return library


GENERATED_ROOT = os.path.join(ASSET_ROOT, "generated")


def _stamp(sources):
    digest = hashlib.sha256()
    for path in sources:
        with open(path, "rb") as f:
            digest.update(f.read())
    return digest.hexdigest()


def generated_library(name, sources, build, root=GENERATED_ROOT):
    """Sprites drawn by code, cached as PNG folders under ``root/name``.

    ``build()`` returns {key: [Surface, ...]}.  The cache is reused until
    one of the ``sources`` (the drawing code) changes.  Frames are loaded
    as drawn: no speck cleanup, since single pixels (whiskers) are art."""
    folder = os.path.join(root, name)
    stamp_path = os.path.join(folder, "stamp.txt")
    stamp = _stamp(sources)
    try:
        with open(stamp_path) as f:
            fresh = f.read().strip() == stamp
    except OSError:
        fresh = False
    if fresh:
        library = {}
        for key in sorted(os.listdir(folder)):
            path = os.path.join(folder, key)
            if os.path.isdir(path):
                names = sorted((n for n in os.listdir(path) if n.endswith(".png")), key=natural_key)
                library[key] = [load_image(os.path.join(path, n)) for n in names]
        return library
    library = build()
    try:
        if os.path.isdir(folder):
            shutil.rmtree(folder)
        for key, frames in library.items():
            os.makedirs(os.path.join(folder, key), exist_ok=True)
            for i, frame in enumerate(frames):
                pygame.image.save(frame, os.path.join(folder, key, f"{i:02d}.png"))
        with open(stamp_path, "w") as f:
            f.write(stamp)
    except OSError:
        pass  # read-only install: draw again next time
    return library
