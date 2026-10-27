# Meadow (mochi-meadow)

A pixel-art cat called Mochi lives in a procedurally grown meadow that follows
the real sky, seasons and clock. It is meant to end up as a lightweight macOS
screensaver. Public repo: https://github.com/hkeremakts/mochi-meadow (MIT).

The README describes every feature. `docs/LOGBOOK.md` records what was decided,
when and why. Read it before re-proposing something that was already settled.

## Standing rules from the owner

- **Natural first.** Behaviour and visuals should feel like a real meadow and a
  real cat. Avoid fixed timers and hard on/off hours. Use the distributions in
  `habitat/chance.py` instead (see the logbook entry for 2026-10-20).
- **Light on CPU and battery.** It's a screensaver; if it drains power nobody
  keeps it. Measure CPU before and after anything that draws more. Screensaver
  mode currently runs at about 8–11% of one core. Prefer baking changes into the
  ground image over drawing something every frame.
- **Screensaver constraints come first.** It can't be interactive, can't rely on
  Location Services or (unverified) the network, and must be readable at a
  glance. Ideas a screensaver can't support are parked until after the Swift
  version.
- **No Swift until asked.** The native `.saver` rewrite (Swift + SpriteKit, with
  Python kept as the art studio exporting sprite sheets) is deferred to the very
  end. A question like "can we rewrite in Swift?" asks for a recommendation; it
  doesn't mean go ahead.
- **Propose, then build.** The owner likes to hear the ideas first and pick
  them ("I will tell you if they are good or bad").
- Don't touch the owner's real journal at
  `~/Library/Application Support/Meadow/journal.json`. Tests point
  `MEADOW_JOURNAL` at a temp file (`tests/__init__.py`).
- `test.py` at the root is the owner's scratch experiment. Leave it alone.

## Setup and commands

```bash
python3.12 -m venv venv && source venv/bin/activate   # 3.12 or 3.13; pygame 2.6.1 has no 3.14 wheels
pip install -r requirements.txt
python main.py                  # window, live time
python main.py --screensaver    # fullscreen lite mode, 30/15 fps
python main.py --help           # all flags (--time, --speed, --date, --place, --event, --seed, ...)
./venv/bin/python -m unittest discover -s tests -t .    # all tests must pass
```

Lint: install pyflakes temporarily, run `python -m pyflakes habitat tests main.py`,
then uninstall it (it isn't a project dependency).

Keys in a window: I info, J journal, D event odds/debug, W weather, T time-lapse,
N new meadow, S screenshot, F fullscreen. In `--screensaver` any key quits.

## Layout

- `main.py` is a thin entry point that calls `habitat.app.main`. It pre-scans
  argv for `--settings`.
- `habitat/defaults.toml` holds every *tuning* value, with comments. A user's
  `settings.toml` (next to the journal, `MEADOW_SETTINGS`, or `--settings`)
  overrides it. Drawing and geometry numbers stay next to the drawing code on
  purpose. `settings.py` loads and validates. `config.py` derives values.
- `chance.py` samples a spec (lognormal, Weibull, von Mises, Hawkes, OU drift
  and more) and holds the per-day character `Day`.
- Sky and world: `sky.py` (offline sun, moon and phase; place from the time
  zone), `environment.py` (light, weather, wind, temperature, snow, frost),
  `seasons.py`, `terrain.py` (procedural meadow, pond, tree with its roof,
  walk grid), `paths.py` (A* plus string-pulling), `shade.py` (the tree
  shadow follows the sun), `marks.py` (paw prints and worn paths), `water.py`,
  `particles.py`.
- Life: `entities/cat.py` (Mochi: needs and activities), `entities/visitor.py`
  (the ginger cat), `entities/wildlife.py`, `world.py` (Director spawns
  creatures), `events.py` (four rarity tiers, notices, recap), `personality.py`,
  `places.py` (places she remembers and goes back to), `journal.py` (atomic
  JSON persistence).
- Art: procedural puppets drawn in code. `pixelrig.py` is the rig.
  `cat_art.py`/`cat_anims.py` draw Mochi, plus `bird_art.py`, `fox_art.py`,
  `deer_art.py`, `pond_art.py` and `critter_art.py`. Frames are cached in
  `assets/generated/` (git-ignored, redrawn when the drawing code's hash
  changes, so the first start after an art change takes about 5 s).
- Drawing: `render.py` (one MULT light pass, lite GPU-scaled mode), `hud.py`,
  `app.py` (loop, flags, keys, screensaver mode).
- `legacy/main_original.py` is the original game, kept for reference.
  `tools/` holds the old sprite-sheet scripts. Only `assets/environment/` is
  published; the other third-party art folders are git-ignored.

## Conventions

- Test first for bugs and behaviour, and keep the whole suite green. Use seeded
  simulations to check that a refactor changes nothing.
- Commit messages describe what you'd see in the meadow (look at `git log`).
- Before pushing, ask unless the owner already said to push.
- When something notable is decided, add a dated entry to `docs/LOGBOOK.md`.
- Keep this file current. When you add a module, change a command, or the owner
  gives a new standing rule, update it in the same commit.
