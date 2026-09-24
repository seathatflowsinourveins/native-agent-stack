"""REST admission for one paper execution-capacity run.

The budget is ``floor(min(configured_cap, observed x-ratelimit-limit) * headroom)``
calls per rolling 60 seconds. Three independent gates must all pass before a
call is admitted:

1. a token bucket refilled at ``budget / 60`` per second (smooths bursts);
2. a hard rolling-60-second count that never exceeds ``budget``;
3. the broker's own view: when ``x-ratelimit-remaining`` (less calls admitted
   since that response) falls to the reserve ``limit - budget`` before
   ``x-ratelimit-reset``, admission waits for the reset. Other users of the
   same account therefore slow this run down instead of causing 429s.

A 429 freezes every admission, is counted and backs off for ``Retry-After``
(seconds or HTTP-date), else until ``x-ratelimit-reset``, else an exponential
backoff. A changed ``x-ratelimit-limit`` header recomputes the budget, still
bounded by the configured cap, so the same code runs at 200/min and at
1000/min once the header rises. Only trading-origin responses may be fed to
``on_response``; the market-data origin carries its own, unrelated limit.

No clock is read implicitly: ``clock`` (monotonic seconds) and ``wall`` (Unix
seconds, for ``x-ratelimit-reset``) are injected.
"""
from __future__ import annotations

from collections import deque
from email.utils import parsedate_to_datetime
import math
import time

WINDOW_SECONDS = 60.0
MAX_CONFIGURED_CAP = 2000
KINDS = ("submit", "cancel", "read")


class GovernorError(RuntimeError):
    """Bounded reason code; never carries provider text."""


def int_header(headers, name):
    value = (headers or {}).get(name)
    if value is None:
        return None
    try:
        number = int(str(value).strip())
    except ValueError:
        return None
    return number if number >= 0 else None


def retry_after_seconds(value, now_wall):
    """Parse Retry-After as delta-seconds or an HTTP-date; None when absent/invalid."""
    if value is None:
        return None
    text = str(value).strip()
    if text.isdigit():
        return float(int(text))
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if when is None or when.tzinfo is None:
        return None
    return max(0.0, when.timestamp() - now_wall)


class RateGovernor:
    def __init__(self, configured_cap, *, headroom=0.9, burst=None, clock=time.monotonic,
                 wall=time.time, max_backoff=60.0):
        if type(configured_cap) is not int or not 1 <= configured_cap <= MAX_CONFIGURED_CAP:
            raise GovernorError("configured_cap_out_of_bounds")
        if (type(headroom) not in (int, float) or not math.isfinite(headroom)
                or not 0.1 <= headroom <= 1.0):
            raise GovernorError("headroom_out_of_bounds")
        if burst is not None and (type(burst) is not int or burst < 1):
            raise GovernorError("burst_out_of_bounds")
        if not 1.0 <= float(max_backoff) <= 600.0:
            raise GovernorError("max_backoff_out_of_bounds")
        self.configured_cap = configured_cap
        self.headroom = float(headroom)
        self.burst = burst
        self.clock, self.wall = clock, wall
        self.max_backoff = float(max_backoff)
        self.observed_limit = None
        self.tokens = 0.0
        self._last_refill = None
        self._sent = deque()
        self.frozen_until = None
        self.consecutive_429 = 0
        self.remaining = None
        self.reset_wall = None
        self._since_remaining = 0
        self.limit_history = []
        self.stats = {"admitted": {kind: 0 for kind in KINDS}, "http_429": 0,
                      "backoff_seconds": 0.0, "backoffs": [], "denied_frozen": 0,
                      "denied_window": 0, "denied_server_remaining": 0, "denied_tokens": 0,
                      "external_calls_noted": 0}

    # -- budget -----------------------------------------------------------------
    @property
    def effective_limit(self):
        if self.observed_limit is None:
            return None
        return min(self.configured_cap, self.observed_limit)

    @property
    def budget(self):
        limit = self.effective_limit
        if limit is None:
            return None
        return max(1, math.floor(limit * self.headroom))

    @property
    def reserve(self):
        limit = self.effective_limit
        return None if limit is None else limit - self.budget

    @property
    def capacity(self):
        if self.budget is None:
            return 0
        return float(self.burst if self.burst is not None else max(1, self.budget // 20))

    @property
    def rate_per_second(self):
        return 0.0 if self.budget is None else self.budget / WINDOW_SECONDS

    def observe_limit(self, limit):
        """Adopt a trading-origin x-ratelimit-limit (preflight or any later response)."""
        if type(limit) is not int or limit < 1:
            raise GovernorError("invalid_observed_limit")
        if limit == self.observed_limit:
            return
        now = self.clock()
        first = self.observed_limit is None
        self._refill(now)
        self.observed_limit = limit
        self.limit_history.append({"at_monotonic": now, "limit": limit,
                                   "effective_limit": self.effective_limit, "budget": self.budget})
        if first:
            self._last_refill = now
            self.tokens = min(self.capacity, 1.0)
        else:
            self.tokens = min(self.tokens, self.capacity)

    def note_external_calls(self, count, at=None):
        """Count calls made outside admission (e.g. the read-only preflight) in the window."""
        at = self.clock() if at is None else at
        for _ in range(int(count)):
            self._sent.append(at)
        self.stats["external_calls_noted"] += int(count)

    # -- admission --------------------------------------------------------------
    def _refill(self, now):
        if self._last_refill is None or self.budget is None:
            self._last_refill = now
            return
        elapsed = max(0.0, now - self._last_refill)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_second)
        self._last_refill = now

    def _expire(self, now):
        while self._sent and self._sent[0] <= now - WINDOW_SECONDS:
            self._sent.popleft()

    def _server_exhausted(self):
        if self.remaining is None or self.reset_wall is None:
            return False
        if self.wall() >= self.reset_wall:
            self.remaining = None
            self.reset_wall = None
            return False
        return self.remaining - self._since_remaining <= self.reserve

    def frozen(self, now=None):
        now = self.clock() if now is None else now
        return self.frozen_until is not None and now < self.frozen_until

    def try_acquire(self, kind):
        if kind not in KINDS:
            raise GovernorError("invalid_request_kind")
        if self.budget is None:
            raise GovernorError("rate_limit_unobserved")
        now = self.clock()
        if self.frozen(now):
            self.stats["denied_frozen"] += 1
            return False
        self._refill(now)
        self._expire(now)
        if len(self._sent) >= self.budget:
            self.stats["denied_window"] += 1
            return False
        if self._server_exhausted():
            self.stats["denied_server_remaining"] += 1
            return False
        if self.tokens < 1.0:
            self.stats["denied_tokens"] += 1
            return False
        self.tokens -= 1.0
        self._sent.append(now)
        self._since_remaining += 1
        self.stats["admitted"][kind] += 1
        return True

    def wait_hint(self):
        """Seconds until admission could next succeed (a bounded sleep hint)."""
        if self.budget is None:
            return 1.0
        now = self.clock()
        waits = [0.0]
        if self.frozen(now):
            waits.append(self.frozen_until - now)
        self._refill(now)
        self._expire(now)
        if self.tokens < 1.0:
            waits.append((1.0 - self.tokens) / self.rate_per_second)
        if len(self._sent) >= self.budget:
            waits.append(self._sent[0] + WINDOW_SECONDS - now)
        if self._server_exhausted():
            waits.append(self.reset_wall - self.wall())
        return max(0.0, min(WINDOW_SECONDS, max(waits)))

    def in_window(self):
        now = self.clock()
        self._expire(now)
        return len(self._sent)

    # -- responses --------------------------------------------------------------
    def on_response(self, kind, status, headers, *, inflight=0):
        """Feed one trading-origin response. Returns the backoff applied (0 if none)."""
        headers = {str(key).lower(): value for key, value in (headers or {}).items()}
        now, wall = self.clock(), self.wall()
        limit = int_header(headers, "x-ratelimit-limit")
        if limit:
            self.observe_limit(limit)
        remaining = int_header(headers, "x-ratelimit-remaining")
        reset = int_header(headers, "x-ratelimit-reset")
        if remaining is not None:
            self.remaining = remaining
            # Calls still in flight were admitted but may not be counted yet.
            self._since_remaining = max(0, int(inflight))
            self.reset_wall = float(reset) if reset is not None else None
        if status != 429:
            if status is not None:
                self.consecutive_429 = 0
            return 0.0
        self.stats["http_429"] += 1
        self.consecutive_429 += 1
        delay = retry_after_seconds(headers.get("retry-after"), wall)
        source = "retry_after"
        if delay is None and reset is not None and reset > wall:
            delay, source = reset - wall, "ratelimit_reset"
        if delay is None:
            delay, source = 2.0 ** (self.consecutive_429 - 1), "exponential"
        delay = min(self.max_backoff, max(1.0, float(delay)))
        self.frozen_until = max(self.frozen_until or now, now + delay)
        self.tokens = 0.0
        self._last_refill = now
        self.stats["backoff_seconds"] += delay
        self.stats["backoffs"].append({"kind": kind, "seconds": round(delay, 3), "source": source})
        return delay

    def summary(self):
        return {"configured_cap_per_minute": self.configured_cap,
                "observed_limit": self.observed_limit, "effective_limit": self.effective_limit,
                "headroom": self.headroom, "budget_per_minute": self.budget,
                "reserve_per_minute": self.reserve, "bucket_capacity": self.capacity,
                "admitted": dict(self.stats["admitted"]), "http_429": self.stats["http_429"],
                "backoff_seconds": round(self.stats["backoff_seconds"], 3),
                "backoffs": list(self.stats["backoffs"]),
                "denied": {key[len("denied_"):]: value for key, value in self.stats.items()
                           if key.startswith("denied_")},
                "external_calls_noted": self.stats["external_calls_noted"]}
