"""Tunables.  Distances are in art pixels, times in seconds."""

FPS = 60
DEFAULT_WINDOW = (1280, 800)

# Every sprite is drawn at one integer zoom so all pixel art shares a grid.
# The zoom is picked from the window height; roughly this many art pixels
# fit vertically.
ART_ROWS_TARGET = 280
MIN_ZOOM, MAX_ZOOM = 2, 8

# The cat ---------------------------------------------------------------
CAT_WALK_SPEED = 26.0
CAT_STALK_SPEED = 11.0
CAT_TROT_SPEED = 48.0
CAT_RUN_SPEED = 96.0
# Stride lengths for gait playback come from the drawn cycles themselves
# (habitat/cat_anims.py STRIDES).
# Where the cat's feet touch the ground inside its 64x64 frame; every
# animation is drawn on the same canvas.
CAT_ANCHOR = (32, 48)

# Needs drain/fill per real second (1.0 = full).
NEED_RATES = {
    "energy_awake": -1 / 720,     # ~12 min from rested to sleepy
    "energy_active": -1 / 300,    # running, hunting
    "energy_sleep": 1 / 200,      # ~3.5 min nap restores fully
    "hunger": 1 / 1500,
    "thirst": 1 / 1100,
    "groom": 1 / 420,
    "play": 1 / 260,
}

# World -------------------------------------------------------------------
EDGE_MARGIN_X = 24
EDGE_MARGIN_TOP = 34
EDGE_MARGIN_BOTTOM = 10

# The bowl is refilled at these hours (someone comes out with food).
MEAL_TIMES = (7.5, 18.0)

# Time & weather ----------------------------------------------------------
WEATHER_MIN_HOLD = 240.0   # real seconds a weather state lasts at least
WEATHER_MAX_HOLD = 600.0
WEATHER_BLEND = 45.0       # seconds to ease between weather states
