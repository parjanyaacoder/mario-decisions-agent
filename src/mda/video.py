"""Headless frame recording.

Pass ``--record out.mp4`` and every frame the agent plays is written to a video
(nearest-neighbour upscaled by ``--scale``). Pass a directory instead of a video
extension and the frames are written as a PNG sequence.

Video writing uses ``imageio`` + the bundled ``imageio-ffmpeg`` (no system
ffmpeg required). The PNG fallback needs only Pillow. Recording works with or
without ``--render``: ``--record`` alone records headlessly.
"""

from __future__ import annotations

import os

import numpy as np

VIDEO_EXTS = (".mp4", ".gif", ".webm", ".mov")


def upscale(frame: np.ndarray, scale: int) -> np.ndarray:
    """Integer nearest-neighbour upscale -- crisp pixels, no blurring."""
    frame = np.asarray(frame, dtype=np.uint8)
    if scale and scale > 1:
        frame = np.repeat(np.repeat(frame, scale, axis=0), scale, axis=1)
    return frame


class VideoRecorder:
    """Write frames to a video file, or a PNG sequence if given a directory."""

    def __init__(self, path: str, fps: float = 60.0, scale: int = 1) -> None:
        self.path = path
        self.fps = max(1.0, float(fps))
        self.scale = max(1, int(scale))
        self.frames = 0
        self._writer = None
        self._png_dir = None

        if path.lower().endswith(VIDEO_EXTS):
            try:
                import imageio
            except ImportError as exc:  # pragma: no cover - depends on install
                raise SystemExit(
                    "--record to a video needs imageio + imageio-ffmpeg:\n"
                    "    uv pip install 'imageio[ffmpeg]'\n"
                    "or pass a directory path to write a PNG sequence instead."
                ) from exc
            self._writer = imageio.get_writer(path, fps=self.fps, macro_block_size=None)
        else:
            os.makedirs(path, exist_ok=True)
            self._png_dir = path

    def add(self, frame: np.ndarray) -> None:
        frame = upscale(frame, self.scale)
        if self._writer is not None:
            self._writer.append_data(frame)
        else:
            from PIL import Image

            name = f"frame_{self.frames:06d}.png"
            Image.fromarray(frame).save(os.path.join(self._png_dir, name))
        self.frames += 1

    def close(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:
                pass
            self._writer = None
