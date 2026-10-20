"""Layout constants, and the tuning values other modules import by name.

The tuning values themselves (frame rates, Mochi's speeds and needs, meal
times, weather lengths) come from the settings (habitat/defaults.toml, and
a settings file of your own).  Distances are in art pixels, times in
seconds.
"""

from .settings import SETTINGS

_screen = SETTINGS["screen"]
_mochi = SETTINGS["mochi"]
_weather = SETTINGS["weather"]

FPS = _screen["fps"]
DEFAULT_WINDOW = tuple(_screen["window"])

# Every sprite is drawn at one integer zoom so all pixel art shares a grid.
# The zoom is picked from the window height; roughly this many art pixels
# fit vertically.
ART_ROWS_TARGET = _screen["art_rows"]
MIN_ZOOM, MAX_ZOOM = _screen["min_zoom"], _screen["max_zoom"]

# The cat ---------------------------------------------------------------
CAT_WALK_SPEED = float(_mochi["walk_speed"])
CAT_STALK_SPEED = float(_mochi["stalk_speed"])
CAT_TROT_SPEED = float(_mochi["trot_speed"])
CAT_RUN_SPEED = float(_mochi["run_speed"])
# Stride lengths for gait playback come from the drawn cycles themselves
# (habitat/cat_anims.py STRIDES).
# Where the cat's feet touch the ground inside its 64x64 frame; every
# animation is drawn on the same canvas.
CAT_ANCHOR = (32, 48)

# Needs drain (-) or fill (+) per real second (1.0 = full).
_needs = _mochi["needs"]
NEED_RATES = {
    "energy_awake": -1 / _needs["energy_awake"],
    "energy_active": -1 / _needs["energy_active"],
    "energy_sleep": 1 / _needs["energy_sleep"],
    "hunger": 1 / _needs["hunger"],
    "thirst": 1 / _needs["thirst"],
    "groom": 1 / _needs["groom"],
    "play": 1 / _needs["play"],
}

# World -------------------------------------------------------------------
EDGE_MARGIN_X = 24
EDGE_MARGIN_TOP = 34
EDGE_MARGIN_BOTTOM = 10

# The bowl is refilled at these hours (someone comes out with food).
MEAL_TIMES = tuple(SETTINGS["meals"]["times"])
