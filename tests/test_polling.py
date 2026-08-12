"""Tests for the pure adaptive-polling helpers."""

import pytest

from dpremote import polling


@pytest.mark.parametrize(
    "status,expected",
    [
        ("Off", False),
        ("Flame On", True),
        ("Ignition starting", True),
        ("Cleaning", True),
        ("Eco idle", True),
        ("Cooling down", True),
        ("Unknown state", True),
    ],
)
def test_is_stove_active(status, expected):
    assert polling.is_stove_active(status) is expected


def test_choose_interval_active_uses_active():
    assert polling.choose_interval_seconds("Flame On", 60, 900) == 60


def test_choose_interval_off_uses_idle():
    assert polling.choose_interval_seconds("Off", 60, 900) == 900


def test_choose_interval_idle_never_below_active():
    # A misconfigured idle < active is clamped up to the active interval.
    assert polling.choose_interval_seconds("Off", 120, 30) == 120
