"""Mario Decisions Agent.

A screenshot-only Super Mario Bros agent whose only "brain" is the OpenAI
Decisions API (``POST /v1/decisions``, model ``gpt-6-luna``). The agent never
reads emulator RAM; it looks at an RGB frame and picks one macro-action.

Design goals
------------
* **Pluggable environments** -- the real NES emulator (``MarioEnv``) and a
  dependency-free toy platformer (``MockEnv``) share one tiny interface.
* **Pluggable backends** -- the live Decisions API (``LiveBackend``) and an
  offline heuristic (``MockBackend``) share one ``decide(frame) -> Decision``
  interface, so the whole loop is testable at zero cost.
* **Speed mismatch is explicit** -- a 60 fps game vs. a ~hundreds-of-ms API is
  handled with macro-actions and an optional pipelined (overlapped) loop.
"""

__version__ = "0.1.0"
