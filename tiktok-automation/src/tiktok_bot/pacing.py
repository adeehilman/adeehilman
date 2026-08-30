"""Rate limiting.

The point is not stealth — it is not hammering an endpoint (or a person's
inbox) faster than a human plausibly would, and stopping at a fixed budget.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class Pacer:
    min_seconds: int
    max_seconds: int
    budget: int
    _spent: int = 0
    _sleep = staticmethod(time.sleep)

    @property
    def spent(self) -> int:
        return self._spent

    @property
    def remaining(self) -> int:
        return max(0, self.budget - self._spent)

    def consume(self) -> None:
        """Record one unit of work against the run budget."""
        self._spent += 1

    def exhausted(self) -> bool:
        return self._spent >= self.budget

    def wait(self) -> float:
        """Sleep a randomised interval; returns the number of seconds slept."""
        delay = random.uniform(self.min_seconds, self.max_seconds)
        log.info("waiting %.1fs before the next action", delay)
        self._sleep(delay)
        return delay

    def jitter(self, base: float = 1.0, spread: float = 1.5) -> float:
        """Short pause between individual UI steps inside one conversation."""
        delay = random.uniform(base, base + spread)
        self._sleep(delay)
        return delay
