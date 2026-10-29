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
python main.py --testing        # testing mode: its own clock, nothing remembered (X toggles it)
python main.py --help           # all flags (--time, --speed, --date, --place, --event, --seed, ...)
./venv/bin/python -m unittest discover -s tests -t .    # all tests must pass
```

Lint: install pyflakes temporarily, run `python -m pyflakes habitat tests main.py`,
then uninstall it (it isn't a project dependency).

Keys in a window: I info, J journal, D event odds/debug, W weather, T time-lapse,
N new meadow, S screenshot, F fullscreen, X testing mode. In testing mode T
steps through its paces, the arrows jump a day or an hour, and `[`/`]` go
to the last or next step of a seasonal story. In `--screensaver` any key
quits.

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
- Seasonal stories: `stories.py` (`Almanac`: each meadow's dates per year;
  `Stories`, one per world: the blackbirds' nest in the crown, frogspawn and
  tadpoles in the pond, stork kettles and goose skeins overhead, seen only
  as shadows and pond reflections), `entities/seasonal.py` (the blackbird
  parents' errands as generators, fledglings, froglets), `story_art.py`.
- Life: `entities/cat.py` (Mochi: needs, activities, body language),
  `entities/visitor.py` (the ginger cat and his kitten), `entities/wildlife.py`, `world.py` (Director spawns
  creatures), `events.py` (four rarity tiers, notices, recap), `personality.py`,
  `places.py` (places she remembers and goes back to), `journal.py` (atomic
  JSON persistence).
- Art: procedural puppets drawn in code. `pixelrig.py` is the rig.
  `cat_art.py`/`cat_anims.py` draw Mochi in "storybook" proportions (see the
  logbook, 2026-10-28; `cat_art.kitten()` draws the kitten with the same rig),
  plus `bird_art.py` (pigeon, sparrow, crow, the blackbirds and fledgling), `fox_art.py`,
  `deer_art.py`, `pond_art.py` and `critter_art.py`. Frames are cached in
  `assets/generated/` (git-ignored, redrawn when the drawing code's hash
  changes, so the first start after an art change takes about 5 s).
- Drawing: `render.py` (one MULT light pass, lite GPU-scaled mode), `hud.py`,
  `app.py` (loop, flags, keys, screensaver mode).
- `testing.py`: testing mode's clock (`TestClock`: any pace, jumps, whole
  days with the hour held) and its scratch copy of the journal. Use it to
  try anything seasonal; it must never write the real journal
  (`tests/test_testing.py` checks).
- `legacy/main_original.py` is the original game, kept for reference.
  `tools/` holds the old sprite-sheet scripts. Only `assets/environment/` is
  published; the other third-party art folders are git-ignored.

## Conventions

- Test first for bugs and behaviour, and keep the whole suite green. Use seeded
  simulations to check that a refactor changes nothing.
- Commit only after the full suite reports OK: chain the commit with `&&`
  behind the test run, never `;` (a commit once went in with tests failing).
- Anything new that is random but not part of the meadow's own story (sheen
  bands, ice cracks, the tree) draws its own `random.Random(seed + k)`, so
  existing seeded meadows and behaviour tests play out exactly as before.
  The seasonal stories do too (never `world.rng`): on a day with no story
  under way a meadow plays out exactly as without them
  (`tests/test_stories.py` checks it).
- Remember a creature by `Entity.serial`, never `id()`: a dead creature's
  memory address gets reused, and a newcomer inherited what Mochi felt
  about the old one (and seeded runs depended on memory layout).
- Movement: measure before changing it (time treading in place, turn speeds,
  view changes, pace spread over a simulated hour); `tests/test_locomotion.py`
  guards arriving without circling, turn speeds, paces and stepped turns.
  Walking variety (pace drift, pauses, glances, pace choice) uses the cat's
  own `gait_rng`, not `self.rng`.
- Views: eight (`right`, `fr`, `front`, `fl`, `left`, `bl`, `back`, `br`). The
  right-facing side and three-quarter keys are drawn and the left ones
  mirrored (`cat_anims.mirror_key`). Only `QUARTERED` animations exist at
  three-quarters; anything else turns her side-on (`Cat._side_on_for`).
- Art changes: look at the frames (render a contact sheet). One style for the
  whole meadow: dark eyes with a glint (`pixelrig.glint_eye`), shadows cool and
  highlights warm, dark plum-tinted outlines, `despeckle` in every finish.
  `tests/test_style.py` and `test_cat_art.py` (via `tests/pixel_lint.py`)
  hold these rules.
- Commit messages describe what you'd see in the meadow (look at `git log`).
- Before pushing, ask unless the owner already said to push.
- When something notable is decided, add a dated entry to `docs/LOGBOOK.md`.
- Keep this file current. When you add a module, change a command, or the owner
  gives a new standing rule, update it in the same commit.
