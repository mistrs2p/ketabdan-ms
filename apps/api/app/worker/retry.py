"""The bounded retry policy for background notification delivery.

The policy (Task 5.7, docs/01 §6.5):

- attempt 1 runs immediately (that is the queue's behavior, not a delay);
- each subsequent retryable attempt waits ``base * 2^(n - 2)`` seconds —
  exponential backoff from the base delay;
- the wait never exceeds ``max_delay``;
- when the provider sent a rate-limit hint (``retry_after``), the wait is
  at least that hint (still capped by ``max_delay`` so everything stays
  bounded);
- after ``max_attempts`` total attempts the job fails permanently —
  there are **no infinite retries**.

Only *retryable* failures ever consult this policy: provider-unavailable
(and other unexpected) errors. Rejected notifications never retry.
"""

import dataclasses


@dataclasses.dataclass(frozen=True)
class RetryPolicy:
    """Bounded exponential backoff for retryable notification failures."""

    max_attempts: int
    base_delay_seconds: float
    max_delay_seconds: float

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if self.base_delay_seconds <= 0:
            raise ValueError("base_delay_seconds must be positive.")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError(
                "max_delay_seconds must be greater than or equal to "
                "base_delay_seconds."
            )

    def delay_for(self, attempt: int, retry_after: float | None = None) -> float:
        """Seconds to wait before ``attempt`` (1-based) runs.

        ``attempt`` is the attempt number *about to be scheduled*
        (2 = the first retry). ``retry_after`` is the provider's
        rate-limit hint, in seconds, when one was given.
        """
        if attempt <= 1:
            return 0.0
        delay = self.base_delay_seconds * (2 ** (attempt - 2))
        if retry_after is not None and retry_after > delay:
            delay = float(retry_after)
        # Bounded: the provider hint is respected up to the configured cap.
        return min(delay, self.max_delay_seconds)
