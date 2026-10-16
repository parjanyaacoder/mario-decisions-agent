"""Decision backends: the agent's only "brain".

Three interchangeable brains, all returning the same ``Decision``:

* ``LiveBackend``   -- OpenAI Decisions API (``POST /v1/decisions``,
                       model ``gpt-6-luna``).
* ``JevBackend``    -- TypeSafe System One API (``POST /v1/systemone``,
                       model ``jev-preview``). TypeSafe calls its model *Jev*.
* ``MockBackend``   -- an offline pixel heuristic, so the loop runs with no
                       key and no network.

All three track input-token usage and cost. Both hosted endpoints bill **input
tokens only**: the Decisions API at $0.10 / 1M, TypeSafe at $0.042 / 1M.

The two hosted APIs look alike but are not: the request/response shapes differ
(see ``JevBackend``), and TypeSafe **rejects images smaller than 280 px on a
side**, which matters here because a NES frame is only 256x240.
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

# --- TypeSafe ("Jev") System One API -------------------------------------
# Images and Box questions are behind a beta flag; 1.14 is the first release
# that accepts images, and `jev-latest` still points at the text-only 1.13, so
# the image path must ask for the preview alias explicitly.
TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
TYPESAFE_MODEL = "jev-preview"
TYPESAFE_INPUT_USD_PER_MTOKEN = 0.042
TYPESAFE_DANGER_HEADER = "TypeSafe-Danger-Zone-Images"

#: Hard limits from https://docs.typesafe.ai/images#limits. An image outside
#: them is *rejected*, never resized to fit, so we pad/scale into the band.
TYPESAFE_MIN_SIDE = 280          # every side must be >= 280 px
TYPESAFE_MAX_SIDE = 1568         # ... and <= 1568 px
TYPESAFE_MIN_PIXELS = 78_400     # 280 x 280
TYPESAFE_MAX_PIXELS = 2_458_624  # 1568 x 1568

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
    #: Normalised Mario bounding box, only filled by backends that can locate
    #: objects in the frame (TypeSafe's ``box`` question type).
    mario_box: dict | None = None
    #: The model that actually answered, as reported by the API.
    model: str = ""


@runtime_checkable
class DecisionBackend(Protocol):
    name: str

    def decide(self, frame: np.ndarray, t: int = 0) -> Decision: ...

    def close(self) -> None: ...


def _resize_frame_max(frame: np.ndarray, max_side: int = 0):
    """Shrink a frame so its longest side is at most ``max_side``.

    Only ever shrinks. This keeps the *whole* field of view -- we never crop,
    because cropping would hide the obstacle the model needs to see.
    """
    from PIL import Image

    img = Image.fromarray(np.asarray(frame, dtype=np.uint8))
    w, h = img.size
    if max_side and max(w, h) > max_side:
        scale = max_side / max(w, h)
        img = img.resize(
            (max(1, round(w * scale)), max(1, round(h * scale))), Image.BILINEAR
        )
    return img


def _typesafe_size(w: int, h: int, max_side: int) -> tuple[int, int]:
    """Pick a legal TypeSafe image size, landing the longest side on ``max_side``.

    Unlike the Decisions API, TypeSafe *rejects* an out-of-band image instead of
    resizing it, so we must land inside: every side in ``[280, 1568]`` px and
    total pixels in ``[78_400, 2_458_624]``. A NES frame (256x240) is under the
    minimum, so the default path scales *up*; a larger ``max_side`` buys detail
    at the cost of latency and tokens.
    """
    target = max(TYPESAFE_MIN_SIDE, min(int(max_side), TYPESAFE_MAX_SIDE))
    scale = target / max(w, h)
    if min(w, h) * scale < TYPESAFE_MIN_SIDE:  # never let a side fall short
        scale = TYPESAFE_MIN_SIDE / min(w, h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))

    if max(nw, nh) > TYPESAFE_MAX_SIDE:
        k = TYPESAFE_MAX_SIDE / max(nw, nh)
        nw, nh = max(1, round(nw * k)), max(1, round(nh * k))
    if nw * nh > TYPESAFE_MAX_PIXELS:
        k = (TYPESAFE_MAX_PIXELS / (nw * nh)) ** 0.5
        nw, nh = max(1, round(nw * k)), max(1, round(nh * k))
    if nw * nh < TYPESAFE_MIN_PIXELS:
        k = (TYPESAFE_MIN_PIXELS / (nw * nh)) ** 0.5
        nw, nh = max(1, round(nw * k)), max(1, round(nh * k))
    if min(nw, nh) < TYPESAFE_MIN_SIDE:
        k = TYPESAFE_MIN_SIDE / min(nw, nh)
        nw, nh = max(1, round(nw * k)), max(1, round(nh * k))
    return nw, nh


def _jpeg_bytes(img, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def encode_jpeg_data_url(
    frame: np.ndarray, quality: int = 80, max_side: int = 256
) -> tuple[str, bytes, tuple[int, int]]:
    """Return ``(data_url, jpeg_bytes, (width, height))`` for the Decisions API.

    Images on ``/v1/decisions`` must be inline base64 data URLs -- hosted URLs
    and ``file_id`` are not supported. Downscaling and JPEG compression keep the
    input token count (and therefore latency and cost) low.

    Note: this keeps the *whole* field of view. We never crop; cropping would
    hide obstacles from the model. ``max_side`` only shrinks the frame.
    """
    img = _resize_frame_max(frame, max_side=max_side)
    raw = _jpeg_bytes(img, quality)
    data_url = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
    return data_url, raw, img.size


def encode_jpeg_base64(
    frame: np.ndarray, quality: int = 80, max_side: int = 320
) -> tuple[str, bytes, tuple[int, int]]:
    """Return ``(base64, jpeg_bytes, (width, height))`` for a TypeSafe asset.

    TypeSafe wants the bare base64 alphabet (no ``data:`` prefix) in
    ``assets[ref].data_base64``. See ``_typesafe_size`` for the sizing rules.
    """
    from PIL import Image

    src = np.asarray(frame, dtype=np.uint8)
    nw, nh = _typesafe_size(src.shape[1], src.shape[0], max_side)
    img = Image.fromarray(src)
    if (nw, nh) != img.size:
        img = img.resize((nw, nh), Image.BILINEAR)
    raw = _jpeg_bytes(img, quality)
    return base64.b64encode(raw).decode("ascii"), raw, img.size


def _post_with_retries(session, url, headers, payload, *, timeout, max_retries,
                       retry_backoff, retry_status=RETRY_STATUS):
    """POST with exponential backoff. Returns ``(data, latency_s, attempts)``.

    Transient statuses and transport errors are retried; anything else raises.
    """
    import requests

    t0 = time.perf_counter()
    data = None
    last_exc: Exception | None = None
    attempt = 0
    for attempt in range(max_retries + 1):
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code in retry_status and attempt < max_retries:
                last_exc = RuntimeError(f"HTTP {resp.status_code} (retrying)")
            else:
                resp.raise_for_status()
                data = resp.json()
                break
        except requests.exceptions.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status in retry_status and attempt < max_retries:
                last_exc = exc
            else:
                raise
        except requests.exceptions.RequestException as exc:
            if attempt < max_retries:
                last_exc = exc
            else:
                raise
        if attempt < max_retries:
            time.sleep(retry_backoff * (2 ** attempt))

    latency = time.perf_counter() - t0
    if data is None:
        raise last_exc or RuntimeError("request failed")
    return data, latency, attempt


class BaseBackend:
    name = "base"
    #: Input-only price, USD per million tokens. Overridden per API.
    usd_per_mtoken = INPUT_USD_PER_MTOKEN

    def __init__(self) -> None:
        self.calls = 0
        self.input_tokens = 0
        self.latency_sum = 0.0
        self.retries = 0
        self._estimated_tokens = False

    @property
    def cost_usd(self) -> float:
        return self.input_tokens / 1_000_000 * self.usd_per_mtoken

    def _account_tokens(self, data: dict, nbytes: int) -> None:
        """Add the API-reported input tokens, or estimate if usage is missing."""
        usage = data.get("usage") or {}
        for key in ("input_tokens", "prompt_tokens"):
            value = usage.get(key)
            if isinstance(value, int):
                self.input_tokens += value
                return
        # Fallback estimate if the API omits usage. Coarse upper bound.
        self._estimated_tokens = True
        self.input_tokens += max(1, round(nbytes * 1.333 / 4))

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

        payload = self._payload(data_url)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data, latency, attempt = _post_with_retries(
            self.session, self.url, headers, payload,
            timeout=self.timeout, max_retries=self.max_retries,
            retry_backoff=self.retry_backoff,
        )
        self.latency_sum += latency
        self.retries += attempt

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
            model=data.get("model") or self.model,
        )


class JevBackend(BaseBackend):
    """Calls the TypeSafe System One API ("Jev"). Requires ``TYPESAFE_API_KEY``.

    TypeSafe's shape differs from the Decisions API in ways that matter here:

    * the image is a **reference** into a top-level ``assets`` map, not an
      ``input_image`` content part;
    * questions are a **map** keyed by name, and a Choice's options live in a
      ``criteria`` map rather than a list;
    * yes/no is a ``noul``, which answers with a bare probability and has no
      separate confidence;
    * answers come back as a **map**, not a list.

    Images sit behind a beta header and need the ``jev-preview`` alias (1.14):
    ``jev-latest`` still points at the text-only 1.13. TypeSafe also *rejects*
    images smaller than 280 px on a side instead of resizing them, so this path
    scales the NES frame up a little where the Decisions path scales it down.
    """

    name = "jev"
    usd_per_mtoken = TYPESAFE_INPUT_USD_PER_MTOKEN

    #: Reference used to plant the frame in ``state``. Deliberately unlikely to
    #: appear as a substring of our own prompt text (references are matched as
    #: plain text, so a short ref like ``frame`` could match mid-word).
    FRAME_REF = "nes_frame"

    def __init__(self, actions, api_key: str | None = None, model: str = TYPESAFE_MODEL,
                 url: str = TYPESAFE_URL, timeout: float = 30.0,
                 jpeg_quality: int = 80, max_side: int = 320, session=None,
                 fallback: str = "RUN_RIGHT", save_frames_dir: str | None = None,
                 max_retries: int = 4, retry_backoff: float = 0.5,
                 locate_mario: bool = False, instructions: str = SYSTEM_PROMPT) -> None:
        super().__init__()
        self.actions = list(actions)
        self.model = model
        self.url = url
        self.timeout = timeout
        self.jpeg_quality = jpeg_quality
        self.max_side = max_side
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff = max(0.0, float(retry_backoff))
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
        if not self.api_key:
            raise RuntimeError("TYPESAFE_API_KEY is not set (see .env.example).")
        import requests

        self.session = session or requests.Session()
        self.fallback = fallback
        self._keys = {a.key for a in self.actions}
        self.locate_mario = locate_mario
        self.instructions = instructions
        self.save_frames_dir = save_frames_dir
        self._frame_no = 0
        if save_frames_dir:
            os.makedirs(save_frames_dir, exist_ok=True)

    def _payload(self, base64_data: str) -> dict:
        ref = self.FRAME_REF
        questions: dict = {
            "next_move": {
                "type": "choice",
                "instructions": (
                    "Look at the game screenshot in `frame` and choose Mario's "
                    "single next action."
                ),
                "criteria": {a.key: a.description for a in self.actions},
            },
            "hazard_imminent": {
                "type": "noul",
                "instructions": (
                    "In `frame`, is an enemy or pit within about 3 tiles ahead "
                    "of Mario?"
                ),
            },
        }
        if self.locate_mario:
            # TypeSafe-only: a Box returns where Mario is, as four fractions of
            # the image. We do not feed it back into the move choice -- it is
            # recorded so runs stay comparable with the Decisions path.
            questions["mario_box"] = {
                "type": "box",
                "instructions": "the player character (Mario) in `frame`",
            }
        return {
            "model": self.model,
            "state": {
                "game": "Super Mario Bros (NES), World 1-1",
                "task": self.instructions,
                "frame": ref,
            },
            "assets": {
                ref: {"type": "image", "format": "jpg", "data_base64": base64_data}
            },
            "questions": questions,
        }

    def decide(self, frame: np.ndarray, t: int = 0) -> Decision:
        self.calls += 1
        b64, raw, size = encode_jpeg_base64(frame, self.jpeg_quality, self.max_side)
        nbytes = len(raw)
        if self.save_frames_dir:
            path = os.path.join(self.save_frames_dir, f"frame_{self._frame_no:05d}.jpg")
            with open(path, "wb") as fh:
                fh.write(raw)
            self._frame_no += 1

        payload = self._payload(b64)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # Images and Box questions are off by default on TypeSafe.
            TYPESAFE_DANGER_HEADER: "true",
        }
        data, latency, attempt = _post_with_retries(
            self.session, self.url, headers, payload,
            timeout=self.timeout, max_retries=self.max_retries,
            retry_backoff=self.retry_backoff,
        )
        self.latency_sum += latency
        self.retries += attempt
        self._account_tokens(data, nbytes)

        answers = data.get("answers")
        if not isinstance(answers, dict):
            answers = {}

        move_ans = answers.get("next_move")
        move_ans = move_ans if isinstance(move_ans, dict) else {}
        choice = move_ans.get("choice")
        if move_ans.get("type") == "refusal" or not choice:
            refused = True
        else:
            refused = False
        move = choice if choice in self._keys else self.fallback

        probs = move_ans.get("probabilities")
        if isinstance(probs, list):  # tolerate the Decisions API's list shape
            probs = {
                p.get("value"): p.get("probability")
                for p in probs
                if isinstance(p, dict)
            }
        elif not isinstance(probs, dict):
            probs = {}

        hazard_ans = answers.get("hazard_imminent")
        hazard_ans = hazard_ans if isinstance(hazard_ans, dict) else {}
        hazard = hazard_ans.get("noul")
        if not isinstance(hazard, (int, float)):
            hazard = None

        mario_box = None
        if self.locate_mario:
            box_ans = answers.get("mario_box")
            if isinstance(box_ans, dict) and isinstance(box_ans.get("box"), dict):
                mario_box = box_ans["box"]

        return Decision(
            move=move,
            move_confidence=move_ans.get("confidence"),
            move_probs=probs,
            hazard_prob=hazard,
            # A noul is a yes/no probability; it has no separate confidence.
            hazard_confidence=None,
            latency_s=round(latency, 3),
            refused=refused,
            note=f"{size[0]}x{size[1]} {nbytes // 1024}KB",
            raw=data,
            mario_box=mario_box,
            model=data.get("model") or self.model,
        )


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
