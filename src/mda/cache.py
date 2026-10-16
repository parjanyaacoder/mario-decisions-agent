"""Layer E: reuse the last decision when the screen has not meaningfully changed.

If nothing on screen moved, asking the API again would (almost certainly) return
the same answer, so we skip the call and replay the previous action. That saves
both latency and money.

Two deliberate safety choices:

* We compare a **perceptual hash** (a downscaled average hash), not exact bytes.
  An exact match is too strict to ever fire in a moving game; "nearly identical"
  with a small Hamming threshold is what actually catches the stationary case.
* We cap consecutive reuses (``max_reuse``). If the screen is frozen because the
  agent is stuck against a wall, we still re-ask periodically instead of looping
  one action forever.

This backend is NOT safe to combine with the blanked-frame control: blank frames
are identical by construction, so the cache would hit every time and the control
would stop making real calls. The CLI refuses that combination.
"""

from __future__ import annotations

import numpy as np

from .backends import BaseBackend, Decision


def fingerprint(frame: np.ndarray, size: int = 16) -> int:
    """Return a ``size*size``-bit average-hash of the frame as a Python int."""
    from PIL import Image

    img = Image.fromarray(np.asarray(frame, dtype=np.uint8)).convert("L")
    img = img.resize((size, size), Image.BILINEAR)
    arr = np.asarray(img, dtype=np.float32)
    bits = (arr > arr.mean()).ravel()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


class CachingBackend(BaseBackend):
    """Wraps a backend; replays the last decision when the frame is unchanged."""

    def __init__(self, inner: BaseBackend, threshold: int = 4, max_reuse: int = 5,
                 name: str | None = None) -> None:
        super().__init__()
        self.inner = inner
        self.threshold = threshold
        self.max_reuse = max_reuse
        self.name = name or f"{inner.name}+cache"
        self._fp: int | None = None
        self._decision: Decision | None = None
        self._reuse = 0
        self.hits = 0
        self.misses = 0

    @property
    def cost_usd(self) -> float:
        return self.inner.cost_usd

    def decide(self, frame: np.ndarray, t: int = 0) -> Decision:
        fp = fingerprint(frame)
        unchanged = (
            self._fp is not None
            and self._reuse < self.max_reuse
            and hamming(fp, self._fp) <= self.threshold
        )
        if unchanged and self._decision is not None:
            self.hits += 1
            self._reuse += 1
            prev = self._decision
            # A cache hit costs no tokens and no network time.
            return Decision(
                move=prev.move,
                move_confidence=prev.move_confidence,
                move_probs=prev.move_probs,
                hazard_prob=prev.hazard_prob,
                hazard_confidence=prev.hazard_confidence,
                latency_s=0.0,
                refused=prev.refused,
                note="cache",
                raw=prev.raw,
                cached=True,
                mario_box=prev.mario_box,
                model=prev.model,
            )

        self.misses += 1
        decision = self.inner.decide(frame, t)
        self._fp = fp
        self._decision = decision
        self._reuse = 0
        return decision

    def stats(self) -> dict:
        stats = self.inner.stats()
        stats["backend"] = self.name
        total = self.hits + self.misses
        stats["cache_hits"] = self.hits
        stats["cache_misses"] = self.misses
        stats["cache_hit_rate"] = round(self.hits / total, 3) if total else 0.0
        return stats

    def close(self) -> None:
        self.inner.close()
