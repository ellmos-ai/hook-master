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


# [U 2026-10-13] After the 5h window resets, the week decides: >10 % left ends
# both modes, 3-10 % left keeps the sparmodus and lifts the notaus, <=3 % keeps it.
@pytest.mark.parametrize(
    ("mode", "prior", "week_used", "expected"),
    [
        ("notaus", "off", 97, "notaus"),
        ("notaus", "off", 99, "notaus"),
        ("notaus", "off", 95, "manual-spar"),
        ("notaus", "auto-spar", 95, "auto-spar"),
        ("notaus", "off", 85, "off"),
        ("manual-spar", None, 95, "manual-spar"),
        ("manual-spar", None, 85, "off"),
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
