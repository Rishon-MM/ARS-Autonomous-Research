"""
recovery/retry.py — Retry policy definitions.

Used by GraphNode to configure retry behavior per worker.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetryPolicy:
    """
    Configurable retry behavior.

    Supports exponential, linear, and fixed backoff strategies.
    """

    max_retries: int = 3
    backoff: str = "exponential"  # exponential | linear | fixed
    base_delay: float = 1.0
    max_delay: float = 60.0
    retryable_exceptions: tuple = (
        TimeoutError,
        ConnectionError,
        OSError,
    )

    def delay_for_attempt(self, attempt: int) -> float:
        if self.backoff == "exponential":
            delay = self.base_delay * (2 ** attempt)
        elif self.backoff == "linear":
            delay = self.base_delay * (attempt + 1)
        else:
            delay = self.base_delay
        return min(delay, self.max_delay)

    def is_retryable(self, exc: Exception) -> bool:
        return isinstance(exc, self.retryable_exceptions)
