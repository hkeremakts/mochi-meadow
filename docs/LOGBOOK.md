# Logbook

A dated record of what was asked, what was decided and why. It was rebuilt
on 2026-10-21 from the chat history and the git log. Quotes are the owner's
own words. Newest entries go at the bottom.

---

## 2026-10-14 · The broken venv

**Asked:** "analyse this game and I think venv has a problem fix it"

- **Cause:** the home folder had been renamed (`huseyinkeremaktas` →
  `hkeremaktas`), so every absolute path inside the venv was dead. Python
  3.11 had also been removed, so the venv's interpreter link pointed nowhere.
  The venv could only be rebuilt, not repaired.
- **Decision:** rebuild it on Homebrew Python 3.12. pygame 2.6.1 has wheels
  for 3.12 and 3.13 but **not 3.14**, so don't upgrade past 3.13. `numpy` was
  added to `requirements.txt`, and the README's paths were made relative.
- **What the analysis of the original game found:** a layout bug on resize,
  images reloaded from disk on every resize, a vignette allocated every
  frame, wall-clock timers, `hasattr`-based food detection, and an unused
  constant. The rewrite fixed all of these.

## 2026-10-15 · Why the animation looked wrong

**Asked:** "the animations are not realistic enough and … it doesn't have
enough things to see. how can we fix these"

Through questions, the owner chose: realism in both movement and art,
**movement first**. New art was allowed ("I want you to create new art if
needed"), and the approach was **"Polish + ecosystem"**.

The diagnosis:
- **Ghosting:** every state change cross-faded two frames for 150 ms. On
  pixel art this shows as a see-through double cat.
- **Rubber-banding:** the drawn position followed the real one with a fixed
  per-frame lerp, so the lag depended on the frame rate.
- **Sliding feet:** walk frames advanced with time, not with distance.

**Decision:** lock gait frames to distance travelled, drop the cross-fade,
use frame-rate-independent easing, and split the 1,500-line `main.py`
into modules.

## 2026-10-16 · The rebuild into a habitat

**Asked:** "Make this game much better and smoother I what this to be a
natural habitat that I can watch or use as a screensaver. change the code
however you want. Take your time"

- **The `habitat/` package** replaced the single file. The original was
  kept at `legacy/main_original.py`.
- **Mochi runs on needs:** energy, hunger, thirst, grooming and play. A
  hunt goes spot → stalk → freeze → wiggle → pounce. The behaviour was
  rebalanced to a calm mix (about a third of the time napping) instead of
  constant mouse-chasing, because a screensaver should feel peaceful.
- **The meadow is procedural:** a pond with fish, bushes, rocks, flowers
  and a food bowl. It replaced the stretched wallpaper background.
- **The real clock:** day and night follow the Mac's clock, and the meadow
  survives the laptop sleeping. Weather comes from a Markov chain.
- **Wildlife:** pigeons with real altitude and shadows, butterflies, mice
  (mostly at night), fireflies, ladybirds and dragonflies.
- **Checks:** 60 tests. A 1080p frame took about 1.4 ms to draw.

## 2026-10-18 · Drawn-in-code art, and a smaller bird

**Asked:** "give cat and the bird necessary sprites too. for example right
now bird is too big … make the movement of the cat and bird more smooth
too", then "try again and redraw cat too"

- **Decision:** draw the animals procedurally (`pixelrig.py` puppets), not
  from sprite sheets. That gives every animation needed, including real
  in-between frames for sitting, lying, curling up and waking, plus
  breathing, blinking, a hiss and a pounce. Mochi became a grey cat with
  white socks, bib and muzzle.
- **The pigeon** shrank from 32 px to about 21 px to be realistic next to
  the cat. Sparrows were added at about half a pigeon's size.
- **Movement:** curved routes (A* plus string-pulling) instead of right-angle
  zig-zags, turning on the spot, and gaits generated so planted paws never
  slide. Birds glide, flare to land and burst up when startled.
- **New creatures:** a frog, a hedgehog, snails with trails, bees and leaping
  fish.

## 2026-10-18 · Rare events, the real sky, and the cost of a screensaver

**Asked:** "what about if we add some rare events and create an event
hyerarcy based on rarity." The owner left the ideas to me: "come up with the
ideas I will tell you if they are good or bad", and then said "those are
great".

**Asked next:** "first I want to make it more natural … if it is day in the
real life it will be day in the screensaver too."
- The clock was already live, but sunrise and sunset were fixed all year.
- **Decision:** compute the sun, moon and moon phase offline. The place is
  guessed from the time zone, because a macOS screensaver can't use Location
  Services. Seasons follow the calendar. Real weather from the internet was
  left optional or for later, since screensaver network access was never
  verified.

**Asked:** "making this program be a screensaver limits these? … I want it
to be as lightweiight as possible … if it use a lot of power and battery
there will be no meaning of using it"
- **Measured:** about 30% of a core at 1280×800 and about 40% at 1080p, far
  too much for a screensaver.
- **The fact that shapes the plan:** macOS only accepts native `.saver`
  bundles (Swift or Objective-C). Python can't be a real system screensaver.
- **The two paths:** make Python lean (draw small, let the GPU scale it up,
  20–30 fps), or rewrite it natively in Swift (an estimated 1–3% CPU).

**Asked:** "what do you suggest. can we rewrite this in swift?", followed
straight away by **"no give me suggesting do not start writing it in swift"**.
- **Recommendation:** Swift + SpriteKit as the eventual `.saver`, with Python
  kept as the "art studio" that exports sprite sheets.
- **Decision (2026-10-19):** "so we will do it at the end." Swift is
  deferred until the owner asks. Features a screensaver can't support come
  after that.

## 2026-10-19 · Encounters designed for a screensaver

**Asked:** "giv em the random encounters and other things that makes this
thing interesting as an screensaver."

**Rules agreed:**
- Something calm is almost always happening.
- Every event reads in two seconds.
- No interaction, since any input closes a screensaver.
- Nothing stays fixed on screen.
- The meadow remembers.
- Effects stay light on power.

**The rarity system:**
- **Tiers:** common, uncommon, rare and legendary, each with conditions
  (time, weather, season, date, moon).
- **Pacing:** only one rare-or-better event at a time, and a "luck safety
  net" that raises the odds when a tier is overdue, so a long watch is
  always rewarded.
- **Signals:** omens before legendary events (the birds go quiet), and
  fading captions for uncommon events and above.

**Built the same day** (after "start working on making the project more
natural and better … work as long as you want"):
- **The real world:** the sun and moon, seasons with snow and frost, and the
  four event tiers with notices (full moon, real meteor-shower dates, first
  snow, New Year, a pumpkin).
- **Memory:** the journal.
- **Power:** a lite GPU-scaled mode at 30 fps, or 15 fps when calm, which
  brought CPU down to about 8–11%.

**Skills:** the owner asked about Addy Osmani's agent-skills pack (24 skills)
and whether installing all of it would hurt performance. On my
recommendation, only **performance-optimization** and
**source-driven-development** were installed, the latter for checking Apple
docs during the Swift rewrite. Superpowers remains the main workflow.

**Asked:** "more event that is common to make every time a little bit more
unique … making Mochis personality more unique is so important … then add
this repo to my github."
- **Common events:** many more everyday ones (tail chase, leaf chase,
  moths, puddles, a dewy web and others).
- **Personality:**
  - Five traits and two of eight quirks, kept in the journal so Mochi
    "stays herself".
  - A mood, a favourite nap spot, and a friendship with the ginger cat.
- **GitHub:** a git repo was created and published publicly as
  `hkeremakts/mochi-meadow`. Third-party sprite folders that the game no
  longer uses were left out, because they're not ours to redistribute.

**Sharing without an Apple Developer account:** yes, it's possible. Running
from source needs no account. An unsigned `.saver` works too, but people have
to click "Open Anyway" in Privacy & Security. **Advice:** don't buy the $99
account until lots of people want the Swift version.

## 2026-10-20 · More life, a roof, and variety

- **Built:**
  - A deer at dawn (legendary), a heron and a duck with ducklings (rare).
  - A "While you were away" recap and the `D` odds overlay.
  - Gifts left at the bowl, and Mochi's birthday bow.
- **"w is not working":** the weather was changing, but it faded in over
  45 s, so the key looked broken. `W` now takes effect in about 3 s and
  shows a note. (In `--screensaver` any key quits, by design.)
- **"lets add some natural thing that works as a roof"**
  - An evergreen tree whose crown keeps off the rain and snow.
  - It's planted last, from its own seed, so existing meadows keep their
    layout.
  - In the rain Mochi mostly shelters but sometimes goes out, more often if
    she's curious or bold, "to make it natural".
- **Follow-up:**
  - A taller tree.
  - Short 20–60 s visits under the tree during drizzle.
  - Drizzle made far lighter than rain, because it had looked "too similar".
- **"which parameters have constant values like rain stops after exactly 10
  minutes"**
  - I listed every fixed timing: weather holds, meal times, bowl refill,
    cooldowns, omens, effect lengths.
- **"can we collect every variable in a config file. is it a good idea"**
  - **Decision:** centralise only the *tuning* values, in
    `habitat/defaults.toml`, with a user `settings.toml` overriding it.
  - **Why only those:** hundreds of drawing and geometry numbers only make
    sense next to their drawing code.
  - **Check:** a seeded simulation of a whole year gave identical output
    before and after.
- **"I think using gaussian with changing but relatively high varience is
  more suitable and natural"**
  - **Partly agreed:** a Gaussian suits times and amounts. Durations need a
    log-normal (skewed, never negative), and waits for arrivals need an
    exponential.
  - **"Changing variance"** became a per-day character: some days are
    settled, others changeable, and Mochi has lazy and lively days.
  - **Asked:** "You can use other distributions too", then "build all of it.
    I will stick to your ideas".
  - **Built in `chance.py`:**
    - von Mises peaks for times of day (no on/off switches)
    - Hawkes clustering for bird visits and meteors
    - mixtures (catnap vs deep sleep, shower vs soaking rain)
    - Weibull "had enough" durations
    - Ornstein–Uhlenbeck drift for wind, rain and mood
    - Poisson counts, Beta proportions, and a capped Pareto for outliers
  - **Pushed** at the owner's "yes push".

## 2026-10-21 · Licence, shade and marks

- **"can you get MIT licence for me and fix npm"**
  - **Licence:** MIT was added and pushed.
  - **npm:** 4,781 cache files are owned by root, left from an old
    `sudo npm`. The fix needs the owner's password:
    `sudo chown -R $(whoami) ~/.npm`.
- **"brainstorm for how long you want"** produced five main ideas:
  1. Snapshots of rare moments for the journal.
  2. Shadows that follow the sun.
  3. Signs of what has happened (prints and paths).
  4. Spring and autumn stories on real dates.
  5. Mochi remembers places.

  Smaller ideas included visible wind waves, thunder, a frozen pond, Venus,
  dreams, evening zoomies, a rain shake-off, and the ginger cat's kitten.

  **Dropped:** sound (a screensaver should be silent), live satellite passes
  (they need the internet), spanning several monitors (too much work), and
  ageing (sad).
- **"dropping #1 is good for now but we can do it later. start by building
  2#"**
  - The tree's shadow follows the real sun (and a bright moon), and fades
    under cloud.
  - On hot days Mochi naps in the shade and follows it as it moves. On cold
    days she seeks the sun.
- **"add #3 too if it is not expensive cpuwise"**
  - Paw prints in snow (also from the fox and deer) and muddy prints after
    puddles.
  - Worn paths that grow back over 2–3 days, kept in the journal.
  - It's cheap because marks are painted into the ground image only when
    they change, never every frame. CPU stayed at 8–10%. 223 tests pass.
- **The logbook:** asking for this record repeatedly tripped an automatic
  safety check in that session, so it was written in a fresh session as
  this file plus `CLAUDE.md`.

## 2026-10-22 · Advice on the Apple Developer account

- **"If I get the apple developer account how can people download this
  screensaver"**
  - With the account, the Swift `.saver` is signed with a Developer ID,
    notarised by Apple, and shared as a zip or `.dmg` on GitHub Releases or
    a website. People double-click it to install, with no warning.
  - The Mac App Store doesn't carry screensavers.
  - It needs the Swift version first.
- **"What should I do for the apple developer account."**
  - **Advice:** wait until the Swift version is ready to share, because it
    costs $99 a year.
  - **When it's time:** enrol as an individual (an organisation needs a
    D-U-N-S number), through developer.apple.com or the Developer app.

## 2026-10-27 · Mochi remembers places

- **Asked:** "I think seasonal stories is a hard work for now, lets do Mochi
  remembering places", then "just build it" (skipping the design questions).
- **What she remembers:**
  - the bush where she saw a mouse (its home bush, not where it ran)
  - where the fox, the deer or the hedgehog passed
  - where she found a gift
- **How:**
  - `habitat/places.py`, kept in the journal per meadow and screen size,
    like the worn paths.
  - **Strength:** each memory fades over a few days (`forget_hours` 60, gone
    in about a fortnight). It grows when the same thing turns up again and
    weakens after an empty visit.
  - **No switches:** she doesn't go back straight away, because the pull
    builds smoothly over about 40 minutes.
  - **Character:** curious cats go back more. Timid ones avoid the fox's
    spot.
- **What you see:**
  - "going back to…" and "checking…" in the info panel.
  - At the mouse's bush she sits and watches, and may paw at it, which can
    really flush a mouse.
  - A caption ("…yesterday", "…last night", "…3 days ago") only when the
    memory is at least 12 hours old, at most every 3 hours or so.
- **Tuning:**
  - **Problem:** in a three-evening simulation, her strong mouse memories
    sent her back the moment her cooldown allowed, about twice an hour.
  - **Fix:** lowering the pull (`weight` 0.6 → 0.25) and setting the
    cooldown to 20 minutes made it about once every 40 minutes at dusk, and
    less by day.
- **Cost:** nothing new is drawn. A check every 0.35 s looks through the
  creatures already on screen.

- **"do you update claude.md on the go"**
  - Not reliably: only the logbook had a rule.
  - Added a convention to `CLAUDE.md`: update it in the same commit whenever
    a module, a command or a standing rule changes.
  - A hook was considered and judged unnecessary, because it could only
    remind, not write.

## 2026-10-28 · Remodelling Mochi: research, tools and the storybook look

- **Asked:** "Search the internet to make the models more visually pleasing.
  If you can find a skill that is reliable and usable great … the cat … can
  have more personality in the model."
- **What held her back:**
  - realistic proportions (a small head and long legs), so at this size she
    read stiff and a bit dog-like
  - one-pixel eyes
  - a grey coat at about 3% saturation, the same value as the grass
- **Research:** saint11's "Cuteness" tutorial, ClanGen's cat sprite guide,
  Slynyrd on colour ramps that shift hue, and pixel-art-studio's checklists.
  They agree on:
  - big head, ears and eyes
  - dark, shiny eyes
  - cool shadows and warm highlights
  - silhouette first
  - ears and tail that carry mood
- **Skills and tools looked at:**
  - **Rejected:** pixel-art-studio, claude-pxl, willibrandon's
    Aseprite-based plugin, and uilianks' pxl/vex/kiln/loom/chirp. None can
    drive our posable rig. Each would mean hand-drawing about 70
    animations, and some need Aseprite or would take over the workflow.
  - **Kept:** pxl's "lint" idea, rewritten in Python as `tests/pixel_lint.py`.
- **Agent Reach:** installed to read a Reddit post. Reddit blocks it
  without a login, so the owner pasted the post instead. Removed again at
  the owner's request.
- **Model sheet:** three versions (now, storybook, chibi) drawn from the
  same rig in eleven poses. The owner chose **storybook**: "yes storybook is
  good. Change every necessary model with storybook".
- **Built, in `cat_art.py`:**
  - **Proportions:** a head 1.22× bigger and a muzzle 0.8× as long, legs
    0.9×, and a fuller body. `proportioned()` lowers a standing body onto
    the shorter legs (smoothly, so sitting down still blends) and keeps
    the bigger head off the ground when she eats or sprawls.
  - **Eyes:** 2×3 pixels, a dark pupil with a glint top-left and amber
    showing below.
  - **Coat:** a slate blue-grey ramp (cool shadow, warm light) with a plum
    outline, darker than the grass.
  - **Her own marks:** a white blaze and a white tail tip, in their own
    `MARK` palette slot. The ginger visitor maps that slot to his coat, so
    the marks stay hers.
  - **Clean-up:** a `despeckle` pass in `pixelrig.py` merges lone crumbs
    left by the crease lines. Stray pixels went from 4.2 a frame to about
    0.4 (only her nose, a single pixel on purpose). Doubled corners dropped
    by about a third.
- **Unchanged:** her mouth reach (21), so meadow layouts don't move.
  Frames are drawn once and cached, so CPU use is the same. The first start
  after the change redraws them.
- **Also:** the README preview was remade with the new Mochi.
- **"I think the whole meadow should match":** every animal was brought into
  the same style, kept realistic.
  - **Eyes:** a shared `glint_eye` in `pixelrig.py` (a dark pupil, a glint
    top-left, colour below). The fox (amber), deer (big and dark), heron
    (yellow), crow (its black eye finally readable) and hedgehog have one;
    the mouse gets a one-pixel glint.
  - **Fox and deer:** slightly bigger heads with shorter snouts, and bigger
    ears on the deer.
  - **Every coat:** shadows shifted cool and highlights warm, and outlines a
    dark plum-tinted version of each animal's own colour.
  - **Clean-up:** the same `despeckle` pass, with each animal's deliberate
    one-pixel details (noses, beaks, wing bars) kept.
  - **Left as they were:** the insects (a few pixels each) and the duck's
    one-pixel eye, which a 2×2 eye would swamp on its head.
  - **Tests:** `tests/test_style.py` holds the rules, and it caught two of
    my own colour picks on the way: the fox's shadow wasn't cooler than its
    light, and the duckling's outline wasn't plum-leaning.
- **"do body language first"** (before watching it and before Swift):
  - **Built:** mood versions of her stand, walk, trot, sit and lie, from
    every angle, chosen by `_read_air()`:
    - **Happy:** mood above 0.5. The tail goes up and hooked (a question
      mark), ears pricked.
    - **Cross:** mood below -0.3. Ears back, the tail lashing, or the tip
      thumping when she sits.
    - **Wary:** the fox within fear distance, rain on her fur outside cover,
      or hiding. Ears flat, tail low. This wins over any mood.
  - **No flicker:** a mood has to fade 0.1 past its edge before she lets
    it go.
  - **Keeps her rhythm:** a mood change mid-walk swaps the clip at the same
    point in its stride.
  - **Left out on purpose:** happy versions of sit and lie, where a happy
    cat looks like any other.
  - **Settings:** `[mochi.body_language]` in `defaults.toml`.
  - **Cost:** about 850 more cached frames (about 14 MB of memory). The
    one-off redraw after an art change went from about 4 s to 6 s. CPU per
    frame is unchanged.
  - **Checked in simulation:** over a 14-hour day, two cats were happy 4–19%
    of the time, and their moods shifted 20–50 times a day. Cross and wary
    only show after bad moments, which is right for a calm meadow.
- **"can we make Mochis waist a little bit bigger, I think this way it will
  look less like a puppet"**
  - Her waist (the body between chest and haunch) was a thinner tube than
    either, which read as a puppet's joint.
  - Three options were compared. Chosen: waist ×1.2 (`WAIST`) plus a belly
    that hangs 0.8 below the chest-to-haunch line (`BELLY`), so her back
    stays straight and the fullness sits underneath.
  - Both fade as she lies down, where her body rests on the ground
    (otherwise a curled-up cat sank into it).
- **"for Mochi belly C good I think and his ass is a little big too big …
  I think tree is again too small."**
  - **Mochi:** belly option C (`WAIST` 1.3, `BELLY` 1.2), and the haunches
    drawn at 0.9 of their pose size (`HAUNCH`, replacing the 1.06 fuller
    look), so her rear no longer dominates.
  - **The tree:** everything scaled by `TREE_SIZE` = 1.35 in `terrain.py`:
    - the crown's width, and the trunk's height (30 → 40) and thickness
    - the crown's height above the ground, which the sun-shadow code now
      reads from `terrain.CROWN_LIFT` rather than its own copy
    - the dry patch under the crown and the baked shade
  - **Checked:** across 60 meadows at four screen sizes the tree always
    still fits. The owner's own meadow keeps everything else where it was,
    because the tree is planted last from its own random numbers.
  - **A bigger crown is see-through over Mochi more often** (that keeps her
    in sight when she's behind it).
## 2026-10-28 · The smaller touches

**Asked:** "do smaller touches, and we will start seasonal stories but wait
for it for now". All eight from the 2026-10-21 brainstorm were built, each
committed on its own:
1. **Dreams:** after `dream_after` (90 s) of sleep, at exponential gaps,
   her paws paddle, an ear twitches and the tail tip flicks.
2. **Shaking off the rain:** her coat soaks while she's out in it
   (`Cat.wet`; drizzle only dampens it) and dries slowly. Past
   `wet_shake`, she shakes with droplets flying, then grooms twice.
3. **Evening zoomies:** after the dusk meal, with a chance scaled by how
   playful she is.
4. **Wind you can see:** the plants' sway was already a travelling wave.
   New are pale sheen bands (`GustSheen`) racing over the grass in gusts
   above 0.5, added to the ground under everything on it. They cost
   nothing measurable. They draw their own random numbers, because sharing
   the world's had changed seeded meadows and broken four behaviour tests.
5. **Thunderstorms:** an uncommon event in a warm downpour.
   - Silent flashes come in Hawkes bursts, some a double flicker.
   - Mochi stays wary throughout, her mood dips a little at each flash,
     and a flash sends her for cover if she's out in it.
   - Because flashing light can bother some people, `lightning_brightness`
     can soften it, and 0 turns it off.
6. **A frozen pond:** `env.ice` forms below `ice_below` (-2 °C) and thaws
   above freezing.
   - It's baked into the ground: grey-blue, the water showing through, and
     a few jagged crack lines (their own random numbers) that spread as it
     thickens. A first try with scattered pixels read as speckle.
   - Nothing ripples on ice, the fish are hidden, and glints drop to a fifth.
   - Mochi tests it with a paw and licks at it instead of drinking.
7. **The sky in the pond:**
   - **Venus:** worked out from JPL mean orbital elements. Checked against
     the published dates to within a degree: greatest elongation +46° on
     2026-08-15, between us and the sun on 2026-10-24, -47° on 2027-01-03.
   - **Lunar eclipses:** NASA's table of total and partial eclipses to
     2040 (penumbral ones and very shallow partials left out). The moon's
     reflection dims and turns copper, moonlight fades, and a legendary
     notice fires.
   - **A fix found on the way:** pond reflections were drawn over the
     (now bigger) tree crown. They are now hidden behind it.
8. **The ginger cat's kitten:** a legendary visit for best friends, in spring
   or summer.
   - It's drawn by Mochi's rig in kitten proportions
     (`cat_art.kitten()`): smaller, mostly head, short in the leg, with blue
     eyes and a cream-ginger coat.
   - It follows him, greets Mochi from her other side (at first all three
     overlapped), pounces at her tail, scampers about and goes home after
     him.

**A slip, fixed:** one commit went in with four tests failing, because the
command chain used `;` instead of `&&`. The fix came straight after, and
commits are now made only when the full suite reports OK.

## 2026-10-28 · Movement: a circling bug fixed, and a plan for the rest

- **Asked:** "Mochi's movement is still too robotic. His turns are too
  sudden and sometimes it walks in the same place … analyse its movement,
  and research how to create more realistic animation algorithm."
- **Measured, over a simulated hour:**
  - Her legs were moving for 30 minutes, about 20 of them spent circling a
    goal 2–4 px out.
  - Her sprite changed view 2,860 times.
  - Her turns ran at 172°/s and up 10% of the time.
- **The bug:**
  - **Cause:** on a final approach with the goal behind or beside her,
    the speed floor (30% of cruise) and the minimum turn rate (3 rad/s)
    gave a turning circle wider than the 0.6 px arrival zone, so she
    orbited the spot.
  - **Fix:** within `ARRIVE_RADIUS` (12 px), if she isn't facing the
    goal she brakes and turns first. After 3 s of final approach she
    steps the last bit.
  - **After:** 10 minutes of leg movement an hour, no circling, 232 view
    changes. Tests are in `tests/test_locomotion.py`.
- **Still robotic, and planned** (owner: "add these 2 steps to to-do list,
  beside seasonal stories"):
  - turning on the spot treads (about 8% of walking time)
  - turns are too fast, on routes with hard corners
  - only three views, so turns snap
  - one pace, with dead stops
- **Research:** Reynolds' arrival steering; The Occupation's layered
  locomotion (turn before setting off, walk starts, lean into turns);
  Orange Duck's spring-smoothed movement; quadruped turning studies
  (turning by uneven stride and duty factor; cats keep their rhythm when
  curving round obstacles).

- **"the hedgehog walked through the pond"**
  - **Cause:** it walked straight lines to its sniffing spots, never
    checking what was in between.
  - **Fix:** it now enters from an edge with nothing solid on the way in,
    and follows `find_path` routes in and out, like the fox.
  - **Same flaw in the birds:** pigeons' and sparrows' little walks could
    also cut across the water, and now need a clear line.
  - **The mouse** already stops at water. Ladybirds, snails and
    grasshoppers check every step.
  - **Tests:** `tests/test_ground_walkers.py`. The chatterer test now
    tries more meadows, since chatter is a chance and the bird change
    shifted the random draws.

## 2026-10-29 · Movement step 1: curves, deliberate turns, three paces

**Asked:** "start with movement step 1".
- **Steering:**
  - She aims `LOOKAHEAD` (12 px) along the route, but only where the
    line there is clear, so she never cuts a corner through a bush.
  - Her turn rate is her speed ÷ `TURN_RADIUS` (12 px), between
    `TURN_MIN` and `TURN_MAX`.
  - She eases off before sharp corners, and her pace drifts (`pace_drift`).
- **Setting off:**
  - a short pause first, and a glance toward you if she's heading your way
  - if the way is more than `FROM_REST` (70°) off, she steps round first,
    then walks off on a curve
  - **Why 70°:** a 124° swing from rest carried her into a bush and
    stranded her
- **Turning on the spot:** `_turn_in_steps`, steps of 34° with 0.08 s
  pauses, the legs resting between steps.
- **Up against an edge facing the wrong way:** she turns to the way out
  rather than burning her replans. This had stranded her by the bowl after
  a pounce.
- **Paces:**
  - a new `amble` animation in every view and mood (stride 11, head lower)
  - `brisk` (34 px/s) when she's hungry
  - `_wander_pace()` chooses an amble more often when she's tired or
    lazy, now and then brisk or a trot
  - leisurely walks pause now and then (`dawdle_rate`) to sniff or look
    about
  - settings: `[mochi.walking]`
- **Random numbers:** walking variety uses its own `gait_rng`, so seeded
  meadows decide as before.
- **Measured over an hour:**
  - sharpest 1% of turns: 172°/s before, 117°/s now
  - most turning is now gentle (90% under 80°/s), instead of straight
    lines and snaps
  - pace now ranges 9–27 px/s, where before it sat at 10–25 with a
    median of 24
  - turning on the spot: 43 s of fast treading before, 66 s of deliberate
    steps now
  - CPU unchanged (0.047 ms a world update)
- **Found on the way:**
  - A fast raindrop could pass the crown's catch height and the ground in
    one frame, splashing under the tree. Fixed.
  - The shade-following test only ever passed by skipping itself. It now
    picks a meadow where the shade falls on open ground.

## 2026-10-29 · Movement step 2: eight directions

**Asked:** "now do the step 2".
- **The views:** `cat_art.three_quarter()` turns a side pose to
  three-quarters, so the side skeleton is seen at an angle:
  - shortened along its length (`QUARTER_SHORTEN`)
  - the far end higher (`QUARTER_DEPTH`), the nearest paws staying on the
    ground line
  - chest and rump a little wider
  - the face turned to you (toward) or the back of her head (away)
  - **Tuning:** going away first looked as if she were climbing, so its
    depth is lower (0.17 against 0.32) and her head sits a little lower.
- **Coverage:** `QUARTERED` animations (stand, walk, amble, trot, run,
  stalk, sit, sitdown, standup, and their moods) are built for "fr" and
  "br". The left ones are mirrors, via `cat_anims.mirror_key`.
- **View choice:** `view_for` now has 8 sectors, with hysteresis.
  `_side_on_for` turns her side-on for anything only drawn side-on.
- **Fixes on the way:**
  - **Strides:** `STRIDES_QUARTER` keeps planted paws put.
  - **Gift and bow:** their positions are worked out for the new views.
  - **Smaller fixes:** shadow size, grooming from behind, and the gift's
    flip.
  - **Outline pinholes:** `despeckle` now also fills outline-coloured
    pinholes inside her shape.
- **Cost:** about 11 MB more (3,550 frames against 2,870), after dropping
  blinks mid-stride (about 770 frames nobody would see). The one-off
  redraw after an art change is about 9 s. CPU per frame is unchanged.
- **Tests:** in `test_locomotion.ThreeQuarters`, every view exists,
  diagonals use them, side-on-only actions turn her side-on, and turns
  skip views less than 10% of the time.

- **"it was doing circles before sitting or laying down is it intentional
  like real cats do"** (then "yes do both")
  - **Not intentional:** separate turns ran back to back: the look-around
    glance at the end of a wander (45–125°), a turn to step into the spot,
    then a turn to face the spot's set direction. Before sitting that came
    to 84° on average, at most about 210°. The deliberate steps from
    step 1 made it more noticeable.
  - **Fix 1:** loose spots (`go_to_spot(..., loose=True)`: nap, loaf,
    shade or sun, and the tree) keep the side she's facing. A final step
    under 5 px is shuffled, not turned to. The look-around glance is now
    30–75°. Turning before sitting dropped to 45° on average; the bigger
    turns left have a reason (facing the pond, a bush or prey).
  - **Fix 2:** `turn_round()` adds the real habit. Before a nap she turns
    round once (or sometimes twice) on the spot, slowly, at odds of
    `circle_before_nap` (0.55). There's no circling before sitting.

- **Known, not fixed:** two meadows starting at the same moment right after
  an art change can collide while redrawing the sprite cache. This was seen
  when six preview renders ran at once. It's rare in real use.

---

## Open items

- **Watch it for a few days** and tune from real viewing (the owner's
  notes): event rates, captions, how often she goes back to places, the new
  look in every light, and whether the 15 fps calm mode shows.
- **Next projects, waiting for the owner's go:**
  - **Seasonal stories** (from the 2026-10-21 brainstorm, #4): a nest in the
    tree in spring (eggs, chirping, fledglings, parents scolding Mochi),
    frogspawn becoming tadpoles and tiny frogs, storks circling over the
    Bosphorus in late August, geese heading south in autumn.
  - **Movement, step 1:** done on 2026-10-29 (see above). Waiting on the
    owner's verdict from watching it.
  - **Movement, step 2:** done on 2026-10-29 (see above).
- **A testing mode** (owner, 2026-10-28: "increasing the clock speed for
  faster testing … the program can switch to testing mode and stops
  following to normal day-night or moon cycles and goes on with its own
  clock"; not to be built yet).
  - **Already there:** `T` cycles time-lapse 1× → 60× → 600×, and
    `--time`, `--date`, `--speed`, `--weather`, `--event` set things up.
    These still follow the real sky and calendar.
  - **To design:** a switchable mode where the meadow runs on its own
    clock. Day and night, the moon's phase and the seasons would cycle
    quickly and independently of the real date, so a whole day, month or
    year can be watched in minutes. It needs a clear on-screen sign that
    it's in testing mode, and must not write the real journal (or must
    keep a separate one), so test runs don't change Mochi or the saved
    meadow.
- **Snapshots of rare moments** (brainstorm #1): deferred.
- **Small fixes:**
  - the sprite-cache collision when two meadows start at once after an art
    change
  - the npm cache, which needs the owner's password
- **The Swift `.saver` rewrite:** last, and only when asked.
- **After Swift:** things a screensaver can't do, such as live weather,
  interacting with Mochi, and widgets.
