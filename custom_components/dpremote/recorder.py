"""CSV snapshot logging for DPRemote.

Appends every successful poll to a CSV file so the data can be crunched later
(spreadsheets, notebooks) for tuning power levels, schedules, etc. This is on
top of Home Assistant's own long-term statistics; it's a plain, portable export.

The row/formatting logic is pure and unit-tested; the thin file append is the
only I/O and is done from the coordinator's executor thread.
"""

from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone

from . import protocol as p

CSV_FIELDS: list[str] = [
    "timestamp",
    "burner_status",
    "hvac_mode",
    "heating",
    "error_code",
    "current_temp_c",
    "target_temp_c",
    "power_level",
    "flu_gas_temp_c",
    "exh_fan_speed_rpm",
    "pellet_speed",
    "pcb_temp_c",
    "total_burn_time_h",
    "burn_time_since_reset_h",
    "pressure_switch_active",
]


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string (seconds precision)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def state_to_row(state: p.StoveState, timestamp: str) -> dict[str, object]:
    """Map a StoveState to a CSV row dict keyed by CSV_FIELDS."""
    return {
        "timestamp": timestamp,
        "burner_status": state.burner_status,
        "hvac_mode": state.hvac_mode,
        "heating": state.heating,
        "error_code": state.error_code,
        "current_temp_c": state.current_temp_c,
        "target_temp_c": state.target_temp_c,
        "power_level": state.power_level,
        "flu_gas_temp_c": state.flu_gas_temp_c,
        "exh_fan_speed_rpm": state.exh_fan_speed_rpm,
        "pellet_speed": state.pellet_speed,
        "pcb_temp_c": state.pcb_temp_c,
        "total_burn_time_h": state.total_burn_time_h,
        "burn_time_since_reset_h": state.burn_time_since_reset_h,
        "pressure_switch_active": state.pressure_switch_active,
    }


def format_row(row: dict[str, object]) -> str:
    """Render one CSV data line (no header, no trailing newline stripping)."""
    buf = io.StringIO()
    csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore").writerow(row)
    return buf.getvalue()


def header_line() -> str:
    """Render the CSV header line."""
    buf = io.StringIO()
    csv.DictWriter(buf, fieldnames=CSV_FIELDS).writeheader()
    return buf.getvalue()


def append_snapshot(path: str, state: p.StoveState, timestamp: str | None = None) -> None:
    """Append one snapshot to ``path``, writing a header if the file is new.

    Blocking file I/O — call from an executor, not the event loop.
    """
    if timestamp is None:
        timestamp = utc_now_iso()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new_file = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", encoding="utf-8", newline="") as handle:
        if new_file:
            handle.write(header_line())
        handle.write(format_row(state_to_row(state, timestamp)))
