"""Adaptive polling helpers (pure, no I/O, no Home Assistant imports).

An idle pellet stove changes very little, so there's no point polling the cloud
relay as often as when it's actively burning. These helpers decide the next poll
interval from the burner status: the normal ("active") interval while the stove
is on or transitioning, and a slower ("idle") interval once it's fully off — kept
non-zero so a remote/scheduled turn-on is still detected within one idle cycle.
"""

from __future__ import annotations

#: The only burner status that counts as "fully off". Everything else
#: (Flame On, Ignition starting, Cleaning, Eco idle, Cooling down, Unknown) is
#: treated as active so transitions are polled promptly.
OFF_STATUS = "Off"


def is_stove_active(burner_status: str) -> bool:
    """Return True unless the stove is fully off."""
    return burner_status != OFF_STATUS


def choose_interval_seconds(
    burner_status: str,
    active_seconds: int,
    idle_seconds: int,
    seconds_since_active: float = 0.0,
    grace_seconds: int = 0,
) -> int:
    """Return the next poll interval.

    - Active (on/transitioning): the active interval.
    - Recently off (within ``grace_seconds`` of the last active reading): keep
      the active interval, so a quick off→on is caught almost immediately.
    - Off past the grace window: the idle interval.

    The idle interval never drops below the active one (a larger "idle" that is
    accidentally configured smaller would defeat the purpose, so it's clamped).
    """
    if is_stove_active(burner_status):
        return active_seconds
    if seconds_since_active < grace_seconds:
        return active_seconds
    return max(active_seconds, idle_seconds)
