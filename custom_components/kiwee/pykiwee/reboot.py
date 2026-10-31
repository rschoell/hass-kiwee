"""Bookkeeping for an adapter restart (no Home Assistant imports, so it can be unit tested)."""

from __future__ import annotations

from dataclasses import dataclass

# Measured on a client adapter: it keeps answering for about 20 s after the request, is then
# unreachable for about 25 s and answers again about 45 s after the request (the network
# controller is reported to take 30-60 s). So "reachable" right after the request does not mean
# "back": the adapter has to be seen going down first.
DEFAULT_MIN_WAIT = 10.0  # seconds before the first probe
DEFAULT_MAX_WAIT = 240.0  # give up if it does not come back after this long
DEFAULT_NO_DOWN_TIMEOUT = 90.0  # never saw it go down: assume the reboot did not happen


@dataclass
class RebootWatch:
    """Tracks the time since a reboot was requested and whether the adapter went down."""

    min_wait: float = DEFAULT_MIN_WAIT
    max_wait: float = DEFAULT_MAX_WAIT
    no_down_timeout: float = DEFAULT_NO_DOWN_TIMEOUT
    started: float | None = None
    went_down: bool = False

    @property
    def active(self) -> bool:
        """A reboot was requested and the adapter has not been seen coming back yet."""
        return self.started is not None

    def start(self, now: float) -> None:
        """Remember when the reboot request was sent."""
        self.started = now
        self.went_down = False

    def settling(self, now: float) -> bool:
        """True right after the request: do not probe the adapter yet."""
        return self.started is not None and now - self.started < self.min_wait

    def _finish(self) -> None:
        self.started = None
        self.went_down = False

    def on_probe(self, now: float, reachable: bool) -> str:
        """Record the result of a probe: "back", "waiting" or "timeout"."""
        if self.started is None:
            return "back"
        elapsed = now - self.started
        if not reachable:
            self.went_down = True
            if elapsed >= self.max_wait:
                self._finish()
                return "timeout"
            return "waiting"
        if self.went_down or elapsed >= self.no_down_timeout:
            self._finish()
            return "back"
        return "waiting"
