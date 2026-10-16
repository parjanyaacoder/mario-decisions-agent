"""Command line entry point: ``python -m mda`` (or the ``mda`` script)."""

from __future__ import annotations

import argparse

from .actions import DEFAULT_ACTIONS
from .backends import (
    FrameTransformBackend,
    JevBackend,
    LiveBackend,
    MockBackend,
    blank_transform,
)
from .cache import CachingBackend
from .env import MarioEnv, MockEnv
from .hud import Hud
from .loop import run_episode
from .recorder import Recorder


def build_env(name: str, args):
    if name == "mario":
        return MarioEnv(
            DEFAULT_ACTIONS,
            world=args.world,
            render=args.render,
            rom_mode=args.rom_mode,
            scale=args.scale,
            record=args.record,
            record_fps=(args.record_fps or args.fps or 60.0),
        )
    if args.render or args.record:
        print("note: --render / --record are only wired for --env mario")
    return MockEnv()


def build_backend(kind: str, args):
    if kind == "mock":
        return MockBackend(DEFAULT_ACTIONS, latency_s=args.mock_latency,
                           seed=args.seed, simulate_latency=args.mock_sleep)
    if kind == "jev":
        # TypeSafe rejects images under 280 px a side, so it wants a slightly
        # *larger* frame than the Decisions path, not a smaller one.
        max_side = args.max_side if args.max_side is not None else 320
        return JevBackend(
            DEFAULT_ACTIONS,
            model=args.typesafe_model,
            jpeg_quality=args.jpeg_quality,
            max_side=max_side,
            save_frames_dir=args.save_frames,
            locate_mario=args.locate_mario,
        )
    max_side = args.max_side if args.max_side is not None else 256
    return LiveBackend(
        DEFAULT_ACTIONS,
        jpeg_quality=args.jpeg_quality,
        max_side=max_side,
        save_frames_dir=args.save_frames,
    )


def format_summary(s: dict) -> str:
    line = (
        f"ep {s.get('episode', 0)}: frames={s['frames']} decisions={s['decisions']} "
        f"stalls={s['stall_frames']} wall={s['wall_s']}s eff_fps={s['effective_fps']} "
        f"avg_lat={s['avg_latency_s']}s calls={s.get('calls')} "
        f"tokens={s.get('input_tokens')} cost=${s.get('cost_usd')}"
    )
    if "cache_hits" in s:
        total = s["cache_hits"] + s["cache_misses"]
        line += f" cached={s['cache_hits']}/{total} ({s['cache_hit_rate']:.0%})"
    return line + f" score={s.get('score')}"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="mda",
        description="Screenshot-only Mario agent driven by a vision model "
                    "(OpenAI Decisions API or TypeSafe System One).",
    )
    p.add_argument("--env", choices=["mock", "mario"], default="mock")
    p.add_argument("--backend", choices=["mock", "live", "jev"], default="mock",
                   help="'live' = OpenAI Decisions API (OPENAI_API_KEY); "
                        "'jev' = TypeSafe System One (TYPESAFE_API_KEY)")
    p.add_argument("--mode", choices=["blocking", "pipelined"], default="pipelined")
    p.add_argument("--frames-per-decision", type=int, default=8,
                   help="frames each macro-action is held (the latency-covering lever)")
    p.add_argument("--fps", type=float, default=60.0,
                   help="wall-clock pacing; 0 = run the emulator as fast as possible")
    p.add_argument("--auto-fps", action="store_true",
                   help="derive the frame rate from measured latency to keep ~--stale-budget "
                        "frames of stale motion per decision (fps ~= stale_budget / latency)")
    p.add_argument("--stale-budget", type=float, default=10.0,
                   help="target frames of stale motion per decision for --auto-fps")
    p.add_argument("--control", choices=["normal", "blank"], default="normal",
                   help="'blank' runs the blanked-frame control arm")
    p.add_argument("--episodes", type=int, default=1)
    p.add_argument("--max-decisions", type=int, default=None)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--world", default="1-1")
    p.add_argument("--rom-mode", default="vanilla",
                   choices=["vanilla", "pixel", "rectangle", "downsample"],
                   help="bundled ROM variant; non-vanilla ones perturb the visuals")
    p.add_argument("--render", action="store_true", help="render the NES window (mario env only)")
    p.add_argument("--scale", type=int, default=3,
                   help="window / recording upscale factor for --env mario (3 => 768x720)")
    p.add_argument("--record", default=None,
                   help="record every frame: 'out.mp4'/'out.gif' for video, or a directory for PNGs")
    p.add_argument("--record-fps", type=float, default=None,
                   help="playback fps of the recording (default: --fps, else 60)")
    p.add_argument("--jpeg-quality", type=int, default=80)
    p.add_argument("--max-side", type=int, default=None,
                   help="longest side of the JPEG sent to the model "
                        "(default: 256 for --backend live, 320 for --backend jev; "
                        "TypeSafe rejects images under 280 px a side)")
    p.add_argument("--typesafe-model", default="jev-preview",
                   help="TypeSafe model alias/id (images need jev-preview / jev-1.14.0)")
    p.add_argument("--locate-mario", action="store_true",
                   help="--backend jev only: also ask a TypeSafe 'box' question for "
                        "Mario's position (recorded, not used to pick the move)")
    p.add_argument("--mock-latency", type=float, default=0.35)
    p.add_argument("--mock-sleep", action="store_true",
                   help="make MockBackend actually sleep for --mock-latency (rehearse the mismatch offline)")
    p.add_argument("--out", default=None, help="JSONL run log path")
    p.add_argument("--save-frames", default=None,
                   help="directory to write every JPEG that is actually sent to the API")
    p.add_argument("--cache", action="store_true",
                   help="Layer E: reuse the last decision when the screen is ~unchanged")
    p.add_argument("--cache-threshold", type=int, default=4,
                   help="max perceptual-hash Hamming distance (of 256 bits) that counts as unchanged")
    p.add_argument("--cache-max-reuse", type=int, default=5,
                   help="force a fresh API call after this many consecutive cache reuses")
    p.add_argument("--no-hud", action="store_true")
    args = p.parse_args(argv)

    hud = Hud(enabled=not args.no_hud)
    recorder = Recorder(args.out)
    # Build the environment once and reuse it across episodes. Recreating the
    # nes-py render window per episode crashes pyglet on macOS (the window cannot
    # be recreated in-process); reusing it lets each run_episode reset the level.
    env = build_env(args.env, args)
    try:
        for episode in range(args.episodes):
            backend = build_backend(args.backend, args)
            if args.cache:
                # The blank control makes every frame identical, so caching would
                # hit every time and stop issuing real calls. Refuse the combo.
                if args.control == "blank":
                    print("note: --cache is disabled for the --control blank arm "
                          "(blank frames are identical by construction)")
                else:
                    backend = CachingBackend(
                        backend,
                        threshold=args.cache_threshold,
                        max_reuse=args.cache_max_reuse,
                    )
            if args.control == "blank":
                backend = FrameTransformBackend(
                    backend, blank_transform, name=f"{backend.name}+blank"
                )
            if args.episodes > 1 and not args.no_hud:
                print(f"\n=== episode {episode + 1}/{args.episodes} ===")
            try:
                summary = run_episode(
                    env,
                    backend,
                    DEFAULT_ACTIONS,
                    frames_per_decision=args.frames_per_decision,
                    mode=args.mode,
                    target_fps=args.fps or None,
                    max_decisions=args.max_decisions,
                    recorder=recorder,
                    hud=hud,
                    seed=args.seed + episode,
                    auto_fps_budget=args.stale_budget if args.auto_fps else None,
                )
            finally:
                backend.close()
            summary["episode"] = episode
            print(format_summary(summary))
    finally:
        env.close()
        recorder.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
