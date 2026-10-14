<div align="center">

# 🍄 mario-decisions-agent

### An AI that plays Super Mario Bros by *looking* at the screen — one screenshot at a time.

No memory hacks. No hidden game state. Pixels in, button out.

![python](https://img.shields.io/badge/python-3.12-blue)
![status](https://img.shields.io/badge/status-experimental-orange)
![platform](https://img.shields.io/badge/platform-macOS%20%C2%B7%20Linux-lightgrey)

<img src="docs/media/live_fps15.gif" width="440" alt="An AI model playing Super Mario Bros World 1-1 from raw screenshots">

<sub>An AI model playing World 1-1 from raw screenshots — slowed down so you can watch.</sub>

</div>

---

## What is this?

Most bots that play games cheat a little. They read the game's memory to find out exactly
where Mario is, how fast he's moving, and what's coming next — then choose a button.
**This one can't do any of that.** It sees what you'd see in a screenshot: one frozen
picture of the level. Its entire brain is a remote vision model on the other end of the
OpenAI **Decisions API**, and the only thing it is ever asked is:

> *"Here's a picture of the screen. Which move gets me further?"*

That limitation is the whole point, because it turns the project into a clean, honest
test of a genuinely open question:

> **How well can a modern vision model play a real-time game when it can only look at
> still pictures and reply a few times per second?**

The short answer: surprisingly well. The *interesting* answer is where it breaks — and
why. Super Mario Bros updates its world **60 times every second**. The model can only
answer about **5 times per second**. Closing that gap is what this repo is about.

## The problem: two clocks that don't agree

Imagine playing Mario, but with a twist: after every move you have to phone a very smart
friend, describe the screen, and wait for them to tell you what to do next. You can only
react as fast as they answer.

- The **game** never waits. It advances 60 steps every second.
- The **model** takes about **0.2 seconds** to reply — so at best it gets to decide about
  **5 times a second**.

While the model is thinking, Mario keeps running. Get the timing wrong and he walks
straight into a Goomba. Managing that timing — *without* secretly feeding the model extra
information — is the entire project.

<p align="center">
  <img src="docs/speed-gap.svg" width="100%" alt="The model takes about 0.2 seconds to answer. At 60 frames per second, 12 game frames pass while it thinks; at 15 frames per second, only 3 do.">
</p>

## How well does it actually do?

Measured, not guessed. The model's steady reply time is **~0.20 s**, which caps how often
it can possibly decide. Speed the game up and you can *watch* it fall apart:

| Run | Game speed | Each move lasts | Decisions | Outcome | Distance reached | Cost | Watch |
|---|--:|--:|--:|---|--:|--:|---|
| **A** | 15 fps | 8 frames | **40** | survived (hit the time budget) | **722** | $0.002 | [▶](docs/media/live_fps15.mp4) |
| **B** | 30 fps | 12 frames | **19** | died | **694** | $0.001 | [▶](docs/media/live_fps30.mp4) |
| **C** | 60 fps | 20 frames | **3** | died | **315** | $0.0002 | [▶](docs/media/live_fps60.mp4) |

Two simple rules fall out of this, and they *are* the project:

```
decisions per second of GAME   =  60 / frames_per_decision     # how often we get to think
game-frames that pass per call =  latency × game_fps           # how stale the picture is when the answer lands
```

At 15 fps an answer is only ~2.4 frames old by the time it lands — quick enough to play.
At full 60 fps it arrives ~11 frames late: Mario has already sprinted blind for a sixth
of a second, and he dies. **Slow motion isn't a gimmick here — it's the only thing that
makes the model's reaction time usable.**

*(Fair warning: these three runs changed game speed and decision length together, so
"faster game → worse" is real but not purely a speed effect. See [Honest limits](#honest-limits).)*

## Watch the three runs

| 15 fps — survives | 30 fps — dies after 19 decisions | 60 fps — dead in 3 |
|---|---|---|
| <img src="docs/media/live_fps15.gif" width="260"> | <img src="docs/media/live_fps30.gif" width="260"> | <img src="docs/media/live_fps60.gif" width="260"> |

At 15 fps you're watching genuine slow motion — the game is deliberately throttled so the
model has time to think. At 60 fps it's full speed, and Mario is dead in under two seconds.

## Try it in 60 seconds

The emulator, the game loop, and an offline stand-in "brain" all run locally — **no API
key, no network, no ROM download**:

```bash
git clone https://github.com/parjanyaacoder/mario-decisions-agent
cd mario-decisions-agent
uv venv --python 3.12
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
uv pip install -e ".[mario,record]"

python -m mda --env mario --backend mock --render --scale 3 --fps 30 --frames-per-decision 8
```

A window opens and a simple offline heuristic plays the game using the *exact same loop*
the real model uses. Swap `--backend mock` for `--backend live` (plus a key) and the
remote model takes the controls.

---

## How it works

Three pieces, cleanly separated — and each one swappable, which is why the whole thing
can run offline:

- **The world** — a real NES emulator stepping the game 60 times a second.
- **The brain** — a remote model that sees one small JPEG and returns one move.
- **The loop** — the glue that keeps a 60 Hz world and a ~5 Hz brain in sync.

<p align="center">
  <img src="docs/architecture.svg" width="100%" alt="Architecture: the game steps 60 times a second; the loop takes a screenshot and asks the model; the model answers about 5 times a second; the loop presses the chosen move for the next few frames.">
</p>

**One decision, end to end:**

1. The emulator advances **one frame** and hands back an RGB picture.
2. The loop shrinks it to a small JPEG and asks the model two things: *which move next?*
   and *is a hazard coming up?*
3. The model answers with one of **10 sensible moves** — run right, short hop, high jump,
   wait, back up, and so on — instead of raw button mashing.
4. The loop presses that move and lets it play out for a few frames — while the *next*
   question is already on its way to the model.

### Project layout

```
src/mda/
  actions.py    10-move macro menu (held + tapped buttons, per-frame masks)
  env.py        MockEnv (offline toy platformer) + MarioEnv (real NES, lazy import)
  backends.py   MockBackend (offline heuristic) + LiveBackend (/v1/decisions)
  cache.py      trick E: perceptual-hash frame cache
  viewer.py     resizeable, pixel-crisp game window
  video.py      headless MP4 / GIF / PNG recording
  loop.py       blocking + pipelined game loops, frame pacing
  hud.py        on-screen HUD (fps, latency, chosen move, cost)
  recorder.py   JSONL run log
  __main__.py   command-line interface
scripts/
  probe_latency.py       measure the model's real reply time — run this first
  make_preview_gifs.py   turn recorded runs into the clips in docs/media
tests/test_pipeline.py   16 offline tests: no key, no ROM, no network
```

Curious how it runs with no key? `MockEnv` is a tiny hand-built platformer — gravity,
variable jumps, pits, pipes, Goombas, scrolling — that exercises the whole loop offline.
`MockBackend` is a crude pixel heuristic that plays the real game well enough to rehearse
the timing.

## Five tricks for closing the gap

The game is a firehose of frames; the model is a slow, expensive advisor. Each trick below
buys back a little responsiveness, and all five are switchable from the command line:

| | Trick | Flag | What it buys |
|---|---|---|---|
| **A** | **Bigger steps** | `--frames-per-decision N` | one answer covers N frames instead of one |
| **B** | **Ask ahead** | `--mode pipelined` | the next question is already in flight while the game keeps moving |
| **C** | **Send a smaller picture** | `--max-side` / `--jpeg-quality` | less image → faster, cheaper answers (**smaller, never cropped**) |
| **D** | **Slow the game down** | `--fps N` / `--auto-fps` | genuine slow motion, so a quick reply becomes fine control |
| **E** | **Skip identical frames** | `--cache` | if the screen barely changed, replay the last move |

**D can calculate itself.** Give it a latency budget (`--auto-fps --stale-budget 10`) and
it picks the game speed for you: 0.25 s → ~40 fps, 1 s → ~10 fps. Slower game, more
responsive agent — but a longer watch.

**C never crops.** It shrinks and compresses the image but keeps the *full* field of view.
Crop it and you hide the Goomba, and a model that can't see the Goomba picks the wrong
move. `--save-frames DIR` dumps exactly what was sent so you can check.

**E is a latency and cost trick, not a skill trick.** Frames are compared with a coarse
16×16 perceptual hash, so "the screen barely moved" can reuse the last move — but
`--cache-max-reuse` forces a fresh call so a frozen screen can't lock the agent in place.
It's deliberately switched off for the blank-frame control, where every frame is identical
and the cache would fake a perfect score.

---

## What actually broke (the honest log)

Every item here has code and a test behind it. This is the part of the project that took
the longest and taught the most.

**1. One measurement that reframed everything.** The very first live call took **4.07
seconds** — which looked fatal for a real-time game. The next five took **0.17–0.23 s**.
That first number was a cold start; the steady state is **~0.20 s**, which turns
"impossible" into "genuinely near-real-time at low speeds". Lesson: measure the model
before you design around it.

**2. The API occasionally throws a `503`.** A single mid-run blip would have killed an
entire recording. Added exponential-backoff retries for `408/409/425/429/5xx`, plus a test
that fires two `503`s and then a success.

**3. A crash that only happens on the second game.** On macOS, the emulator's own window
can only be created once per process — the second attempt dies with a cryptic
`PygletDelegate` error. Fixed by building the environment once and reusing it, and by
replacing the stock game window with one that resizes nicely and closes cleanly.

**4. A flag that silently did nothing.** Game-speed pacing was wired into only one of the
two loop modes, so "slow" runs in the other mode raced by at thousands of frames a second.
Pacing is now shared by both loops.

**5. What counts as "nothing changed"?** An exact pixel match would essentially never fire
in a moving game. The useful version is a coarse perceptual hash — sensitive enough to
catch a genuinely still screen, loose enough not to reuse a stale move when something new
creeps into the frame.

**6. Dependency pins for real bugs.** `numpy<2` (older `nes-py` overflows) and `gym<0.26`
(the API changed shape). The bundled game ROM means there's nothing extra to download, and
it ships sprite-perturbed variants we use as controls.

## Proving it's actually *seeing*

A model that has memorized World 1-1 could look good without seeing anything. This repo is
built to be *disbelieved*, so it ships controls:

- **Blank-frame control** (`--control blank`) — run the identical pipeline on a featureless
  frame. If performance barely drops, the model is recalling, not looking.
- **Perturbed sprites** (`--rom-mode pixel|rectangle|downsample`) — swap the graphics so
  familiar pixel patterns can't be memorized.
- **Unseen levels** (`--world …`) — so layout memory is useless.
- **Score-only memory.** The emulator's internal state (position, lives, time) is used to
  *grade* runs and is **never** put in the model's prompt. The model only ever sees pixels.
- **Full logging.** `--save-frames` writes every image sent; `--record` writes the played
  frames; `--out` writes a per-decision log.

## Honest limits

Read this before quoting any number above.

- **World 1-1 is probably memorized.** It's the most-reproduced level in gaming, and the
  model's knowledge is well past it. A good score here is **not** proof of vision — which is
  exactly why the controls exist.
- **One run each.** Runs A–C are single episodes; "faster is worse" is suggestive, not
  statistically proven.
- **Speed and step size moved together.** The sweep changed both `frames-per-decision` and
  fps, so it shows "faster game → worse" without isolating speed alone. A clean run holds
  step size fixed and adds seeds.
- **Slow motion isn't real time.** At 15 fps the game runs 4× slower than a human would see
  it. "Near-real-time" honestly means ~30–60 fps, where the agent is much weaker.

## Using the real model

Grab a standard OpenAI key — the Decisions API is public beta, no waitlist. Then measure
first, play second:

```bash
export OPENAI_API_KEY=sk-...

python scripts/probe_latency.py --repeats 5   # measure the model's real reply time
python -m mda --env mario --backend live --auto-fps --cache \
    --scale 3 --record runs/live.mp4          # watch it play (and save the video)
```

Prefer it fully offline? Both examples work with `--backend mock` and no key at all.

### Key flags

| Flag | Meaning |
| --- | --- |
| `--env mock\|mario` | toy platformer vs. real game |
| `--backend mock\|live` | offline stand-in vs. the real model |
| `--mode blocking\|pipelined` | freeze during thinking vs. overlap it |
| `--frames-per-decision N` | how many frames each move is held |
| `--fps N` | how fast the game runs in real time (`0` = as fast as possible) |
| `--auto-fps` / `--stale-budget` | pick the game speed from measured latency |
| `--control normal\|blank` | run the blank-frame control |
| `--max-side` / `--jpeg-quality` | image budget — the main speed/cost lever |
| `--world` / `--rom-mode` | which level, and which sprite set (`vanilla`/`pixel`/`rectangle`/`downsample`) |
| `--render` / `--scale N` | show the game window, at N× size |
| `--record PATH` / `--record-fps` | save the run as `out.mp4`/`.gif` or a folder of PNGs |
| `--cache` / `--cache-threshold` / `--cache-max-reuse` | the reuse-unchanged-frames trick |
| `--save-frames DIR` | dump every image actually sent to the model |
| `--out PATH` | write a per-decision JSONL log |
| `--mock-latency` / `--mock-sleep` | simulate latency to rehearse timing offline |

## Reproduce these results

```bash
export OPENAI_API_KEY=sk-...
python scripts/probe_latency.py --repeats 5         # expect ~0.20 s

for fps in 15 30 60; do
  case $fps in 15) fpd=8;; 30) fpd=12;; 60) fpd=20;; esac
  python -m mda --env mario --backend live --mode pipelined \
      --fps $fps --frames-per-decision $fpd --max-decisions 40 \
      --scale 3 --record runs/live_fps$fps.mp4 --no-hud
done
```

Run the offline test suite any time with `python tests/test_pipeline.py` (16 tests, no key
or network).

## Cost

The Decisions API bills **input only** — $0.10 per million tokens, nothing for output. A
single frame is about **1,050 tokens ≈ $0.0001**, so one decision costs a hundredth of a
cent. The entire three-run demo above cost **under half a cent**. Cost is never the
bottleneck here — latency is.

## Roadmap

- **A clean speed sweep** — fix the step size, vary only fps, add seeds, to separate speed
  from step length.
- **Run the controls for real** — blank frames and perturbed sprites on 1-1, to separate
  seeing from remembering.
- **Unseen levels** — grade on layouts the model can't have memorized.
- **Ask even earlier** — request the next decision just *before* the current move ends, so
  latency is hidden instead of paid for.

## License

MIT — see [LICENSE](LICENSE).

<div align="center"><sub>Not affiliated with Nintendo or OpenAI. Super Mario Bros is a trademark of Nintendo; the game ROM is bundled by <code>gym-super-mario-bros</code> for research use.</sub></div>
