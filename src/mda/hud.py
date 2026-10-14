"""A minimal terminal HUD: FPS, latency, current pick, hazard probability, cost."""

from __future__ import annotations

import sys


def format_status(state: dict) -> str:
    hazard = state.get("hazard")
    hazard_s = "  -  " if hazard is None else f"{hazard:.2f}"
    cost = state.get("cost") or 0.0
    return (
        f"t={state.get('frames', 0):>6}  "
        f"fps={state.get('fps', 0.0):>5.1f}  "
        f"dec={state.get('decisions', 0):>4}  "
        f"lat={state.get('latency', 0.0):>5.2f}s  "
        f"move={str(state.get('move', '-')):<16}  "
        f"haz={hazard_s}  "
        f"x={state.get('x', '-')!s:>5}  "
        f"held={state.get('held', 0):>3}  "
        f"${cost:.4f}"
    )


class Hud:
    """Writes a single self-overwriting status line to stdout."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def update(self, **state) -> None:
        if not self.enabled:
            return
        sys.stdout.write("\r" + format_status(state)[:180].ljust(150))
        sys.stdout.flush()

    def finish(self) -> None:
        if self.enabled:
            sys.stdout.write("\n")
            sys.stdout.flush()
