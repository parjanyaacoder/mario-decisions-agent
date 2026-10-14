"""Offline pipeline tests: no key, no ROM, no network."""

from __future__ import annotations

import os
import pathlib
import tempfile

from mda.actions import DEFAULT_ACTIONS, ACTION_BY_KEY
from mda.backends import LiveBackend, MockBackend, blank_transform
from mda.cache import CachingBackend, fingerprint, hamming
from mda.env import MockEnv
from mda.loop import run_episode


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    """Captures the outgoing request and returns a canned answer."""

    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.sent: dict | None = None
        self.calls = 0

    def post(self, url, headers=None, json=None, timeout=None):  # noqa: A002
        self.sent = json
        self.calls += 1
        return _FakeResponse(self.payload, self.status_code)


def test_action_masks():
    run = ACTION_BY_KEY["RUN_RIGHT"]
    assert run.button_mask(0) == frozenset({"RIGHT", "B"})
    assert run.button_mask(999) == frozenset({"RIGHT", "B"})

    hop = ACTION_BY_KEY["SHORT_HOP_RIGHT"]
    assert "A" in hop.button_mask(0)
    assert "A" not in hop.button_mask(10)

    jump = ACTION_BY_KEY["HIGH_JUMP_RIGHT"]
    assert jump.button_mask(50) == frozenset({"RIGHT", "A", "B"})


def test_mock_env_advances_and_is_deterministic():
    env = MockEnv()
    frame = env.reset()
    assert frame.shape == (240, 256, 3)

    a = MockEnv()
    b = MockEnv()
    ra = a.reset()
    rb = b.reset()
    for _ in range(30):
        ra, da = a.step_buttons(frozenset({"RIGHT", "B"}))
        rb, db = b.step_buttons(frozenset({"RIGHT", "B"}))
        assert da == db
    assert (ra == rb).all()


def test_blank_transform_erases_information():
    frame = MockEnv().reset()
    blank = blank_transform(frame)
    assert blank.shape == frame.shape
    assert blank.max() == 0


def test_blocking_episode_runs_to_completion():
    env = MockEnv()
    backend = MockBackend(DEFAULT_ACTIONS, latency_s=0.0, jitter_s=0.0, seed=1)
    summary = run_episode(
        env, backend, DEFAULT_ACTIONS,
        frames_per_decision=4, mode="blocking",
        target_fps=None, max_decisions=200,
    )
    assert summary["decisions"] > 0
    assert summary["backend"] == "mock"
    assert summary["cost_usd"] == 0.0


def test_pipelined_loop_produces_decisions():
    env = MockEnv()
    backend = MockBackend(DEFAULT_ACTIONS, latency_s=0.05, jitter_s=0.0, seed=2)
    summary = run_episode(
        env, backend, DEFAULT_ACTIONS,
        frames_per_decision=4, mode="pipelined",
        target_fps=None, max_decisions=50,
    )
    assert summary["decisions"] >= 3
    assert summary["frames"] > 0


def test_pipelined_loop_asks_ahead_and_hides_latency():
    """Trick B: the next request is in flight *during* the macro.

    With a reply time well under the macro length, the answer should already
    be waiting when the macro ends, so the loop never stalls. (Before the fix
    it asked only after the macro finished, and stalled by ~latency*fps frames
    every single decision.)
    """
    env = _StaticEnv(MockEnv().reset())
    backend = MockBackend(DEFAULT_ACTIONS, latency_s=0.05, jitter_s=0.0, seed=7,
                          simulate_latency=True)
    summary = run_episode(
        env, backend, DEFAULT_ACTIONS,
        frames_per_decision=12, mode="pipelined",
        target_fps=60.0, max_decisions=3,
    )
    assert summary["decisions"] == 3
    # 12 frames @ 60fps = 0.2s of macro vs a 0.05s reply: nothing should stall.
    assert summary["stall_frames"] == 0


def test_live_backend_contract_and_frame_saving():
    """Exercise the live path offline: payload shape, parsing, and saved frames."""
    payload = {
        "answers": [
            {"type": "choice", "name": "next_move", "choice": "HIGH_JUMP_RIGHT",
             "confidence": 0.81,
             "probabilities": [{"value": "HIGH_JUMP_RIGHT", "probability": 0.81}]},
            {"type": "predicate", "name": "hazard_imminent", "probability": 0.71},
        ]
    }
    session = _FakeSession(payload)
    with tempfile.TemporaryDirectory() as tmp:
        backend = LiveBackend(
            DEFAULT_ACTIONS, api_key="test-key", session=session,
            save_frames_dir=tmp,
        )
        decision = backend.decide(MockEnv().reset())

        # --- response parsing ---
        assert decision.move == "HIGH_JUMP_RIGHT"
        assert decision.move_confidence == 0.81
        assert decision.hazard_prob == 0.71
        assert decision.refused is False

        # --- outgoing payload uses the real Decisions contract ---
        sent = session.sent
        assert sent["model"] == "gpt-6-luna"
        image_part = sent["input"][0]["content"][1]
        assert image_part["type"] == "input_image"
        assert image_part["image_url"].startswith("data:image/jpeg;base64,")
        choice_q = sent["questions"][0]
        assert choice_q["type"] == "choice"
        assert "choices" in choice_q and "options" not in choice_q
        assert choice_q["choices"][0]["value"] in ACTION_BY_KEY

        saw_image = sent["input"][0]["content"][1]["type"]
        assert saw_image == "input_image"

        # --- the exact JPEG that was sent is on disk ---
        saved = list(pathlib.Path(tmp).glob("*.jpg"))
        assert len(saved) == 1 and saved[0].stat().st_size > 0
        backend.close()


def test_live_backend_handles_refusal():
    session = _FakeSession({"answers": [{"type": "refusal", "name": "next_move"}]})
    backend = LiveBackend(DEFAULT_ACTIONS, api_key="test-key", session=session)
    decision = backend.decide(MockEnv().reset())
    assert decision.refused is True
    assert decision.move == "RUN_RIGHT"  # safe fallback
    assert decision.hazard_prob is None
    backend.close()


def test_fingerprint_is_stable_and_distinguishes_blank():
    frame = MockEnv().reset()
    fp = fingerprint(frame)
    assert fp == fingerprint(frame.copy())
    assert hamming(fp, fp) == 0
    # The blank control erases the screen, so it must NOT match the real frame.
    assert hamming(fp, fingerprint(blank_transform(frame))) > 0


def test_cache_reuses_unchanged_frame_and_misses_on_change():
    base = MockBackend(DEFAULT_ACTIONS, latency_s=0.0, jitter_s=0.0, seed=0)
    cache = CachingBackend(base, threshold=0, max_reuse=100)
    env = MockEnv()
    frame = env.reset()

    first = cache.decide(frame)
    second = cache.decide(frame.copy())
    assert first.cached is False
    assert second.cached is True
    assert second.move == first.move
    assert second.latency_s == 0.0
    assert base.calls == 1  # only one real API call
    assert cache.hits == 1

    # A visibly different frame forces a fresh call.
    changed = frame.copy()
    changed[:120] = 0
    third = cache.decide(changed)
    assert third.cached is False
    assert base.calls == 2


def test_cache_respects_max_reuse():
    base = MockBackend(DEFAULT_ACTIONS, latency_s=0.0, jitter_s=0.0, seed=0)
    cache = CachingBackend(base, threshold=0, max_reuse=1)
    frame = MockEnv().reset()
    cache.decide(frame)          # miss
    assert cache.decide(frame).cached is True   # hit 1
    assert cache.decide(frame).cached is False  # capped -> forced miss
    assert base.calls == 2


class _StaticEnv:
    """A toy env whose frame never changes, to force cache hits."""

    def __init__(self, frame) -> None:
        self._frame = frame
        self._steps = 0

    def reset(self):
        self._steps = 0
        return self._frame.copy()

    def step_buttons(self, mask):
        self._steps += 1
        return self._frame.copy(), self._steps > 40

    def score(self):
        return {"x": self._steps}

    def close(self):
        pass


def test_cache_integration_through_the_loop():
    frame = MockEnv().reset()
    base = MockBackend(DEFAULT_ACTIONS, latency_s=0.0, jitter_s=0.0, seed=3)
    backend = CachingBackend(base, threshold=0, max_reuse=100)
    summary = run_episode(
        _StaticEnv(frame), backend, DEFAULT_ACTIONS,
        frames_per_decision=4, mode="blocking", target_fps=None, max_decisions=5,
    )
    assert base.calls == 1            # everything after the first decision was cached
    assert summary["cache_hits"] >= 1
    assert summary["cache_hit_rate"] > 0
    assert summary["backend"] == "mock+cache"


def test_viewer_opens_at_requested_scale_without_a_display():
    from mda.viewer import Viewer

    viewer = Viewer(scale=3)
    assert (viewer.width, viewer.height) == (768, 720)  # 3x the 256x240 NES frame
    assert viewer.closed is False


def test_video_recorder_writes_mp4():
    from mda.video import VideoRecorder

    frame = MockEnv().reset()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "out.mp4")
        rec = VideoRecorder(path, fps=30, scale=2)
        for _ in range(6):
            rec.add(frame)
        rec.close()
        assert rec.frames == 6
        assert os.path.getsize(path) > 0


def test_video_recorder_writes_png_sequence_for_a_directory():
    from mda.video import VideoRecorder

    frame = MockEnv().reset()
    with tempfile.TemporaryDirectory() as tmp:
        rec = VideoRecorder(tmp, fps=30, scale=1)
        for _ in range(3):
            rec.add(frame)
        rec.close()
        assert sorted(os.listdir(tmp)) == [
            "frame_000000.png", "frame_000001.png", "frame_000002.png",
        ]


def test_blocking_mode_is_frame_paced():
    # Before the shared pace() helper, blocking mode ignored --fps and ran the
    # emulator flat-out. Prove it now throttles near the requested 30 fps.
    env = MockEnv()
    backend = MockBackend(DEFAULT_ACTIONS, latency_s=0.0, jitter_s=0.0, seed=1)
    summary = run_episode(
        env, backend, DEFAULT_ACTIONS,
        frames_per_decision=5, mode="blocking", target_fps=30.0, max_decisions=3,
    )
    assert summary["frames"] > 0
    assert summary["effective_fps"] <= 60  # unthrottled would be thousands


def test_live_backend_retries_transient_then_succeeds():
    payload = {"answers": [
        {"type": "choice", "name": "next_move", "choice": "RUN_RIGHT", "confidence": 0.9,
         "probabilities": [{"value": "RUN_RIGHT", "probability": 0.9}]},
        {"type": "predicate", "name": "hazard_imminent", "probability": 0.1},
    ]}
    calls = {"n": 0}

    class _SeqSession:
        def post(self, url, headers=None, json=None, timeout=None):  # noqa: A002
            calls["n"] += 1
            code = 503 if calls["n"] < 3 else 200  # two 503s, then success
            return _FakeResponse(payload, code)

    backend = LiveBackend(DEFAULT_ACTIONS, api_key="k", session=_SeqSession(),
                          max_retries=4, retry_backoff=0.0)
    decision = backend.decide(MockEnv().reset())
    assert decision.move == "RUN_RIGHT"
    assert calls["n"] == 3       # it did retry through the 503s
    assert backend.retries == 2
    backend.close()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all tests passed")
