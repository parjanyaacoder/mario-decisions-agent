#!/usr/bin/env python3
"""Turn recorded ``runs/*.mp4`` into small GIFs for the README.

GitHub READMEs cannot autoplay a ``<video>`` pointing at a repo file, but they
*do* autoplay GIFs. So we ship a downscaled GIF (for the inline preview) next
to the full-resolution MP4 (for anyone who wants the real recording).

    python scripts/make_preview_gifs.py                 # runs/*.mp4 -> docs/media/*.gif
    python scripts/make_preview_gifs.py --seconds 6 --width 320 --fps 10
"""

from __future__ import annotations

import argparse
import glob
import os

import numpy as np
from PIL import Image

try:
    import imageio.v2 as iio
except ImportError:  # pragma: no cover
    raise SystemExit("needs imageio + imageio-ffmpeg:  uv pip install '.[record]'")


def make_gif(src: str, dst: str, width: int, fps: float, seconds: float) -> tuple[int, int]:
    reader = iio.get_reader(src)
    meta = reader.get_meta_data()
    src_fps = float(meta.get("fps") or 60.0)
    step = max(1, round(src_fps / fps))
    max_frames = int(seconds * src_fps)

    frames = []
    for i, frame in enumerate(reader):
        if i >= max_frames:
            break
        if i % step:
            continue
        img = Image.fromarray(np.asarray(frame, dtype=np.uint8))
        h = round(width * img.height / img.width)
        img = img.resize((width, h), Image.NEAREST)  # crisp pixels
        frames.append(img.convert("P", palette=Image.ADAPTIVE, colors=128))
    reader.close()

    if not frames:
        raise SystemExit(f"no frames read from {src}")

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    frames[0].save(
        dst,
        save_all=True,
        append_images=frames[1:],
        duration=round(1000 / fps),
        loop=0,
        optimize=True,
        disposal=2,
    )
    return len(frames), os.path.getsize(dst)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-dir", default="runs")
    ap.add_argument("--out-dir", default="docs/media")
    ap.add_argument("--width", type=int, default=320)
    ap.add_argument("--fps", type=float, default=10.0)
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--only", default="live_*.mp4",
                    help="glob of source files to include (default: live runs only)")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    sources = sorted(glob.glob(os.path.join(args.src_dir, args.only)))
    if not sources:
        raise SystemExit(f"no files matching {args.only} in {args.src_dir}")

    for src in sources:
        name = os.path.splitext(os.path.basename(src))[0]
        dst = os.path.join(args.out_dir, name + ".gif")
        # full-size MP4 next to the GIF, so the repo carries the real recording
        mp4_dst = os.path.join(args.out_dir, name + ".mp4")
        if os.path.abspath(src) != os.path.abspath(mp4_dst):
            with open(src, "rb") as fh, open(mp4_dst, "wb") as out:
                out.write(fh.read())
        n, size = make_gif(src, dst, args.width, args.fps, args.seconds)
        print(f"{dst}: {n} frames, {size // 1024} KB  (+ {os.path.basename(mp4_dst)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
