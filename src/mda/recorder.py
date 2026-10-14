"""Append-only JSONL run log: one line per decision, plus a final summary."""

from __future__ import annotations

import json


class Recorder:
    def __init__(self, path: str | None) -> None:
        self.path = path
        self._fh = open(path, "w", encoding="utf-8") if path else None

    def write(self, record: dict) -> None:
        if self._fh is not None:
            self._fh.write(json.dumps(record, default=str) + "\n")
            self._fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
