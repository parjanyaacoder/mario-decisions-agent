"""Decision backends: the agent's only "brain".

``LiveBackend`` talks to the OpenAI Decisions API (``POST /v1/decisions``,
model ``gpt-6-luna``). ``MockBackend`` is an offline pixel heuristic so the
whole loop can run with no key and no network.

Both return the same ``Decision`` object, and both track input-token usage and
cost. Per the Decisions guide, ``/v1/decisions`` bills **input tokens only**
($0.10 / 1M); there are no output-token charges on this endpoint.
"""

from __future__ import annotations

import base64
import io
import os
import random
import time
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np

DECISIONS_URL = "https://api.openai.com/v1/decisions"
MODEL = "gpt-6-luna"
INPUT_USD_PER_MTOKEN = 0.10

#: Transient statuses worth retrying (public beta endpoints do return 503s).
RETRY_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

SYSTEM_PROMPT = (
    "You are playing Super Mario Bros (NES). Look at Mario's position and the "
    "obstacles ahead (pipes, pits, Goombas) and choose the single best next "
    "action from the choices. Advance to the right and survive. Remember that "
    "actions are held for several frames, so pick a move that stays safe for "
    "about half a second."
)


@dataclass
class Decision:
    move: str
    move_confidence: float | None
    move_probs: dict[str, float]
    hazard_prob: float | None
    hazard_confidence: float | None
    latency_s: float
    refused: bool = False
    cached: bool = False
    note: str = ""
    raw: dict = field(default_factory=dict)


@runtime_checkable
class DecisionBackend(Protocol):
    name: str

    def decide(self, frame: np.ndarray, t: int = 0) -> Decision: ...

    def close(self) -> None: ...


def encode_jpeg_data_url(
    frame: np.ndarray, quality: int = 80, max_side: int = 256
) -> tuple[str, bytes, tuple[int, int]]:
    """Return ``(data_url, jpeg_bytes, (width, height))``.

    Images on ``/v1/decisions`` must be inline base64 data URLs -- hosted URLs
    and ``file_id`` are not supported. Downscaling and JPEG compression keep the
    input token count (and therefore latency and cost) low.

    Note: this keeps the *whole* field of view. We never crop; cropping would
    hide obstacles from the model. ``max_side`` only shrinks the frame.
    """
    from PIL import Image

    img = Image.fromarray(np.asarray(frame, dtype=np.uint8))
    if max_side and max(img.size) > max_side:
        w, h = img.size
        scale = max_side / max(w, h)
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    raw = buf.getvalue()
    data_url = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
    return data_url, raw, img.size


class BaseBackend:
    name = "base"

    def __init__(self) -> None:
        self.calls = 0
        self.input_tokens = 0
        self.latency_sum = 0.0
        self.retries = 0
        self._estimated_tokens = False

    @property
    def cost_usd(self) -> float:
        return self.input_tokens / 1_000_000 * INPUT_USD_PER_MTOKEN

    def stats(self) -> dict:
        return {
            "backend": self.name,
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "input_tokens_estimated": self._estimated_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "retries": self.retries,
            "avg_latency_s": round(self.latency_sum / self.calls, 3) if self.calls else 0.0,
        }

    def close(self) -> None:
        pass


class MockBackend(BaseBackend):
    """Offline heuristic brain. No key, no network, no cost.

    It does a deliberately crude job: count non-sky pixels in the lower-right
    region of the frame and jump if that region looks busy. Good enough to
    exercise the loop, macro-actions and pipelining; not a real player.
    """

    name = "mock"

    def __init__(self, actions, latency_s: float = 0.35, jitter_s: float = 0.25, seed: int = 0,
                 hazard_threshold: float = 0.06, simulate_latency: bool = False) -> None:
        super().__init__()
        self.actions = list(actions)
        self.latency_s = latency_s
        self.jitter_s = jitter_s
        self.rng = random.Random(seed)
        self.hazard_threshold = hazard_threshold
        self.simulate_latency = simulate_latency

    @staticmethod
    def _hazard_score(frame: np.ndarray) -> float:
        h, w, _ = frame.shape
        region = frame[h // 2:, w // 2:, :]
        r = region[:, :, 0].astype(np.int16)
        b = region[:, :, 2].astype(np.int16)
        sky = (b > 200) & (r < 150)
        return float((~sky).mean())

    def decide(self, frame: np.ndarray, t: int = 0) -> Decision:
        self.calls += 1
        lat = max(0.0, self.rng.gauss(self.latency_s, self.jitter_s))
        self.latency_sum += lat

        hazard = self._hazard_score(frame)
        if self.simulate_latency:
            # Not a real request; this just lets us rehearse the latency mismatch
            # offline. Use it to tune --frames-per-decision without spending money.
            time.sleep(max(0.0, lat))
        if hazard > 0.15:
            move = "HIGH_JUMP_RIGHT"  # big obstacle (pipe) straight ahead
        elif hazard > self.hazard_threshold:
            move = "SHORT_HOP_RIGHT" if self.rng.random() < 0.6 else "HIGH_JUMP_RIGHT"
        else:
            r = self.rng.random()
            move = "RUN_RIGHT" if r < 0.75 else ("WAIT_OR_DUCK" if r < 0.9 else "HIGH_JUMP_RIGHT")

        probs = {a.key: 0.02 for a in self.actions}
        probs[move] = probs.get(move, 0.0) + 0.6
        probs["RUN_RIGHT"] = probs.get("RUN_RIGHT", 0.0) + 0.1
        total = sum(probs.values())
        probs = {k: round(v / total, 3) for k, v in probs.items()}

        return Decision(
            move=move,
            move_confidence=probs.get(move, 0.0),
            move_probs=probs,
            hazard_prob=round(hazard, 3),
            hazard_confidence=round(min(1.0, abs(hazard - self.hazard_threshold) * 4), 3),
            latency_s=round(lat, 3),
            note="mock",
        )


class LiveBackend(BaseBackend):
    """Calls the OpenAI Decisions API. Requires ``OPENAI_API_KEY``."""

    name = "live"

    def __init__(self, actions, api_key: str | None = None, model: str = MODEL,
                 url: str = DECISIONS_URL, timeout: float = 30.0,
                 jpeg_quality: int = 80, max_side: int = 256, session=None,
                 fallback: str = "RUN_RIGHT", save_frames_dir: str | None = None,
                 max_retries: int = 4, retry_backoff: float = 0.5) -> None:
        super().__init__()
        self.actions = list(actions)
        self.model = model
        self.url = url
        self.timeout = timeout
        self.jpeg_quality = jpeg_quality
        self.max_side = max_side
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff = max(0.0, float(retry_backoff))
        self.retries = 0
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set (see .env.example).")
        import requests

        self.session = session or requests.Session()
        self.fallback = fallback
        self._keys = {a.key for a in self.actions}

        # When set, every JPEG that is actually sent is written here. Use it to
        # confirm exactly what the model sees (full frame, just compressed).
        self.save_frames_dir = save_frames_dir
        self._frame_no = 0
        if save_frames_dir:
            os.makedirs(save_frames_dir, exist_ok=True)

    def _payload(self, data_url: str) -> dict:
        choices = [{"value": a.key, "description": a.description} for a in self.actions]
        return {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": SYSTEM_PROMPT},
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
            "questions": [
                {
                    "type": "choice",
                    "name": "next_move",
                    "instructions": "Choose Mario's single next action.",
                    "choices": choices,
                },
                {
                    "type": "predicate",
                    "name": "hazard_imminent",
                    "instructions": (
                        "Is an enemy or pit within about 3 tiles ahead of Mario?"
                    ),
                },
            ],
        }

    def decide(self, frame: np.ndarray, t: int = 0) -> Decision:
        self.calls += 1
        data_url, raw, size = encode_jpeg_data_url(frame, self.jpeg_quality, self.max_side)
        nbytes = len(raw)
        if self.save_frames_dir:
            path = os.path.join(self.save_frames_dir, f"frame_{self._frame_no:05d}.jpg")
            with open(path, "wb") as fh:
                fh.write(raw)
            self._frame_no += 1

        import requests

        payload = self._payload(data_url)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        t0 = time.perf_counter()
        data = None
        last_exc: Exception | None = None
        attempt = 0
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.post(
                    self.url, headers=headers, json=payload, timeout=self.timeout
                )
                if resp.status_code in RETRY_STATUS and attempt < self.max_retries:
                    last_exc = RuntimeError(f"HTTP {resp.status_code} (retrying)")
                else:
                    resp.raise_for_status()
                    data = resp.json()
                    break
            except requests.exceptions.HTTPError as exc:
                status = getattr(exc.response, "status_code", None)
                if status in RETRY_STATUS and attempt < self.max_retries:
                    last_exc = exc
                else:
                    raise
            except requests.exceptions.RequestException as exc:
                if attempt < self.max_retries:
                    last_exc = exc
                else:
                    raise
            if attempt < self.max_retries:
                time.sleep(self.retry_backoff * (2 ** attempt))

        latency = time.perf_counter() - t0
        self.latency_sum += latency
        self.retries += attempt
        if data is None:
            raise last_exc or RuntimeError("decisions request failed")

        self._account_tokens(data, nbytes)

        answers = {a.get("name"): a for a in data.get("answers", []) if isinstance(a, dict)}
        move_ans = answers.get("next_move", {})
        refused = move_ans.get("type") == "refusal" or not move_ans.get("choice")
        move = move_ans.get("choice") if move_ans.get("type") == "choice" else None
        if move not in self._keys:
            move = self.fallback
        probs = {
            p.get("value"): p.get("probability")
            for p in move_ans.get("probabilities", [])
            if isinstance(p, dict)
        }

        hazard_ans = answers.get("hazard_imminent", {})
        hazard = hazard_ans.get("probability") if hazard_ans.get("type") == "predicate" else None

        return Decision(
            move=move,
            move_confidence=move_ans.get("confidence"),
            move_probs=probs,
            hazard_prob=hazard,
            hazard_confidence=hazard_ans.get("confidence"),
            latency_s=round(latency, 3),
            refused=refused,
            note=f"img={size[0]}x{size[1]} {nbytes // 1024}KB",
            raw=data,
        )

    def _account_tokens(self, data: dict, nbytes: int) -> None:
        usage = data.get("usage") or {}
        for key in ("input_tokens", "prompt_tokens"):
            value = usage.get(key)
            if isinstance(value, int):
                self.input_tokens += value
                return
        # Fallback estimate if the API omits usage. Coarse upper bound.
        self._estimated_tokens = True
        self.input_tokens += max(1, round(nbytes * 1.333 / 4))


def blank_transform(frame: np.ndarray) -> np.ndarray:
    """The blanked-frame control: same shape, no information."""
    return np.zeros_like(frame)


class FrameTransformBackend(BaseBackend):
    """Wraps a backend, transforming the frame first (used for the blank control)."""

    def __init__(self, inner: BaseBackend, transform, name: str | None = None) -> None:
        super().__init__()
        self.inner = inner
        self.transform = transform
        self.name = name or f"{inner.name}+transform"

    def decide(self, frame: np.ndarray, t: int = 0) -> Decision:
        decision = self.inner.decide(self.transform(frame), t)
        self.calls = self.inner.calls
        self.input_tokens = self.inner.input_tokens
        self.latency_sum = self.inner.latency_sum
        self._estimated_tokens = self.inner._estimated_tokens
        return decision

    def stats(self) -> dict:
        stats = self.inner.stats()
        stats["backend"] = self.name
        return stats

    def close(self) -> None:
        self.inner.close()
