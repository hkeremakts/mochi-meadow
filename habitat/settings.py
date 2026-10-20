"""The meadow's tuning, in one place.

Every number that decides how the meadow *feels* (weather lengths, how
often encounters happen, Mochi's rhythms, frame rates) lives in
``defaults.toml`` next to this file, with a comment saying what it does.
A settings file of your own can change any of them: it only needs the
values you want different, in the same sections.

    from .settings import SETTINGS
    SETTINGS["weather"]["blend"]          # 45

Drawing numbers (poses, shapes, palettes) stay with the drawing code,
where they make sense.
"""

import copy
import os
import sys
import tomllib

# Tables keyed by event name, where a settings file may add names.
OPEN_TABLES = {"events.cooldown_minutes", "events.omen_seconds"}
DEFAULTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "defaults.toml")


def user_path():
    """Where a settings file of your own is looked for."""
    override = os.environ.get("MEADOW_SETTINGS")
    if override:
        return override
    from .journal import default_path
    return os.path.join(os.path.dirname(default_path()), "settings.toml")


def _merge(base, extra, where, problems):
    """Copy ``extra`` over ``base``, keeping only known keys whose values
    have the right shape; problems are collected rather than raised."""
    for key, value in extra.items():
        name = f"{where}.{key}" if where else key
        if key not in base:
            if where in OPEN_TABLES and _number(value):
                base[key] = value          # a table of event names may name any event
                continue
            problems.append(f"unknown setting {name}")
            continue
        current = base[key]
        if isinstance(current, dict):
            if isinstance(value, dict):
                _merge(current, value, name, problems)
            else:
                problems.append(f"{name} should be a table")
        elif isinstance(current, list):
            if isinstance(value, list) and len(value) == len(current) and all(_number(v) for v in value):
                base[key] = value
            else:
                problems.append(f"{name} should be a list like {current}")
        elif _number(current):
            if _number(value):
                base[key] = value
            else:
                problems.append(f"{name} should be a number")
        else:
            base[key] = value


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def load(path=None, quiet=False):
    """The defaults, with the user's file (if any) on top.  A broken or
    odd user file never stops the meadow: its problems are reported and
    the defaults stand."""
    with open(DEFAULTS_PATH, "rb") as f:
        settings = tomllib.load(f)
    path = path or user_path()
    problems = []
    if path and os.path.exists(path):
        try:
            with open(path, "rb") as f:
                mine = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError) as e:
            problems.append(f"couldn't read {path}: {e}")
        else:
            _merge(settings, mine, "", problems)
    if problems and not quiet:
        for p in problems:
            print(f"meadow settings: {p}", file=sys.stderr)
    return settings


def defaults():
    return copy.deepcopy(DEFAULTS)


DEFAULTS = load(path=os.devnull, quiet=True)
SETTINGS = load()
