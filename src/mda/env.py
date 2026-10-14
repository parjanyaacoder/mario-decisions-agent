"""Game environments.

The agent only ever sees an RGB frame. ``MarioEnv`` wraps the real NES
emulator; ``MockEnv`` is a tiny procedural side-scroller so the whole pipeline
can run with no emulator and no ROM. Both expose the same interface:

    frame = env.reset()
    frame, done = env.step_buttons(pressed)   # advances exactly ONE frame
    state = env.score()                       # judge-only; never given to the model
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

FRAME_W, FRAME_H = 256, 240
GROUND_TOP = 208
MARIO_W = MARIO_H = 16

#: Our uppercase button names -> the strings JoypadSpace expects.
BUTTON_MAP = {
    "RIGHT": "right",
    "LEFT": "left",
    "UP": "up",
    "DOWN": "down",
    "A": "A",
    "B": "B",
    "START": "start",
    "SELECT": "select",
}


@runtime_checkable
class GameEnv(Protocol):
    frame_shape: tuple[int, int]

    def reset(self) -> np.ndarray: ...

    def step_buttons(self, pressed: frozenset[str]) -> tuple[np.ndarray, bool]: ...

    def score(self) -> dict: ...

    def close(self) -> None: ...


class MockEnv:
    """Deterministic toy platformer: no ROM, no emulator, no native build.

    It is *not* Mario. It exists so the loop, HUD, macro-actions, pipelining and
    logging can be exercised end-to-end offline. It deliberately mimics the bits
    that matter for our loop: gravity, variable jump height, run speed, pits,
    pipes, enemies, scrolling, and a win condition.
    """

    frame_shape = (FRAME_W, FRAME_H)
    LEVEL_LENGTH = 1700
    PITS = ((600, 680), (1100, 1180))
    OBSTACLES = (
        (320, "pipe"),
        (520, "goomba"),
        (780, "pipe"),
        (900, "goomba"),
        (1230, "goomba"),
        (1420, "pipe"),
    )

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> np.ndarray:
        self.x = 40.0
        self.y = float(GROUND_TOP - MARIO_H)
        self.vy = 0.0
        self.on_ground = True
        self.win = False
        self.dead = False
        self.done = False
        self.t = 0
        self.obstacles = [list(rect) for rect in self._initial_obstacles()]
        return self.render()

    def _over_pit(self, world_x: float) -> bool:
        center = world_x + MARIO_W / 2
        return any(a <= center <= b for a, b in self.PITS)

    def _initial_obstacles(self) -> list[tuple[float, float, float, float, str]]:
        rects = []
        for ox, kind in self.OBSTACLES:
            if kind == "pipe":
                rects.append((float(ox), float(GROUND_TOP - 32), 32.0, 32.0, "pipe"))
            else:
                rects.append((float(ox), float(GROUND_TOP - 16), 16.0, 16.0, "goomba"))
        return rects

    def _resolve_obstacles(self) -> bool:
        """Apply collisions. Stomping a Goomba removes it and bounces Mario.

        Returns True if Mario died. Pipes are always lethal; a Goomba is lethal
        unless Mario is falling onto its top.
        """
        mx, my = self.x, self.y
        alive: list[list] = []
        died = False
        for ox, oy, ow, oh, kind in self.obstacles:
            overlap = (
                mx < ox + ow and ox < mx + MARIO_W
                and my < oy + oh and oy < my + MARIO_H
            )
            if not overlap:
                alive.append([ox, oy, ow, oh, kind])
                continue
            if kind == "goomba" and self.vy > 0 and (my + MARIO_H) < oy + oh:
                self.vy = -6.0  # stomp: bounce, Goomba deleted
                continue
            died = True
            alive.append([ox, oy, ow, oh, kind])
        self.obstacles = alive
        return died

    def step_buttons(self, pressed: frozenset[str]) -> tuple[np.ndarray, bool]:
        if self.done:
            return self.render(), True

        right = "RIGHT" in pressed
        left = "LEFT" in pressed
        run = "B" in pressed
        jump = "A" in pressed

        vx = 0.0
        if right:
            vx = 5.0 if run else 3.0
        if left:
            vx = -(5.0 if run else 3.0)

        if jump and self.on_ground:
            self.vy = -9.0
            self.on_ground = False
        if not jump and self.vy < 0:
            self.vy += 1.2  # releasing A cuts the jump short -> variable height

        self.x += vx
        self.y += self.vy
        self.vy += 0.55

        if self.y >= GROUND_TOP - MARIO_H:
            if self._over_pit(self.x):
                self.dead = True
            else:
                self.y = float(GROUND_TOP - MARIO_H)
                self.vy = 0.0
                self.on_ground = True
        else:
            self.on_ground = False

        self.x = max(0.0, self.x)
        if self._resolve_obstacles():
            self.dead = True
        if self.dead:
            self.done = True
        if self.x >= self.LEVEL_LENGTH:
            self.win = True
            self.done = True

        self.t += 1
        return self.render(), self.done

    def _blit(self, frame, cam, wx, wy, w, h, color) -> None:
        x0 = int(wx - cam)
        y0 = max(0, int(wy))
        sx0 = max(0, x0)
        sx1 = min(FRAME_W, x0 + w)
        sy1 = min(FRAME_H, y0 + h)
        if sx1 <= sx0 or sy1 <= y0:
            return
        frame[y0:sy1, sx0:sx1] = color

    def render(self) -> np.ndarray:
        frame = np.empty((FRAME_H, FRAME_W, 3), dtype=np.uint8)
        frame[:, :] = (107, 140, 255)  # sky
        cam = max(0.0, self.x - 96.0)
        cam_i = int(cam)

        for gx in range(cam_i, cam_i + FRAME_W):
            if self._over_pit(gx):
                continue
            sx = gx - cam_i
            if 0 <= sx < FRAME_W:
                frame[GROUND_TOP:FRAME_H, sx] = (200, 120, 60)

        for ox, oy, ow, oh, kind in self.obstacles:
            color = (40, 160, 60) if kind == "pipe" else (140, 80, 40)
            self._blit(frame, cam, ox, oy, int(ow), int(oh), color)

        self._blit(frame, cam, self.x, self.y, MARIO_W, MARIO_H, (210, 40, 40))
        return frame

    def score(self) -> dict:
        return {"x": int(self.x), "win": self.win, "dead": self.dead, "frames": self.t}

    def close(self) -> None:
        pass


class MarioEnv:
    """Wraps ``gym-super-mario-bros``. Imported lazily so the mock path needs no ROM.

    A single NES action table is derived from the macro-action set: we collect
    every distinct button combination the macros can produce and hand exactly
    those to ``JoypadSpace``. ``step_buttons`` then maps a live button set to
    the matching table index.
    """

    frame_shape = (FRAME_W, FRAME_H)

    def __init__(self, actions, world: str = "1-1", render: bool = False,
                 rom_mode: str = "vanilla", scale: int = 3,
                 record: str | None = None, record_fps: float = 60.0) -> None:
        from gym_super_mario_bros import make
        from nes_py.wrappers import JoypadSpace

        masks = sorted({a.button_mask(f) for a in actions for f in range(0, 48)})
        # JoypadSpace wants lists of lowercase button names.
        movement = [sorted(BUTTON_MAP[b] for b in m) for m in masks]
        self._index = {mask: i for i, mask in enumerate(masks)}
        self._empty = self._index.get(frozenset(), 0)

        env_id = world if world.startswith("SuperMarioBros") else f"SuperMarioBros-{world}-v0"
        # nes-py predates gym's render_mode plumbing, so we do NOT pass it.
        # ``--render`` is handled by calling ``inner.render()`` during stepping.
        # ``rom_mode`` selects a bundled ROM variant (vanilla / pixel /
        # rectangle / downsample); the non-vanilla ones replace the sprites,
        # which is a cheap visual-perturbation control.
        self.inner = JoypadSpace(make(env_id, rom_mode=rom_mode), movement)
        self._render = render
        self._scale = scale
        self._record = record
        self._record_fps = record_fps
        self._world = world
        self._viewer = None
        self._recorder = None
        self._output_ready = False
        self._info: dict = {}
        self.reset()

    def _init_output(self) -> None:
        """Create the window/recorder lazily, on the first stepped frame."""
        if self._output_ready:
            return
        self._output_ready = True
        if self._render:
            from .viewer import Viewer

            self._viewer = Viewer(f"mda {self._world} (scale {self._scale})", scale=self._scale)
        if self._record:
            from .video import VideoRecorder

            self._recorder = VideoRecorder(self._record, fps=self._record_fps, scale=self._scale)

    def reset(self) -> np.ndarray:
        obs = self.inner.reset()
        if isinstance(obs, tuple):  # gymnasium-style (obs, info)
            obs = obs[0]
        return np.asarray(obs, dtype=np.uint8)

    def step_buttons(self, pressed: frozenset[str]) -> tuple[np.ndarray, bool]:
        idx = self._index.get(pressed, self._empty)
        obs, _reward, done, info = self.inner.step(idx)
        self._info = info or {}
        obs = np.asarray(obs, dtype=np.uint8)
        if self._render or self._record:
            self._init_output()
        if self._viewer is not None:
            self._viewer.show(obs)
            if self._viewer.closed:
                # User closed the window: end the episode instead of crashing
                # on the next blit to a destroyed GL context.
                done = True
        if self._recorder is not None:
            self._recorder.add(obs)
        return obs, bool(done)

    def score(self) -> dict:
        i = self._info
        return {
            "x": i.get("x_pos"),
            "lives": i.get("life"),
            "time": i.get("time"),
            "win": bool(i.get("flag_get")),
        }

    def close(self) -> None:
        if self._viewer is not None:
            self._viewer.close()
            self._viewer = None
        if self._recorder is not None:
            self._recorder.close()
            self._recorder = None
        try:
            self.inner.close()
        except Exception:
            pass
