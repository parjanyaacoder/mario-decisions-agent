#!/usr/bin/env python3
"""One-shot latency probe: send a single frame to a vision model and report timing.

This is the cheapest possible check and answers the single most important
unknown of the whole project: how long does one decision actually take? Run it
before building anything else. Its output feeds straight into
``--auto-fps``/``--frames-per-decision`` and into the maths in the README.

    export OPENAI_API_KEY=sk-...
    python scripts/probe_latency.py --repeats 3

    export TYPESAFE_API_KEY=...
    python scripts/probe_latency.py --backend jev --repeats 3
    python scripts/probe_latency.py --backend jev --locate-mario   # also box Mario

    python scripts/probe_latency.py --blank        # blanked-frame control
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from mda.actions import DEFAULT_ACTIONS  # noqa: E402
from mda.backends import JevBackend, LiveBackend, blank_transform  # noqa: E402
from mda.env import MockEnv  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe one vision-model call's latency.")
    parser.add_argument("--backend", choices=["live", "jev"], default="live",
                        help="'live' = OpenAI Decisions API, 'jev' = TypeSafe System One")
    parser.add_argument("--blank", action="store_true", help="send a blank frame (control arm)")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--jpeg-quality", type=int, default=80)
    parser.add_argument("--max-side", type=int, default=None,
                        help="default: 256 for --backend live, 320 for --backend jev")
    parser.add_argument("--typesafe-model", default="jev-preview")
    parser.add_argument("--locate-mario", action="store_true",
                        help="--backend jev only: also ask a 'box' question for Mario")
    args = parser.parse_args()

    if args.backend == "jev":
        key_env = "TYPESAFE_API_KEY"
    else:
        key_env = "OPENAI_API_KEY"
    if not os.environ.get(key_env):
        print(f"{key_env} is not set. Export it first.", file=sys.stderr)
        return 2

    frame = MockEnv().reset()
    if args.blank:
        frame = blank_transform(frame)

    max_side = args.max_side if args.max_side is not None else (320 if args.backend == "jev" else 256)
    if args.backend == "jev":
        backend = JevBackend(
            DEFAULT_ACTIONS, jpeg_quality=args.jpeg_quality, max_side=max_side,
            model=args.typesafe_model, locate_mario=args.locate_mario,
        )
    else:
        backend = LiveBackend(
            DEFAULT_ACTIONS, jpeg_quality=args.jpeg_quality, max_side=max_side
        )

    latencies = []
    for i in range(args.repeats):
        decision = backend.decide(frame, i)
        latencies.append(decision.latency_s)
        box = ""
        if decision.mario_box:
            b = decision.mario_box
            box = (f"  mario_box=({b['left']:.2f},{b['top']:.2f})-"
                   f"({b['right']:.2f},{b['bottom']:.2f})")
        print(
            f"[{i + 1}/{args.repeats}] {decision.latency_s:.3f}s  "
            f"move={decision.move} (conf={decision.move_confidence})  "
            f"hazard={decision.hazard_prob}  refused={decision.refused}  "
            f"{decision.note}{box}"
        )

    mean = sum(latencies) / len(latencies)
    print(
        f"\nlatency: min={min(latencies):.3f}s  max={max(latencies):.3f}s  "
        f"mean={mean:.3f}s"
    )
    print(f"hint: --auto-fps --stale-budget 10  =>  {10.0 / mean:.1f} fps" if mean else "")
    print(json.dumps(backend.stats(), indent=2))
    backend.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
