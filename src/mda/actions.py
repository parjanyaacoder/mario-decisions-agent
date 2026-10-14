"""The reduced macro-action space.

A NES controller has 8 buttons, which explodes into hundreds of combinations.
We expose a small, semantically meaningful set to the model instead. Each
action is a *macro*: it is held for several emulator frames, which is how we
cope with API latency (see ``loop.py``).

A button can either be *held* for the whole macro, or *tapped* for the first
``n`` frames. The tap is what distinguishes a short hop (release A early, low
arc) from a full jump (hold A, high arc).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MacroAction:
    """One discrete move the model can choose."""

    key: str
    """Value returned by the Decisions API and used to look the action back up."""

    description: str
    """Shown to the model as the option description. Be concrete about buttons."""

    held: tuple[str, ...] = ()
    """NES buttons held for the entire macro."""

    taps: tuple[tuple[str, int], ...] = ()
    """``(button, n_frames)`` pairs pressed for the first ``n`` frames only."""

    def button_mask(self, frame_in_macro: int) -> frozenset[str]:
        """The set of buttons pressed on frame ``frame_in_macro`` of this macro."""
        pressed = set(self.held)
        for button, n_frames in self.taps:
            if frame_in_macro < n_frames:
                pressed.add(button)
        return frozenset(pressed)


#: The default action set. Keep labels stable -- they are part of the prompt.
DEFAULT_ACTIONS: tuple[MacroAction, ...] = (
    MacroAction(
        key="RUN_RIGHT",
        description=(
            "Hold Right + B (run). Use on flat, safe ground to advance quickly."
        ),
        held=("RIGHT", "B"),
    ),
    MacroAction(
        key="HIGH_JUMP_RIGHT",
        description=(
            "Hold Right + A + B the whole time for a long, high jump. Use to "
            "clear pipes and wide gaps."
        ),
        held=("RIGHT", "A", "B"),
    ),
    MacroAction(
        key="SHORT_HOP_RIGHT",
        description=(
            "Hold Right + B and tap A briefly for a short hop. Use to stomp a "
            "Goomba or land on a small ledge."
        ),
        held=("RIGHT", "B"),
        taps=(("A", 8),),
    ),
    MacroAction(
        key="WAIT_OR_DUCK",
        description=(
            "Stand still (optionally duck) to wait for an enemy to pass or to "
            "time a jump. Does not move right."
        ),
        held=(),
        taps=(("DOWN", 30),),
    ),
    MacroAction(
        key="BACKTRACK_LEFT",
        description="Hold Left + B to back away from a hazard.",
        held=("LEFT", "B"),
    ),
)

ACTION_BY_KEY: dict[str, MacroAction] = {a.key: a for a in DEFAULT_ACTIONS}
