# Explainer Video Script — "60 Frames a Second, 5 Decisions a Second"

**Project:** mario-decisions-agent — https://github.com/parjanyaacoder/mario-decisions-agent
**Target runtime:** 8 min 30 s
**Style reference:** 3Blue1Brown — dark canvas, smooth camera moves, objects that morph
into one another, equations drawn on screen, colour used to carry *meaning* (not decoration).

---

## 0. Hard rules for this video

1. **NO AUDIO-ONLY SEGMENTS.** Every single narration line must have a visible change
   on screen — an equation completing, a bar growing, footage cutting, a number counting.
   If you cannot name what is moving, do not write the line yet.
2. **Nothing sits still for more than ~3 seconds.** Every shot has a camera push/pan,
   an element morphing, a counter ticking, or a new colour highlight.
3. **Real footage carries the emotional beats; diagrams carry the maths.** Alternate:
   footage → diagram → footage → diagram. Never three diagrams in a row.
4. **Numbers appear when spoken, vanish when done.** On-screen numbers must animate in
   on the exact word.
5. **Units are always shown next to numbers** (frames, seconds, px, dollars).

## Visual style guide

| Element | Spec |
|---|---|
| Canvas | near-black `#0B1020`, subtle vignette, very faint grid that parallaxes on camera moves |
| Primary text | Lato or Fira Sans, regular weight, white `#FFFFFF` |
| Equations | serif-free, letter-by-letter draw-on, 64–96 px, centred third of frame |
| Accent A — the **game** | cyan `#35C4E8` (frames, fps, world) |
| Accent B — the **model** | amber `#FFB300` (latency, decisions, cost) |
| Accent C — **tension/failure** | magenta `#FF5F8F` (staleness, death, the gap) |
| Accent D — **success/answer** | green `#4ADE80` (answer lands, cached, kept-up) |
| Footage | full-bleed, 4:3 NES content letterboxed on the dark canvas; nearest-neighbour upscale for pixel fidelity |
| Transitions | no wipes/cuts-with-noise; morph one object into the next (e.g. a 60-frame ruler *becomes* the equation) |
| Music | calm, curious, minimal; rises only at Scene 7 (the result) |
| Typing SFX | subtle keyboard tick when a terminal command appears |

### Rules against the failure mode

- ✅ Every scene below has an explicit `VISUAL` block describing exactly what is on screen
  and what changes, beat by beat. Follow it.
- ❌ Do not render a static slide with narration over it.
- ❌ Do not place a full paragraph of text on screen — only equations, labels, and
  ≤6-word captions.
- ❌ Do not use stock "AI brain" or "robot" imagery. Ever.

---

## 1. Asset manifest (real files in the repo)

| Asset | Path | What it shows |
|---|---|---|
| 15 fps run | `runs/live_fps15.mp4` | agent keeping up, 8 frames/move, 294 frames, x=722 |
| 30 fps run | `runs/live_fps30.mp4` | agent keeping up, 8 frames/move, 294 frames, x=722 |
| 60 fps run | `runs/live_fps60.mp4` | agent falling behind, ~12 frames/move, stalling |
| latency-spike run | `runs/fix_fps30_r2.mp4` | 0.49 s reply → ~9 stalls/decision → stopped at x=434 |
| early (confounded) sweep | `runs/sweep_fps15_r1.mp4`, `runs/sweep_fps60_r3.mp4` | older runs where fps and step size both changed — **label as "before the fix" if used** |
| 6 s hero clips | `docs/media/live_fps15.gif` / `live_fps30.gif` / `live_fps60.gif` | short loops for the result triptych |
| architecture diagram | `docs/architecture.svg` | three blocks: world / loop / brain — **rebuild as animation, don't show as static PNG** |
| speed-gap diagram | `docs/speed-gap.svg` | latency bracket at 60 vs 15 fps — **rebuild as animation** |

---

## 2. THE SCRIPT

---

### SCENE 1 — COLD OPEN · 0:00 – 0:35 · (35 s)

**VISUAL**

- **0:00** Black. A single NES frame of World 1-1 fades up, full-bleed 4:3,
  centred on the dark canvas. Faint parallax push-in.
- **0:03** A mono frame counter types into the lower-left: `FRAME 0000`.
  It starts ticking fast — one increment per real game frame, no gap.
- **0:06** A **cyan ruler** slides in under Mario and starts sweeping right with him,
  tick marks every frame, labelled `FRAMES`.
- **0:09** Mario runs right. Goomba appears at screen centre. Counter: `FRAME 0100`.
- **0:12** An **amber chip** flies in from off-screen right toward Mario and hangs there,
  unopened. Label above it: `THINKING… 0.20 s`. Under the ruler, the frame counter
  keeps ticking: `0101 0102 … 0106`.
- **0:15** Collide. Screen flashes magenta, Mario dies, counter stops at `0106`.
  Magenta annotation draws: **"12 frames later"**.
- **0:19** The whole shot shrinks into a small panel and docks left. A **second,
  identical** panel opens right playing `runs/live_fps15.mp4` at the same spot,
  arriving there calmly.
- **0:24** Big white text draws between them: **"same agent · same level · same move set"**
  then under it: **"one number changed."**
- **0:30** Both panels fly out. One enormous cyan `60` draws centre-frame.

**ON-SCREEN TEXT**
- `FRAME 0000 → 0106`
- `THINKING… 0.20 s`
- `12 frames later`
- `same agent · same level · same move set`
- `one number changed`

**NARRATION** *(verbatim)*
> Watch this. One screenshot in, one button out — an AI deciding where Mario should jump.
> Every answer takes about a fifth of a second to come back. But the game doesn't wait
> for it. In that fifth of a second it advances twelve frames.
> Same agent, same level, same move set. Only one number changed — and the difference
> between "wins" and "dies" was hiding inside it.

**ASSET:** `runs/live_fps60.mp4` (0–2 s), then split with `runs/live_fps15.mp4`.

**SFX:** game audio low under VO; single death sting at 0:15; music starts 0:19.

---

### SCENE 2 — TITLE · 0:35 – 0:45 · (10 s)

**VISUAL**
- The `60` morphs: its right half slides away and an amber `5` slides into the gap.
  A cyan↔amber bracket appears between them labelled **12×**.
- Underneath, the title types on in Lato light, one line at a time.

**ON-SCREEN TEXT**
> `60 frames a second · 5 decisions a second`
> `Making the OpenAI Decisions API play Super Mario Bros from pixels alone`

**NARRATION**
> Sixty frames a second. Five decisions a second. This is the story of what has to happen
> in between.

**ASSET:** none (pure type/motion).

---

### SCENE 3 — THE PROBLEM · 0:45 – 2:25 · (100 s)

**3a — the phone-a-friend analogy (0:45 – 1:15)**

**VISUAL**
- Dark canvas. Left: a small cyan sprite of Mario on a ground line.
  Right: an amber cloud labelled `THE MODEL`.
- **0:48** An arrow launches left→right carrying a small JPEG thumbnail icon. The camera
  tracks it. It takes visibly long to cross.
- **0:55** While it travels, the **ground line scrolls left** and a frame-ruler below
  accumulates ticks — cyan ticks stacking up, labelled `FRAMES THE GAME PLAYED`.
  The stack reaches **12**.
- **1:02** The arrow returns with an amber chip reading `RUN_RIGHT`.
- **1:06** The chip docks into Mario's controller. He jumps — but the Goomba he was
  avoiding has already walked past his landing spot. A small magenta `✗ LATENCY`
  stamps over the moment.
- **1:10** The whole diagram freezes and the word **"stale"** draws in magenta across
  the scrolling ruler.

**ON-SCREEN TEXT**
- `THE MODEL`
- `FRAMES THE GAME PLAYED: 12`
- `RUN_RIGHT`
- `✗ LATENCY`
- `stale`

**NARRATION**
> Imagine playing Mario with one twist: after every move you have to phone a very smart
> friend, describe the screen, and wait for them to tell you what to do next. You can only
> react as fast as they answer.
> While your friend is thinking, the game is not paused. It keeps going — twelve frames of
> it. By the time the answer arrives, the picture it was based on is no longer the picture
> you're looking at.

**3b — the two clocks, side by side (1:15 – 1:45)**

**VISUAL**
- The diagram clears. Two large numerals draw in from opposite sides and meet at centre.
  - Left, **cyan** `60` with a label animating under it: `frames per second — the game`.
    Beneath, a strip of 60 tiny ticks fills in over exactly one second of music beat.
  - Right, **amber** `5` with label: `decisions per second — the model`. Beneath, only
    **5** amber dots appear in the same one second, spread wide, with long gaps between.
- **1:30** The two strips align on a shared time axis. The mismatch is brutally visible:
  60 cyan ticks vs 5 amber dots.
- **1:36** A magenta bracket spans the whole axis labelled **12×**.
- **1:41** Below, the equation draws letter by letter:

  `0.20 s  ×  60 frames/s  =  12 frames`

  Units animate: `s × frames/s` → the `s` and `s` strike through and vanish →
  leaves `frames`. *(This unit cancellation should be a visible animation.)*

**ON-SCREEN TEXT**
- `60` `frames per second — the game`
- `5` `decisions per second — the model`
- `12×`
- `0.20 s × 60 frames/s = 12 frames`

**NARRATION**
> The game runs at sixty hertz — it advances sixty times every second. The model takes
> about two hundred milliseconds to reply. At best, that's five decisions a second.
> Multiply it out: two hundred milliseconds times sixty frames per second equals twelve
> frames. Twelve game frames pass for every single answer. Which means, at full speed,
> the model is only ever reacting to a screen that is a fifth of a second old.

**3c — measure it, don't guess it (1:45 – 2:05)**

**VISUAL**
- A terminal window slides up from the bottom, monospace, dark.
  Typing animation with key ticks:

  ```
  python scripts/probe_latency.py --repeats 5
  ```
- Output lines type in one at a time, **magenta** first line, then **green**:
  ```
  call 1   4.07 s   ← cold start (model not warm)
  call 2   0.23 s
  call 3   0.17 s
  call 4   0.21 s
  call 5   0.19 s
  steady state ≈ 0.20 s
  ```
- **1:58** The 4.07 row dims and a magenta annotation writes: `cold — do not design around this`.
  The green `≈ 0.20 s` enlarges and becomes the **canonical symbol** used for the rest of
  the video: an amber `L` slides in beside it — `L = 0.20 s`.

**ON-SCREEN TEXT**
- `probe_latency.py --repeats 5`
- `4.07 s ← cold start`
- `steady state ≈ 0.20 s`
- `L = 0.20 s`

**NARRATION**
> And we measured it rather than assumed it. The very first call took four seconds — a cold
> start that would have looked fatal. The next five took between a hundred and seventy and
> two hundred and thirty milliseconds. Steady state is about two hundred milliseconds.
> From here on, that number has a name: L.

**3d — the statement of the problem (2:05 – 2:25)**

**VISUAL**
- Terminal slides away. Centre-frame, the equation from 3b reassembles, now symbolic:

  `staleness  =  L × F`

  with `L = 0.20 s` and `F = 60 frames/s` attached as small notes.
- `L × F` substitutes in real time → `12 frames`, stamped magenta.
- Camera pushes slowly into the word `stale`, which then morphs into a **title strip**
  across the bottom: `THE PROBLEM`.

**ON-SCREEN TEXT**
- `staleness = L × F`
- `= 12 frames`

**NARRATION**
> So the entire problem is one multiplication. Latency times the game's speed gives you how
> out of date every answer is. Twelve frames out of date at sixty hertz — about a sixth of a
> second of your life happening while you're still reading the screen. Close that gap without
> secretly feeding the model extra information, and you've built the project.

**SFX:** quiet typing at 1:45; a soft "settle" chime when `L = 0.20 s` locks in.

---

### SCENE 4 — THE SYSTEM · 2:25 – 3:25 · (60 s)

**VISUAL**

- **2:25** Three blocks assemble from the left, each arriving with a small icon:
  `THE WORLD` (cyan) → `THE LOOP` (white) → `THE BRAIN` (amber).
  Connectors draw between them as arrows.
- **2:32** A **frame** pops out of THE WORLD: a thumbnail of the NES frame, labelled
  `RGB 256×240`.
- **2:36** The thumbnail flies into THE LOOP and **physically shrinks** to a small
  JPEG chip — a `256 px` badge and a `quality 80` badge snap onto it as it compresses.
- **2:41** The chip flies toward THE BRAIN and, en route, two question chips split off it
  and travel with it:
  - `? which move` (amber, expands into **10 small move chips**: `RUN_RIGHT`,
    `SHORT_HOP_RIGHT`, `HIGH_JUMP_RIGHT`, `WAIT_OR_DUCK`, `BACK_UP`, … )
  - `? hazard ahead?` (amber outline, predicate)
- **2:48** THE BRAIN pulses once. Returns an **answer chip**: `HIGH_JUMP_RIGHT`.
- **2:52** The answer lands in THE LOOP; a strip of **8 frame-ticks** lights cyan and the
  chip presses held across all 8 — label `held for N frames`.
- **2:56** Simultaneously a **second** arrow leaves the loop toward THE BRAIN (labelled
  `NEXT QUESTION — already in flight`). Two arrows now exist at once. This is the key image.
- **3:05** The cycle replays once at 2× speed, arrows overlapping.
- **3:12** The three blocks are labelled with a magenta bracket on the right:
  `60 Hz world · ~5 Hz brain · one loop between them`.
- **3:18** A small footnote badge slides in bottom-left: `pixels only — no memory reads`.

**ON-SCREEN TEXT**
- `THE WORLD` / `THE LOOP` / `THE BRAIN`
- `RGB 256×240` → `256 px · q80`
- `? which move` · `? hazard ahead?`
- `HIGH_JUMP_RIGHT`
- `held for N frames`
- `NEXT QUESTION — already in flight`
- `60 Hz world · ~5 Hz brain · one loop between them`
- `pixels only — no memory reads`

**NARRATION**
> Three pieces, and each one is swappable — which is why the whole thing can also run
> offline with no key at all.
> The world is a real NES emulator stepping sixty times a second. The brain is a remote
> vision model that sees one small JPEG and returns one move. And the loop is the glue
> between them.
> One decision, end to end: the emulator advances a frame and hands back a picture. The
> loop shrinks it — but never crops it, because cropping hides the obstacle you need to see —
> and asks the model two questions: which move, and is a hazard coming. The model picks one
> of ten sensible moves, not raw button presses. The loop holds that move for a few frames,
> and while it does, the *next* question is already on its way.
> Three blocks, one constraint: the model only ever sees pixels. No position, no lives, no
> score. Nothing but what a screenshot shows.

**ASSET:** rebuilt animation of `docs/architecture.svg` — do **not** paste the SVG static.

**SFX:** soft whooshes for each block; two overlapping arrows get a distinct double-pulse.

---

### SCENE 5 — THE MATHS · 3:25 – 5:15 · (110 s)

> *This is the centrepiece. Everything is drawn. Nothing is spoken without appearing.*

**5a — define the three symbols (3:25 – 3:45)**

**VISUAL** Three symbols drop in from the top and settle in a row, each in its own colour:

- `L` **amber** `= 0.20 s` — under it, small: `latency of one answer`
- `F` **cyan** `= 60` `frames/s` — under it: `game speed`
- `N` **green** `= 8` `frames` — under it: `frames each move is held`

As each is spoken, a tiny live example appears beneath: `L` → a stopwatch; `F` → a rapid
tick strip; `N` → 8 lit squares in a row.

**ON-SCREEN TEXT:** the three symbols and labels above.

**NARRATION**
> Let's do the maths. Three quantities, and the whole project is written in them.
> L — the model's latency, about point-two seconds. F — the game's speed, sixty frames a
> second. And N — how many frames we decide to hold each move for. Call it eight.

**5b — staleness with units (3:45 – 4:05)**

**VISUAL**
- The three symbols float to the left. Equation draws centre:

  `staleness  =  L × F`

- **3:50** Substitutes: `0.20 s × 60 frames/s`. The `s` in `0.20 s` and the `/s` in
  `frames/s` are highlighted amber/cyan and **fly together and annihilate** with a small
  flash, leaving `frames`.
- **3:55** Result stamps: `= 12 frames`, magenta, with a bracket drawn beneath it.
- **4:00** A **slider** appears labelled `F`. Dragging it from 60 down to 15, the result
  re-computes live: `60 → 12` · `30 → 6` · `15 → 3`. Each value flashes green as it
  becomes safe. The magenta bracket physically **shrinks** as the slider moves left.

**ON-SCREEN TEXT**
- `staleness = L × F`
- `0.20 s × 60 frames/s = 12 frames`
- `F = 60 → 12` · `F = 30 → 6` · `F = 15 → 3`

**NARRATION**
> Staleness is latency times speed — and watch the units, because they cancel: seconds times
> frames per second leaves frames. Point-two seconds at sixty hertz is twelve frames.
> Now drag the game slower. At thirty hertz that's six frames. At fifteen, only three. The
> seconds don't change; the frames do.

**5c — the cycle: sum versus max (4:05 – 4:45)**

**VISUAL** *(This is the most important animation in the video.)*

- Two Gantt-style timelines appear one above the other, sharing a horizontal time axis.

- **TOP** labelled `BLOCKING — ask after the move ends`:
  - Bar 1: **cyan**, width `N/F = 0.13 s` — label `apply move (8 frames @ 60 fps)`.
  - Bar 2: **amber**, width `L = 0.20 s` — label `ask, wait for answer`.
  - They sit **end to end**. Total bracket draws under both: `0.33 s`.
  - A **magenta idle-hatch** appears in the amber bar's tail — the game is running but
    nothing is being decided.
  - Rate stamps: `3.0 decisions per second`.

- **4:25** The bottom timeline builds, labelled `PIPELINED — ask when the move is applied`:
  - Bar 1: **cyan** `N/F = 0.13 s`.
  - Bar 2: **amber** `L = 0.20 s` now **slides left to overlap** bar 1, starting
    simultaneously.
  - Total bracket collapses to `0.20 s` — the bracket physically **shortens** with a
    morph, and the overlap region is hatched **green** labelled `answer ready before move ends`.
  - Rate stamps green: `5.0 decisions per second`.

- **4:35** The two brackets are compared: `0.33 s → 0.20 s`. A `1.67×` pops in.
- **4:40** Above both, the equation resolves in large type:

  `blocking  T = N/F + L`  →  `pipelined  T = max(N/F, L)`

  The `+` **morphs** into `max(` with a smooth shape change — this transition is the
  visual thesis of the whole video.

**ON-SCREEN TEXT**
- `BLOCKING — ask after the move ends` → `T = N/F + L` → `0.33 s` → `3.0 decisions/s`
- `PIPELINED — ask when the move is applied` → `T = max(N/F, L)` → `0.20 s` → `5.0 decisions/s`
- `answer ready before move ends`
- `1.67×`

**NARRATION**
> Here's where it gets interesting. If you only ask the model after the current move has
> finished playing, the two waits stack up: eight frames is a bit over a tenth of a second,
> then point-two seconds of thinking — thirty-three hundredths of a second per decision.
> Three decisions a second. The game runs at sixty.
> So instead, ask the *moment* you apply a move. Now the two waits overlap: the answer to
> question one arrives while move one is still playing. The cycle is no longer a sum, it's
> whichever is bigger — the maximum.
> At sixty hertz that's twenty hundredths of a second instead of thirty-three. Five decisions
> a second instead of three. Same model, same level, no extra information — just not paying
> for the same wait twice.

**5d — frames per move (4:45 – 5:00)**

**VISUAL**
- The `max` equation **restructures** into:

  `frames per move  =  max( N ,  L × F )`

- Three columns build beneath, one per measured speed:

  | `F` | `L × F` | `max` | observed |
  |---|---|---|---|
  | `15` | `2.9` | **`8`** | `8.2` ✓ |
  | `30` | `4.8` | **`8`** | `8.2` ✓ |
  | `60` | `12` | **`12`** | `12.4` ✓ |

  Rows animate in one at a time; the `max` column highlights green for the first two
  and **magenta for the third** with a small break-glass icon.

**ON-SCREEN TEXT:** the equation and the 3-row table above.

**NARRATION**
> And that gives us the governing line of the whole project: how many frames one move really
> covers is the larger of the frames we asked for, or the frames that pass while we wait.
> Eight frames or three — take the eight. Eight or five — take the eight. Eight or twelve —
> you don't get a choice. The model's latency wins, and every move stretches to twelve.

**5e — the ceiling (5:00 – 5:15)**

**VISUAL**
- Camera pulls back. A graph draws: x-axis `game speed F`, y-axis `decisions per second`.
- Curve rises straight from origin with slope `1/N` — label `limited by your choice of N`.
- It then **bends and flatlines** at a horizontal amber dashed line labelled
  `1/L = 5 decisions per second`.
- The flat region fills magenta: label `the model's ceiling`.
- **5:10** The derived equation writes itself:

  `decisions/s  =  min( F/N ,  1/L )`

**ON-SCREEN TEXT**
- `min(F/N, 1/L)`
- `1/L = 5 decisions per second`
- `the model's ceiling`

**NARRATION**
> Put together, decisions per second is the smaller of two things: how often the game lets
> you ask — F over N — or how often the model can answer, one over L.
> Which is the punchline. Run the game as fast as you like and the curve just flatlines.
> One over point-two seconds is five. That is a hard ceiling the model puts on everything
> downstream of it.

**SFX:** the `+` → `max` morph gets one signature sound (low bell); nothing else in this scene.

---

### SCENE 6 — THE FIVE LEVERS · 5:15 – 7:25 · (130 s)

**VISUAL** *(uniform pattern, applied five times:)*
Each lever opens with **the equation from Scene 5 centred**, then the **term it attacks
flashes** in its colour, then the equation dims and the **real footage plate** slides up
from the bottom to fill the lower two-thirds, with the flag typed in a terminal chip at
the top-right. Then footage plays full-bleed for the payoff beat.

---

#### LEVER A — Bigger steps · 5:15 – 5:40

**VISUAL**
- Equation centre: `frames per move = max( N , L × F )`. The `N` pulses green.
- A row of 60 tiny cyan squares fills a strip. With `N = 1`, **60 decision markers**
  try to squeeze in — they overlap and magenta-cross out: `60/s — impossible, ceiling is 5`.
- The `N` counts up to `8`. The markers re-space: only `7.5` needed at 60 fps — still above
  5, so a magenta cap clamps them to `5`.
- Flag chip types in: `--frames-per-decision 8`
- Footage: `runs/live_fps15.mp4`, overlay label `N = 8`.

**ON-SCREEN TEXT:** `N` pulses green · `60/s — impossible, ceiling is 5` · `--frames-per-decision 8`

**NARRATION**
> Lever A: make each decision cover more frames. Raise N and you need fewer answers per
> second. But there's a trade — the longer you hold a button, the less responsive Mario
> becomes. Eight frames is a compromise: a fifth of a game-second of steering.

---

#### LEVER B — Ask ahead · 5:40 – 6:15

**VISUAL**
- Equation: the **operator** flashes — `max( N/F , L )`, with the ghost of `+` still visible
  behind it in dim magenta.
- The **two Gantt bars from Scene 5c fly back in** and re-perform the slide from sum→max,
  at half speed, this time with `5.0 decisions/s` counting up in green.
- Numeric proof animates as a two-row comparison:

  ```
  ask after the move:  0.13 + 0.20 = 0.33 s  →  3.0 /s
  ask on applying it:  max(0.13, 0.20) = 0.20 s  →  5.0 /s
  ```

- Flag chip: `--mode pipelined`
- Footage: `runs/live_fps60.mp4` — show **the loop never freezing**: an amber `WAIT` badge
  in the corner stays **off** the whole clip (contrast: if you want, cut to a pre-fix clip
  for 1 s with the badge ON).

**ON-SCREEN TEXT:** `max(N/F, L)` · `0.13 + 0.20 = 0.33 s → 3.0/s` · `max(0.13, 0.20) = 0.20 s → 5.0/s` · `--mode pipelined`

**NARRATION**
> Lever B is the one that took the longest to get right, and it costs nothing. Don't wait
> for the move to finish before asking the next question — ask the instant you apply one.
> The waits overlap, the sum becomes a maximum, and the same model gets fifty percent more
> decisions a second out of exactly the same latency. No extra information, no shortcuts —
> just not idling.

---

#### LEVER C — Smaller picture · 6:15 – 6:50

**VISUAL**
- Equation: `L` flashes amber. Annotation draws: `L depends on payload`.
- A large 640×480 frame appears with a pixel grid. The **long side counts down**
  `640 → 512 → 384 → 256` while a byte counter falls `41 KB → 12 KB → 4 KB`.
  Under it, a token counter falls `→ ~500 tokens` and a cost badge reads `≈ $0.00005`.
- Flag chip: `--max-side 256 --jpeg-quality 80`
- **6:32** The frame is now full-bleed NES footage. A magenta **crop rectangle** slides in
  from the right and cuts off the right third of the screen, where a **Goomba is standing**.
  A red `✗` stamps. Then the crop rectangle **widens back out** to the full frame, the
  Goomba reappears, and a green `✓` stamps with the label `never crop`.
- The compression animation plays in reverse-and-back once more so the point lands.

**ON-SCREEN TEXT:** `L depends on payload` · `640 → 256` · `41 KB → 4 KB` · `~500 tokens ≈ $0.00005` · `--max-side 256 --jpeg-quality 80` · `never crop`

**NARRATION**
> Lever C attacks latency itself: a smaller image means less for the model to ingest, so the
> answer comes back sooner — and it costs a twentieth of a cent a decision either way.
> But there is one absolute rule. Shrink, never crop. If you crop the frame, you hide the
> obstacle you need to react to — and a model that can't see the Goomba will pick the wrong
> move with complete confidence.

---

#### LEVER D — Slow the game down · 6:50 – 7:10

**VISUAL**
- Equation: `F` flashes cyan. Annotation: `staleness ∝ F`.
- A speed dial appears with three detents. As it turns **60 → 30 → 15**, three things
  animate together: the magenta staleness bracket shrinks `12 → 6 → 3`; the cyan tick strip
  under Mario visibly slows; and the green "answer in time" badge starts pulsing.
- Second line appears: `F = S / L`, then substitutes with the two real examples:
  `S = 10, L = 0.25 s → 40 fps` and `L = 1 s → 10 fps`.
- Flag chip: `--fps 15` or `--auto-fps --stale-budget 10`
- Footage: **split screen** — `runs/live_fps15.mp4` (left, calm) vs
  `runs/live_fps60.mp4` (right, stalling). Same agent.

**ON-SCREEN TEXT:** `staleness ∝ F` · `12 → 6 → 3` · `F = S / L` · `S=10, L=0.25s → 40 fps` · `L=1s → 10 fps` · `--auto-fps --stale-budget 10`

**NARRATION**
> Lever D is the most honest one: slow the game down. Staleness scales linearly with speed,
> so halving the frames per second halves how late your answers are — twelve frames becomes
> three. You can even derive the speed from a latency budget: if you're willing to tolerate
> S frames of lag, then the game should run at S over L. Tell it "ten frames of lag is fine"
> and a quarter-second reply gives you forty hertz.

---

#### LEVER E — Skip unchanged frames · 7:10 – 7:25

**VISUAL**
- Equation: `L` flashes amber again, but this time a big `→ 0` animates beside it.
  Annotation: `L = 0 when nothing changed`.
- A 16×16 pixel grid overlays a still game frame; it **downsamples to a coarse 16×16
  fingerprint** (a little block mosaic). The mosaic converts to a short bit-string with a
  soft tick sound.
- A second fingerprint (next frame) slides in and **compares** — a difference meter stays
  in the green zone. Result chip: `SAME → reuse last move`. Counter: `network calls: 0`.
- Then a Goomba enters; the fingerprints differ, meter goes magenta, chip:
  `CHANGED → ask the model`. Counter: `network calls: 1`.
- Flag chip: `--cache`, and a small note `--cache-max-reuse N` and `off for --control blank`.

**ON-SCREEN TEXT:** `L → 0 when nothing changed` · `16×16 fingerprint` · `SAME → reuse last move` · `network calls: 0` · `CHANGED → ask the model` · `--cache` · `off for --control blank`

**NARRATION**
> Lever E: don't ask at all when nothing happened. A coarse sixteen-by-sixteen fingerprint
> of the screen is enough to tell "nothing changed" from "something did" — and when nothing
> changed, you just replay the last move. Zero latency, zero cost. A cap forces a fresh call
> every so often so a frozen screen can't trap the agent, and it's switched off for the
> blank-frame control, where every frame is identical and it would fake a perfect score.

**SFX:** counting ticks on the pixel countdown; one satisfying "clunk" when the crop
rectangle snaps back out.

---

### SCENE 7 — THE RESULT · 7:25 – 8:15 · (50 s)

**VISUAL**
- **7:25** Black. Three vertical panels wipe up simultaneously, each labelled:
  `15 fps` (cyan) · `30 fps` (cyan) · `60 fps` (magenta).
  Each plays its footage in sync: `docs/media/live_fps15.gif`,
  `docs/media/live_fps30.gif`, `docs/media/live_fps60.gif`.
- **7:30** Live counters run above each panel: `frames` · `decisions` · `distance`.
- **7:40** The counters settle: `294 / 36 / 722`, `294 / 36 / 722`, `497 / 40 / 722`.
  The 60 fps panel's `frames` counter visibly overshoots the other two. A small magenta
  badge appears on it: `12 frames per move`.
- **7:46** The three panels slide up and a table draws in their place, row by row:

  ```
   speed   reply   frames/move   decisions   distance
    15 fps  0.19 s       8           36         722
    30 fps  0.16 s       8           36         722
    60 fps  0.20 s      12           40         722
  ```

- **7:56** The `8` cells pulse green; the `12` pulses magenta; the `722` column pulses
  once in white with a label: **`same distance, all three`**.
- **8:08** On the 15 and 30 rows, a bracket joins them and writes itself:
  **`identical game · different clock`**.

**ON-SCREEN TEXT:** the table · `12 frames per move` · `same distance, all three` · `identical game · different clock`

**NARRATION**
> So — what actually happened? We held the step size at eight frames and changed only the
> game's speed, twice each.
> At fifteen and thirty hertz, the model answers before the move ends, so it gets asked at
> exactly the same points — and it plays a pixel-identical game. Same decisions, same frames,
> just stretched over twenty seconds instead of ten. Slow motion turns out to be a viewing
> convenience, not a difficulty setting.
> At sixty hertz it can't keep up: every move stretches to twelve frames, and you can watch
> it stall. That is the speed gap, finally visible.
> And all three finish at the same distance — which is a claim about timing, not about score.

**SFX:** music swells at 7:25 and settles at 8:08.

---

### SCENE 8 — THE HONEST BIT · 8:15 – 8:45 · (30 s)

**VISUAL**
- The table fades. World 1-1 footage plays, desaturated, with a large `?` over it.
- **8:19** The frame **blanks to solid black** (the blank-frame control) while a chip reads
  `--control blank`. VO line lands on this.
- **8:24** The frame returns but the sprites are **recoloured to rectangles** — chip
  `--rom-mode rectangle`.
- **8:30** A magenta card writes one line at a time:
  `World 1-1 is the most-copied level in gaming.` then
  `A good score is not proof of vision.`
- **8:38** A small second card: `2 runs per speed · 1 level · 1 reply spike (0.49 s → x=434)`

**ON-SCREEN TEXT:** `--control blank` · `--rom-mode rectangle` · `World 1-1 is the most-copied level in gaming.` · `A good score is not proof of vision.` · `2 runs per speed · 1 level · 1 reply spike (0.49 s → x=434)`

**NARRATION**
> One caveat before anyone quotes this. World 1-1 is the most reproduced level in gaming,
> and this model has almost certainly seen it many times. A good score on 1-1 is not proof
> that it can see — knowing the level can hide bad timing.
> That's why the repo ships the controls: blank out the screen and see if performance drops,
> recolour the sprites so memorised pixels stop matching, change levels entirely. And why the
> honest headline here is about **latency**, not about skill.

---

### SCENE 9 — CLOSE · 8:45 – 9:10 · (25 s)

**VISUAL**
- Everything wipes. A dark terminal slides up, monospace, and types with key ticks:

  ```
  git clone https://github.com/parjanyaacoder/mario-decisions-agent
  python -m mda --env mario --backend mock --render --scale 3 --fps 30
  ```

- A green badge snaps in: **`runs offline · no API key · 60 seconds`**
- **9:00** The repo URL replaces the terminal, very large, centred, in cyan.
- Under it, three chips fade in one by one:
  `17 offline tests` · `~$0.01 per sweep` · `pixels only, no memory reads`
- Last frame holds the 15 fps gameplay loop silently behind the URL at 15% opacity.

**ON-SCREEN TEXT:** the clone command · `runs offline · no API key · 60 seconds` · the repo URL · `17 offline tests` · `~$0.01 per sweep` · `pixels only, no memory reads`

**NARRATION**
> The whole thing runs offline with no key in sixty seconds — a real NES emulator and a
> stand-in brain on your own machine. If you do want to see it think, it costs about a cent
> for the full sweep.
> The model gives you five decisions a second. Everything else in this video was the glue
> between those five and the other sixty.
> Repository's linked below. Go make it run faster.

**SFX:** music resolves; final 2 s silent under the URL.

---

## 3. Production checklist (verify before rendering)

- [ ] Total runtime ≈ 8:30 (±15 s).
- [ ] **Every narration line has a named visible change** — scan each `VISUAL` against each
      `NARRATION` sentence. This is the rule that failed last time.
- [ ] No static SVG/PNG diagram appears for more than 2 s without a camera move or highlight.
- [ ] Footage appears in Scenes 1, 4, 6 (all five levers), 7, 8, 9 — i.e. it is never more
      than ~90 s absent from the screen.
- [ ] All on-screen numbers match the repo exactly:
      `L ≈ 0.20 s`, `60 fps`, `12 frames`, `N = 8`, `5 decisions/s`, `1.67×`,
      `8 / 8 / 12 frames per move`, `36 / 36 / 40 decisions`, `722` distance,
      `~500 tokens ≈ $0.00005`, `17 tests`, `~$0.01`.
- [ ] Cold-start `4.07 s` is always labelled as cold start, never as steady state.
- [ ] The `sum → max` morph (Scene 5c) is present and legible — it is the thesis.
- [ ] No stock "AI/robot" imagery anywhere.
- [ ] Closing card: repo URL, and the trademark disclaimer from the README in small type.
