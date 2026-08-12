"""Tests for the pure CSV snapshot recorder helpers."""

import csv
import io

from dpremote import protocol as p
from dpremote import recorder


def _state() -> p.StoveState:
    return p.StoveState(
        burner_status="Flame On",
        error_code="All OK",
        exh_fan_speed_rpm=1600,
        flu_gas_temp_c=120,
        pellet_speed=5,
        power_level="Medium",
        pcb_temp_c=40,
        total_burn_time_h=291,
        burn_time_since_reset_h=69,
        pressure_switch_active=False,
        current_temp_c=21.0,
        target_temp_c=21.0,
        hvac_mode=p.HVAC_HEAT,
        heating=True,
    )


def test_state_to_row_covers_all_fields():
    row = recorder.state_to_row(_state(), "2026-08-12T10:00:00+00:00")
    assert set(row) == set(recorder.CSV_FIELDS)
    assert row["timestamp"] == "2026-08-12T10:00:00+00:00"
    assert row["burner_status"] == "Flame On"
    assert row["current_temp_c"] == 21.0
    assert row["exh_fan_speed_rpm"] == 1600
    assert row["pressure_switch_active"] is False


def test_header_and_row_roundtrip_via_csv():
    ts = "2026-08-12T10:00:00+00:00"
    text = recorder.header_line() + recorder.format_row(recorder.state_to_row(_state(), ts))
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 1
    assert rows[0]["timestamp"] == ts
    assert rows[0]["power_level"] == "Medium"
    assert rows[0]["total_burn_time_h"] == "291"


def test_append_snapshot_writes_header_once(tmp_path):
    path = str(tmp_path / "sub" / "pellet.csv")  # nested dir is created
    recorder.append_snapshot(path, _state(), "2026-08-12T10:00:00+00:00")
    recorder.append_snapshot(path, _state(), "2026-08-12T10:01:00+00:00")

    with open(path, encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    # Two data rows, single header (DictReader consumes the one header line).
    assert len(rows) == 2
    assert rows[0]["timestamp"] == "2026-08-12T10:00:00+00:00"
    assert rows[1]["timestamp"] == "2026-08-12T10:01:00+00:00"
