#!/usr/bin/env python3
"""One-shot latency probe: send a single frame to /v1/decisions and report timing.

This is the cheapest possible check and answers the single most important
unknown of the whole project: how long does one decision actually take? Run it
before building anything else.

    export OPENAI_API_KEY=sk-...
    python scripts/probe_latency.py --repeats 3
    python scripts/probe_latency.py --blank        # blanked-frame control
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from mda.actions import DEFAULT_ACTIONS  # noqa: E402
from mda.backends import LiveBackend, blank_transform  # noqa: E402
from mda.env import MockEnv  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe /v1/decisions latency with one frame.")
    parser.add_argument("--blank", action="store_true", help="send a blank frame (control arm)")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--jpeg-quality", type=int, default=80)
    parser.add_argument("--max-side", type=int, default=256)
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set. Export it first.", file=sys.stderr)
        return 2

    frame = MockEnv().reset()
    if args.blank:
        frame = blank_transform(frame)

    backend = LiveBackend(
        DEFAULT_ACTIONS, jpeg_quality=args.jpeg_quality, max_side=args.max_side
    )
    latencies = []
    for i in range(args.repeats):
        decision = backend.decide(frame, i)
        latencies.append(decision.latency_s)
        print(
            f"[{i + 1}/{args.repeats}] {decision.latency_s:.3f}s  "
            f"move={decision.move} (conf={decision.move_confidence})  "
            f"hazard={decision.hazard_prob}  refused={decision.refused}  {decision.note}"
        )

    print(
        f"\nlatency: min={min(latencies):.3f}s  max={max(latencies):.3f}s  "
        f"mean={sum(latencies) / len(latencies):.3f}s"
    )
    print(json.dumps(backend.stats(), indent=2))
    backend.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
