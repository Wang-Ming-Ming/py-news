"""Small per-process request pacer for respectful source collection."""

from __future__ import annotations

import threading
import time


class RequestPacer:
    def __init__(self, minimum_interval_seconds: float = 1.0) -> None:
        self.minimum_interval_seconds = max(0.0, float(minimum_interval_seconds))
        self._last_request_at = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            remaining = self.minimum_interval_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
            self._last_request_at = time.monotonic()


__all__ = ["RequestPacer"]
