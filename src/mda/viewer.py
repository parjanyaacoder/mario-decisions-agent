"""A large, pixel-crisp, resizeable viewer for the NES frames.

We deliberately do **not** use nes-py's bundled ``ImageViewer``:

* it opens a fixed 256x240 window (too small to record legibly);
* on macOS a closed pyglet window cannot be re-created in the same process, so
  opening a second one raises ``AttributeError`` from pyglet's Cocoa backend.

Instead we own one pyglet window that we can open at an integer ``scale``
(``--scale 3`` -> 768x720), keep sharp with nearest-neighbour filtering, resize
freely, and shut down cleanly when the user clicks the close button (instead of
crashing on the next frame).
"""

from __future__ import annotations

import numpy as np

FRAME_W, FRAME_H = 256, 240


class Viewer:
    """Display NES frames in a resizeable pyglet window."""

    def __init__(self, caption: str = "mda", scale: int = 3) -> None:
        self.caption = caption
        self.scale = max(1, int(scale))
        self.width = FRAME_W * self.scale
        self.height = FRAME_H * self.scale
        self.closed = False
        self._window = None
        self._image = None
        self._sprite = None
        self._pyglet = None

    # -- lifecycle -----------------------------------------------------------
    def _ensure(self) -> None:
        if self._window is not None or self.closed:
            return
        import pyglet

        self._pyglet = pyglet
        self._window = pyglet.window.Window(
            caption=self.caption,
            width=self.width,
            height=self.height,
            resizable=True,
            vsync=False,
        )

        @self._window.event
        def on_close() -> None:  # user clicked the close button
            self.closed = True

        @self._window.event
        def on_draw() -> None:
            self._draw()

    def _draw(self) -> None:
        if self._window is None:
            return
        pyglet = self._pyglet
        self._window.clear()
        if self._sprite is None:
            return
        # Fill the window; if the user resized it, the pixels stay square-ish
        # by scaling x and y independently.
        self._sprite.scale_x = self._window.width / FRAME_W
        self._sprite.scale_y = self._window.height / FRAME_H
        self._sprite.draw()

    def show(self, frame: np.ndarray) -> None:
        """Blit one RGB frame (H, W, 3) to the window."""
        self._ensure()
        if self.closed or self._window is None:
            return
        pyglet = self._pyglet
        frame = np.ascontiguousarray(frame, dtype=np.uint8)
        pitch = frame.shape[1] * -3  # negative => top row first
        if self._image is None:
            self._image = pyglet.image.ImageData(
                frame.shape[1], frame.shape[0], "RGB", frame.tobytes(), pitch=pitch
            )
            texture = self._image.get_texture()
            gl = pyglet.gl
            texture.min_filter = gl.GL_NEAREST
            texture.mag_filter = gl.GL_NEAREST
            self._sprite = pyglet.sprite.Sprite(texture, 0, 0)
        else:
            self._image.set_data("RGB", pitch, frame.tobytes())

        self._window.switch_to()
        self._window.dispatch_events()  # keep the window responsive
        self._window.clear()
        self._draw()
        self._window.flip()

    def close(self) -> None:
        self.closed = True
        if self._window is not None:
            try:
                self._window.close()
            except Exception:
                pass
            self._window = None
