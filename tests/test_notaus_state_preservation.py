from __future__ import annotations

import importlib.util
import io
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_library_module(name: str, filename: str):
    path = REPO / "library" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_budget_recovery_preserves_park_markers_and_reports_pending_resume(tmp_path, monkeypatch, capsys):
    guard = _load_library_module("token_budget_guard_test", "token_budget_guard.py")
    bridge = tmp_path / "token_budget.json"
    state = tmp_path / "sparmodus_state.json"
    guard_state = tmp_path / "token_budget_guard_state.json"
    config = tmp_path / "token_budget_config.json"

    _write(bridge, {"written_at": time.time(), "five_hour": {"used_percentage": 0}})
    _write(
        state,
        {
            "mode": "notaus",
            "prior_mode": "off",
            "paused_goals": ["goal-1", "goal-2"],
            "paused_agents": [{"name": "worker-1"}],
        },
    )
    _write(guard_state, {})
    _write(config, {})

    monkeypatch.setattr(guard, "BRIDGE_PATH", str(bridge))
    monkeypatch.setattr(guard, "SPARMODUS_STATE_PATH", str(state))
    monkeypatch.setattr(guard, "GUARD_STATE_PATH", str(guard_state))
    monkeypatch.setattr(guard, "CONFIG_PATH", str(config))
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"session_id":"test-session"}'))

    assert guard.main() == 0

    written = json.loads(state.read_text(encoding="utf-8"))
    assert written["mode"] == "off"
    assert written["paused_goals"] == ["goal-1", "goal-2"]
    assert written["paused_agents"] == [{"name": "worker-1"}]
    assert "Aufhebung ausstehend" in capsys.readouterr().out


def test_wake_check_reports_preserved_park_markers(tmp_path, monkeypatch, capsys):
    wake = _load_library_module("notaus_wake_check_test", "notaus_wake_check.py")
    state = tmp_path / "sparmodus_state.json"
    _write(
        state,
        {
            "mode": "notaus",
            "wake_at": 0,
            "prior_mode": "off",
            "paused_goals": ["goal-1"] * 18,
            "paused_agents": [{"name": "worker-1"}] * 3,
        },
    )
    monkeypatch.setattr(wake, "SPARMODUS_STATE_PATH", str(state))
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))

    assert wake.main() == 0

    output = capsys.readouterr().out
    assert "Aufhebung ausstehend" in output
    assert "18 pausierte Goals" in output
    assert "3 geparkte Worker" in output



import pytest


# [U 2026-10-13] + T-20261115-791506015: After the 5h window resets, the week
# decides: >20 % left (<80 % used) ends both modes, 3-20 % left (80-96 % used)
# keeps sparmodus and lifts notaus, <=3 % left (>=97 % used) keeps notaus.
@pytest.mark.parametrize(
    ("mode", "prior", "week_used", "expected"),
    [
        ("notaus", "off", 97, "notaus"),
        ("notaus", "off", 99, "notaus"),
        ("notaus", "off", 95, "manual-spar"),
        ("notaus", "auto-spar", 95, "auto-spar"),
        ("notaus", "off", 85, "manual-spar"),
        ("notaus", "off", 75, "off"),
        ("manual-spar", None, 95, "manual-spar"),
        ("manual-spar", None, 85, "manual-spar"),
        ("manual-spar", None, 75, "off"),
    ],
)
def test_weekly_window_has_its_own_thresholds(tmp_path, monkeypatch, mode, prior, week_used, expected):
    guard = _load_library_module(f"token_budget_guard_week_{mode}_{week_used}", "token_budget_guard.py")
    bridge = tmp_path / "token_budget.json"
    state = tmp_path / "sparmodus_state.json"
    guard_state = tmp_path / "token_budget_guard_state.json"
    config = tmp_path / "token_budget_config.json"

    _write(bridge, {"written_at": time.time(), "five_hour": {"used_percentage": 0},
                    "seven_day": {"used_percentage": week_used, "resets_at": 1792209600}})
    _write(state, {"mode": mode, "prior_mode": prior})
    _write(guard_state, {})
    _write(config, {})

    monkeypatch.setattr(guard, "BRIDGE_PATH", str(bridge))
    monkeypatch.setattr(guard, "SPARMODUS_STATE_PATH", str(state))
    monkeypatch.setattr(guard, "GUARD_STATE_PATH", str(guard_state))
    monkeypatch.setattr(guard, "CONFIG_PATH", str(config))
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"session_id":"test-session"}'))

    assert guard.main() == 0
    assert json.loads(state.read_text(encoding="utf-8"))["mode"] == expected


def test_weekly_advisory_names_seven_day_window_and_manual_notaus_holds_with_null_5h(tmp_path, monkeypatch, capsys):
    guard = _load_library_module("token_budget_guard_advisory_test", "token_budget_guard.py")
    bridge = tmp_path / "token_budget.json"
    state = tmp_path / "sparmodus_state.json"
    guard_state = tmp_path / "token_budget_guard_state.json"
    config = tmp_path / "token_budget_config.json"
    now = time.time()

    _write(bridge, {"written_at": now, "five_hour": {"used_percentage": None, "resets_at": None},
                    "seven_day": {"used_percentage": 92.0, "resets_at": now + 300000}})
    _write(state, {"mode": "off"})
    _write(guard_state, {})
    _write(config, {})

    monkeypatch.setattr(guard, "BRIDGE_PATH", str(bridge))
    monkeypatch.setattr(guard, "SPARMODUS_STATE_PATH", str(state))
    monkeypatch.setattr(guard, "GUARD_STATE_PATH", str(guard_state))
    monkeypatch.setattr(guard, "CONFIG_PATH", str(config))
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"session_id":"s-adv"}'))

    assert guard.main() == 0
    out = capsys.readouterr().out
    assert "7d-Wochenlimit" in out
    assert "5h-Session-Limit >=" not in out

    _write(state, {"mode": "notaus", "prior_mode": "manual-spar", "set_by": "user", "wake_at": now + 300000})
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"session_id":"s-adv"}'))
    assert guard.main() == 0
    assert json.loads(state.read_text(encoding="utf-8"))["mode"] == "notaus"


def test_wake_check_filters_foreign_and_stale_session_park_markers(tmp_path, monkeypatch, capsys):
    wake = _load_library_module("notaus_wake_check_session_test", "notaus_wake_check.py")
    state = tmp_path / "sparmodus_state.json"
    now = time.time()
    _write(
        state,
        {
            "mode": "off",
            "paused_agents": {
                "stale-legacy": {"parked_at": now - 5 * 86400, "resumed_at": None},
                "foreign-worker": {"parked_at": now - 60, "session_id": "other-sess", "resumed_at": None},
                "own-worker": {"parked_at": now - 60, "session_id": "my-sess", "resumed_at": None},
            },
        },
    )
    monkeypatch.setattr(wake, "SPARMODUS_STATE_PATH", str(state))
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"session_id":"brand-new-sess"}'))
    assert wake.main() == 0
    assert capsys.readouterr().out == ""

    monkeypatch.setattr(sys, "stdin", io.StringIO('{"session_id":"my-sess"}'))
    assert wake.main() == 0
    assert "1 geparkte Worker" in capsys.readouterr().out


def test_wake_check_reports_dict_park_markers_when_not_in_notaus(tmp_path, monkeypatch, capsys):
    wake = _load_library_module("notaus_wake_check_dict_test", "notaus_wake_check.py")
    state = tmp_path / "sparmodus_state.json"
    _write(
        state,
        {
            "mode": "off",
            "paused_goals": {"goal-1": {}},
            "paused_agents": {"worker-1": {"resumed_at": None}},
        },
    )
    monkeypatch.setattr(wake, "SPARMODUS_STATE_PATH", str(state))
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))

    assert wake.main() == 0

    output = capsys.readouterr().out
    assert "additionalContext" in output
    assert "erhaltener Goal-Parkvermerk" in output
    assert "1 geparkte Worker" in output

