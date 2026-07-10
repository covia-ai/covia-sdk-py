"""429 backpressure retry policy (covia-sdk-py#3).

Venues shed load with ``429 Too Many Requests`` + ``Retry-After`` (request
rate limit / concurrent-job cap). A 429 means the request was refused BEFORE
any effect (no job created), so it is safe to retry automatically — even
``POST /invoke``. Policy mirrors the Java client (covia-core ``RetryPolicy``):
``Retry-After`` is the floor, backoff uses FULL jitter (randomise the whole
interval — otherwise every client that got the same ``Retry-After``
re-stampedes together), attempts and total wait are bounded, and exhaustion
raises a typed :class:`~covia.exceptions.RateLimitError`.

The decision function is pure (``random`` supplied by the caller) so tests
are deterministic.
"""

from __future__ import annotations

from email.utils import parsedate_to_datetime

MAX_ATTEMPTS = 4  # 1 try + 3 retries
BASE_DELAY_MS = 200
MAX_DELAY_MS = 10_000
BUDGET_MS = 30_000


def parse_retry_after_ms(header: str | None, now_ms: float) -> float:
    """Parse a ``Retry-After`` header (delta-seconds or HTTP-date) to ms from now."""
    if not header:
        return 0
    try:
        return max(0.0, float(header) * 1000)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(header)
        return max(0.0, dt.timestamp() * 1000 - now_ms)
    except Exception:
        return 0


def retry_delay_ms(attempt: int, retry_after_ms: float, remaining_budget_ms: float, random: float) -> float:
    """Delay before the next attempt after a 429, or ``-1`` to give up."""
    if attempt >= MAX_ATTEMPTS:
        return -1
    backoff = min(MAX_DELAY_MS, BASE_DELAY_MS * 2 ** (attempt - 1))
    delay = max(retry_after_ms, random * backoff)
    return -1 if delay > remaining_budget_ms else delay
