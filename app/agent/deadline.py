"""Monotonic budget arithmetic; cancellation belongs to the I/O supervisor."""
from __future__ import annotations

from collections.abc import Callable
import math
from time import monotonic


class Deadline:
    """An absolute deadline shared across multiple operations, without any I/O.

    Checking this helper alone cannot interrupt a blocking operation. Callers
    must supervise killable work using its remaining budget.
    """

    def __init__(self, seconds: float, clock: Callable[[], float] = monotonic):
        if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
                or not math.isfinite(seconds)):
            raise ValueError("Invalid deadline budget")
        self._clock = clock
        self.expires_at = clock() + max(0, seconds)

    def remaining(self) -> float:
        return max(0, self.expires_at - self._clock())

    @property
    def expired(self) -> bool:
        return self.remaining() <= 0
