"""The game loop.

Two modes exist because of the speed mismatch between a 60 fps game and a
network decision that takes hundreds of milliseconds:

* ``blocking``   -- capture, ask, then play the action. The game is frozen while
                    the model thinks; simplest to reason about, and honest about
                    the stall.
* ``pipelined``  -- a worker thread keeps a decision request in flight while the
                    emulator keeps stepping with the *previous* action. This is
                    the "overlap thinking with playing" layer: movement stays
                    continuous and the game only stalls if latency exceeds the
                    macro length.
"""

from __future__ import annotations

import threading
import time

from .hud import Hud


class _Worker(threading.Thread):
    """Runs one blocking ``decide`` at a time on a background thread."""

    def __init__(self, backend) -> None:
        super().__init__(daemon=True)
        self.backend = backend
        self._lock = threading.Lock()
        self._frame = None
        self._t = 0
        self._requested = threading.Event()
        self._result = None
        self._ready = threading.Event()
        # NB: do not name this ``_stop`` -- threading.Thread already has an
        # internal ``_stop()`` method and shadowing it breaks join().
        self._stop_event = threading.Event()
        self.error: Exception | None = None

    def request(self, frame, t: int) -> None:
        with self._lock:
            self._frame = frame
            self._t = t
        self._ready.clear()
        self._requested.set()

    def poll(self):
        if not self._ready.is_set():
            return None
        with self._lock:
            result = self._result
            self._result = None
        self._ready.clear()
        return result

    def run(self) -> None:
        while not self._stop_event.is_set():
            if not self._requested.wait(0.1):
                continue
            self._requested.clear()
            with self._lock:
                frame = self._frame
                t = self._t
            try:
                decision = self.backend.decide(frame, t)
            except Exception as exc:  # surfaced to the caller
                self.error = exc
                result = None
            else:
                result = decision
            with self._lock:
                self._result = result
            self._ready.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._requested.set()


def run_episode(env, backend, actions, *, frames_per_decision: int = 8,
                mode: str = "pipelined", target_fps: float | None = 60.0,
                max_decisions: int | None = None, recorder=None,
                hud: Hud | None = None, seed: int = 0,
                auto_fps_budget: float | None = None) -> dict:
    """Run one episode.

    ``auto_fps_budget`` (pipelined mode only): once a real latency is observed,
    set the wall-clock frame rate to ``auto_fps_budget / latency`` (clamped to
    [5, 60]). This keeps roughly that many frames of stale motion per decision,
    so the game is as responsive as the API allows without guesswork. The rule
    of thumb is ``fps ~= 10 / latency_s``.
    """
    action_by_key = {a.key: a for a in actions}
    default = action_by_key.get("RUN_RIGHT") or next(iter(action_by_key.values()))

    frame = env.reset()
    current = default
    frames_on_action = 0
    decisions_made = 0
    stall_frames = 0
    step_count = 0
    latency_sum = 0.0
    last_latency = 0.0
    last_hazard: float | None = None
    done = False

    # Effective wall-clock rate. With auto mode we start conservatively at 30
    # and adjust after the first measured latency.
    pace_fps = target_fps
    if auto_fps_budget is not None and pace_fps is None:
        pace_fps = 30.0

    start = time.perf_counter()
    next_deadline = start

    def snapshot_score() -> dict:
        s = env.score()
        return s if isinstance(s, dict) else {}

    def emit(decision) -> None:
        nonlocal latency_sum
        latency_sum += decision.latency_s
        if recorder:
            recorder.write({
                "type": "decision",
                "index": decisions_made,
                "frame": step_count,
                "t": round(time.perf_counter() - start, 3),
                "move": decision.move,
                "move_confidence": decision.move_confidence,
                "move_probs": decision.move_probs,
                "hazard_prob": decision.hazard_prob,
                "latency_s": decision.latency_s,
                "refused": decision.refused,
                "cached": decision.cached,
                "mario_box": decision.mario_box,
                "model": decision.model,
                "note": decision.note,
                "score": snapshot_score(),
            })

    def push_hud() -> None:
        if not hud:
            return
        elapsed = time.perf_counter() - start
        hud.update(
            frames=step_count,
            fps=step_count / elapsed if elapsed else 0.0,
            decisions=decisions_made,
            latency=last_latency,
            move=current.key,
            hazard=last_hazard,
            x=snapshot_score().get("x"),
            held=frames_on_action,
            cost=backend.cost_usd,
        )

    def pace() -> None:
        """Throttle to ``pace_fps`` frames per wall-clock second (slow motion)."""
        nonlocal next_deadline
        if not pace_fps:
            return
        next_deadline += 1.0 / pace_fps
        now = time.perf_counter()
        if now < next_deadline:
            time.sleep(next_deadline - now)
        elif now - next_deadline > 0.25:
            next_deadline = now  # fell too far behind; resync

    def retune(latency: float) -> None:
        nonlocal pace_fps
        if auto_fps_budget is not None and latency > 0:
            pace_fps = min(60.0, max(5.0, auto_fps_budget / latency))

    try:
        if mode == "blocking":
            while not done:
                decision = backend.decide(frame.copy(), decisions_made)
                decisions_made += 1
                emit(decision)
                current = action_by_key.get(decision.move, default)
                last_latency = decision.latency_s
                last_hazard = decision.hazard_prob
                retune(last_latency)
                for f in range(frames_per_decision):
                    frame, done = env.step_buttons(current.button_mask(f))
                    step_count += 1
                    frames_on_action = f + 1
                    push_hud()
                    pace()
                    if done:
                        break
                if max_decisions and decisions_made >= max_decisions:
                    break
        else:
            worker = _Worker(backend)
            worker.start()
            # Ask for the very first move straight away; the fallback action
            # plays until the answer lands.
            worker.request(frame.copy(), 0)
            outstanding = True
            pending = None  # an answer that came early, waiting for a macro to end
            try:
                while not done:
                    # Collect the answer as soon as the worker has it...
                    if outstanding:
                        decision = worker.poll()
                        if decision is not None:
                            pending = decision
                            outstanding = False

                    # ...but only switch moves on a macro boundary, so every
                    # action gets its full frames_per_decision of play. Asking
                    # for the *next* move the moment we switch is what hides the
                    # latency: the model thinks while this action still plays.
                    # We stall only when latency outlasts the macro.
                    if pending is not None and frames_on_action >= frames_per_decision:
                        current = action_by_key.get(pending.move, default)
                        decisions_made += 1
                        emit(pending)
                        frames_on_action = 0
                        last_latency = pending.latency_s
                        last_hazard = pending.hazard_prob
                        retune(last_latency)
                        pending = None
                        worker.request(frame.copy(), decisions_made)
                        outstanding = True

                    frame, done = env.step_buttons(current.button_mask(frames_on_action))
                    step_count += 1
                    frames_on_action += 1
                    if frames_on_action > frames_per_decision:
                        stall_frames += 1

                    if step_count % 5 == 0:
                        push_hud()

                    pace()

                    if max_decisions and decisions_made >= max_decisions:
                        break

                if worker.error:
                    raise worker.error
            finally:
                worker.stop()
                worker.join(timeout=2.0)
    finally:
        if hud:
            hud.finish()

    wall = time.perf_counter() - start
    summary = {
        "type": "summary",
        "mode": mode,
        "frames_per_decision": frames_per_decision,
        "target_fps": target_fps,
        "effective_fps_setting": pace_fps,
        "frames": step_count,
        "decisions": decisions_made,
        "stall_frames": stall_frames,
        "wall_s": round(wall, 3),
        "effective_fps": round(step_count / wall, 1) if wall else 0.0,
        "avg_latency_s": round(latency_sum / decisions_made, 3) if decisions_made else 0.0,
        "score": snapshot_score(),
    }
    summary.update(backend.stats())
    if recorder:
        recorder.write(summary)
    return summary
