from __future__ import annotations

import json
import shutil
import sys

import pytest

from hook_master.consent import ConsentStore
from hook_master.doctor import run as run_doctor
from hook_master.providers import (
    PROVIDER_REGISTRY,
    AgyProvider,
    ClaudeProvider,
    CodexProvider,
    GitProvider,
    InterpreterAliasError,
    InvalidTimeoutError,
    KimiProvider,
    ManualProvider,
    format_raw_script_snippet,
    resolve_canonical_script,
    resolve_provider,
    run_self_test,
    validate_interpreter,
    validate_timeout,
    verify_timeout_kills,
)
from hook_master.registry import HookRegistry

# ---------------------------------------------------------------------------
# Pflicht-Invarianten (T-20260921-750493182)
# ---------------------------------------------------------------------------


def test_validate_interpreter_accepts_sys_executable():
    resolved = validate_interpreter(sys.executable)
    assert resolved.is_file()
    assert resolved.stat().st_size > 0


def test_validate_interpreter_rejects_empty():
    with pytest.raises(ValueError, match="Interpreter darf nicht leer sein"):
        validate_interpreter("")


def test_validate_interpreter_rejects_nonexistent():
    with pytest.raises(FileNotFoundError):
        validate_interpreter("this_executable_does_not_exist_xyz123.exe")


def test_validate_interpreter_rejects_zero_byte_file(tmp_path):
    zero_exe = tmp_path / "mock_app_alias.exe"
    zero_exe.write_bytes(b"")
    assert zero_exe.stat().st_size == 0

    with pytest.raises(InterpreterAliasError, match="0-Byte App-Execution-Alias"):
        validate_interpreter(zero_exe)


def test_validate_interpreter_rejects_python3_on_windows():
    if sys.platform != "win32":
        pytest.skip("Windows-spezifische Store-Alias-Invariante")
    with pytest.raises(InterpreterAliasError, match="(Store-Alias|0-Byte)"):
        validate_interpreter("python3")


def test_validate_timeout_accepts_positive():
    assert validate_timeout(10) == 10
    assert validate_timeout("15") == 15
    assert validate_timeout(1) == 1


def test_validate_timeout_rejects_none():
    with pytest.raises(InvalidTimeoutError, match="darf nicht None sein"):
        validate_timeout(None)


def test_validate_timeout_rejects_zero_and_negative():
    with pytest.raises(InvalidTimeoutError, match="positiv sein"):
        validate_timeout(0)
    with pytest.raises(InvalidTimeoutError, match="positiv sein"):
        validate_timeout(-5)


def test_verify_timeout_kills_effective():
    """Beweist, dass der Timeout einen haengenden Prozess nachweislich toetet."""
    killed = verify_timeout_kills(timeout=0.2)
    assert killed is True


def test_run_self_test_reports_all_ok():
    report = run_self_test(timeout=0.2)
    assert report["ok"] is True
    assert report["interpreter_valid"] is True
    assert report["alias_detection_works"] is True
    assert report["timeout_kills"] is True


# ---------------------------------------------------------------------------
# Regression T-20260921-750493182 Runde 3: alias_detection_works war auf
# ubuntu-latest/macos-latest IMMER False, weil der alte Selbsttest gegen den
# Namen "python3" prüfte -- ein legitimer, realer Interpreter auf POSIX.
# Diese Tests simulieren alle drei Zielplattformen per monkeypatch, statt
# sich auf das tatsächliche CI-Runner-Betriebssystem zu verlassen.
#
# Bewusst NICHT per monkeypatch.setattr(sys, "platform", "win32") getestet:
# der Windows-only Zweig von validate_interpreter() ("python3" verbotener
# Name), weil er intern shutil.which() aufruft -- und shutil.which() macht
# auf einem REALEN POSIX-Host bei sys.platform=="win32" NoneType-Crashes
# (fehlendes nt-Modul), da es selbst nicht nur nach sys.platform verzweigt,
# sondern echte OS-Internals braucht. Dieser Zweig bleibt ueber den
# bestehenden test_validate_interpreter_rejects_python3_on_windows oben
# abgedeckt (skip-basiert, laeuft echt nur auf windows-latest).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fake_platform", ["win32", "linux", "darwin"])
def test_run_self_test_alias_detection_works_on_every_platform(monkeypatch, fake_platform):
    monkeypatch.setattr(sys, "platform", fake_platform)
    report = run_self_test(timeout=0.2)
    assert report["alias_detection_works"] is True
    assert report["ok"] is True


def test_validate_interpreter_accepts_python3_when_platform_is_not_windows(monkeypatch, tmp_path):
    """Ausserhalb von Windows ist 'python3' kein verbotener Name -- ein
    echter, nicht-0-Byte Kandidat wird unveraendert akzeptiert (das war der
    eigentliche Bug: die alte Selbsttest-Logik nahm bislang das Gegenteil an)."""
    monkeypatch.setattr(sys, "platform", "linux")
    fake_python3 = tmp_path / "python3"
    fake_python3.write_bytes(b"#!/bin/sh\n")
    monkeypatch.setattr(shutil, "which", lambda name: str(fake_python3) if name == "python3" else None)
    resolved = validate_interpreter("python3")
    assert resolved == fake_python3


# ---------------------------------------------------------------------------
# Provider-Adapter (claude / codex / kimi / agy / git / manual)
# ---------------------------------------------------------------------------


def test_claude_provider_emits_valid_structure():
    provider = ClaudeProvider()
    snippet = provider.hook_snippet(python_executable=sys.executable)
    assert "PreToolUse" not in snippet["hooks"]
    assert set(snippet["hooks"]) == {"SessionStart", "UserPromptSubmit"}
    for event in ("SessionStart", "UserPromptSubmit"):
        hook_list = snippet["hooks"][event]
        assert len(hook_list) == 1
        assert hook_list[0]["hooks"][0]["type"] == "command"


def test_claude_provider_pretooluse_blocker():
    provider = ClaudeProvider()
    blocker = provider.pretooluse_blocker_snippet(python_executable=sys.executable)
    assert "PreToolUse" in blocker["hooks"]
    entry = blocker["hooks"]["PreToolUse"][0]
    assert entry["matcher"] == "Edit|Write|MultiEdit|NotebookEdit"
    assert "PreToolUse" in entry["hooks"][0]["command"]


def test_codex_provider_emits_valid_structure():
    provider = CodexProvider()
    snippet = provider.hook_snippet(python_executable=sys.executable, timeout=10)
    assert "PreToolUse" not in snippet["hooks"]
    assert set(snippet["hooks"]) == {"SessionStart", "UserPromptSubmit"}
    hook_item = snippet["hooks"]["SessionStart"][0]["hooks"][0]
    assert hook_item["command"] == hook_item["commandWindows"]
    assert hook_item["timeout"] == 10


def test_codex_provider_action_guard():
    provider = CodexProvider()
    blocker = provider.pretooluse_blocker_snippet(python_executable=sys.executable)
    assert "PreToolUse" in blocker["hooks"]
    entry = blocker["hooks"]["PreToolUse"][0]
    assert entry["matcher"] == "^apply_patch$"
    assert entry["hooks"][0]["timeout"] == 10


def test_agy_provider_snippet():
    provider = AgyProvider()
    snippet = provider.script_snippet(
        "library/guards.py",
        event="PreInvocation",
        python_executable=sys.executable,
    )
    assert "PreInvocation" in snippet["hooks"]
    assert snippet["hooks"]["PreInvocation"][0]["type"] == "command"


def test_kimi_provider_emits_toml_array_structure():
    provider = KimiProvider()
    snippet = provider.script_snippet(
        "library/guards.py",
        event="PreToolUse",
        python_executable=sys.executable,
        matcher="WriteFile|StrReplaceFile",
        timeout=15,
    )
    assert len(snippet["hooks"]) == 1
    hook = snippet["hooks"][0]
    assert hook["event"] == "PreToolUse"
    assert hook["timeout"] == 15
    assert hook["matcher"] == "WriteFile|StrReplaceFile"


def test_git_provider_stub():
    assert GitProvider().is_available() is False
    assert GitProvider().reason


def test_manual_provider_available():
    assert ManualProvider().is_available() is True


def test_provider_registry_contains_all_six():
    assert set(PROVIDER_REGISTRY.keys()) == {"claude", "codex", "kimi", "agy", "git", "manual"}


def test_resolve_provider_fallback_chain():
    class ConfigMock:
        order = ["nonexistent", "git", "manual"]

    chosen = resolve_provider(ConfigMock())
    assert chosen.name == "manual"


# ---------------------------------------------------------------------------
# Kanonische Roh-Skripte (guards / token_budget_guard / notaus_wake_check)
# ---------------------------------------------------------------------------


def test_resolve_canonical_scripts_and_aliases():
    assert resolve_canonical_script("guards")["filename"] == "guards.py"
    assert resolve_canonical_script("token_budget_guard")["filename"] == "token_budget_guard.py"
    assert resolve_canonical_script("token-budget-guard")["filename"] == "token_budget_guard.py"
    assert resolve_canonical_script("notaus_wake_check")["filename"] == "notaus_wake_check.py"
    assert resolve_canonical_script("notaus-wake-check")["filename"] == "notaus_wake_check.py"


def test_format_raw_script_guards_claude():
    snippet = format_raw_script_snippet("guards", "claude", python_executable=sys.executable)
    assert "PreToolUse" in snippet["hooks"]
    entry = snippet["hooks"]["PreToolUse"][0]
    assert entry["matcher"] == "Edit|Write|MultiEdit|NotebookEdit"
    assert "-S -X utf8" in entry["hooks"][0]["command"]


def test_format_raw_script_guards_codex():
    snippet = format_raw_script_snippet("guards", "codex", python_executable=sys.executable)
    assert "PreToolUse" in snippet["hooks"]
    entry = snippet["hooks"]["PreToolUse"][0]
    assert entry["matcher"] == "^apply_patch$"
    assert entry["hooks"][0]["timeout"] == 10
    assert entry["hooks"][0]["statusMessage"] == "guards: pre-tool safety check"


def test_format_raw_script_token_budget_guard():
    snippet = format_raw_script_snippet("token-budget-guard", "codex", python_executable=sys.executable)
    assert "UserPromptSubmit" in snippet["hooks"]
    hook = snippet["hooks"]["UserPromptSubmit"][0]["hooks"][0]
    assert hook["timeout"] == 10


def test_format_raw_script_notaus_wake_check():
    snippet_claude = format_raw_script_snippet("notaus-wake-check", "claude", python_executable=sys.executable)
    assert "SessionStart" in snippet_claude["hooks"]

    snippet_agy = format_raw_script_snippet("notaus-wake-check", "agy", python_executable=sys.executable)
    assert "PreInvocation" in snippet_agy["hooks"]


# ---------------------------------------------------------------------------
# Doctor Invarianten-Scanning
# ---------------------------------------------------------------------------


def test_doctor_detects_alias_in_config(tmp_path):
    registry = HookRegistry(tmp_path / "registry.json")
    # Synthetischer 0-Byte-Alias-Kandidat statt "python3": "python3" ist auf
    # POSIX ein legitimer Interpreter (T-20260921-750493182, Runde 3) und
    # waere dort faelschlich NICHT als Invarianten-Verstoss erkannt worden.
    fake_alias = tmp_path / "mock_alias.exe"
    fake_alias.write_bytes(b"")
    bad_config = tmp_path / "settings.json"
    bad_config.write_text(
        json.dumps({
            "hooks": {
                "PreToolUse": [
                    {"hooks": [{"type": "command", "command": f"{fake_alias} script.py"}]}
                ]
            }
        }),
        encoding="utf-8",
    )
    entry = {
        "id": "consumer:bad",
        "kind": "consumer",
        "title": "Bad Config Hook",
        "event": "PreToolUse",
        "source": {"kind": "external-module", "module": "bad"},
        "targets": [{"agent": "claude-code", "config_path": str(bad_config)}],
        "consumers": [],
        "status": "active",
        "adoption": {"laptop": "adopted"},
    }
    registry.register(entry)
    report = run_doctor(registry, consent=ConsentStore(tmp_path / "allowlist.json"))
    assert report["exit_code"] == 2
    finding = report["entries"][0]["findings"][0]
    assert finding["state"] == "invalid-hook-invariants"


def test_doctor_detects_invalid_timeout_in_config(tmp_path):
    registry = HookRegistry(tmp_path / "registry.json")
    bad_config = tmp_path / "settings.json"
    bad_config.write_text(
        json.dumps({
            "hooks": {
                "PreToolUse": [
                    {"hooks": [{"type": "command", "command": f"{sys.executable} script.py", "timeout": 0}]}
                ]
            }
        }),
        encoding="utf-8",
    )
    entry = {
        "id": "consumer:bad-timeout",
        "kind": "consumer",
        "title": "Bad Timeout Hook",
        "event": "PreToolUse",
        "source": {"kind": "external-module", "module": "bad"},
        "targets": [{"agent": "claude-code", "config_path": str(bad_config)}],
        "consumers": [],
        "status": "active",
        "adoption": {"laptop": "adopted"},
    }
    registry.register(entry)
    report = run_doctor(registry, consent=ConsentStore(tmp_path / "allowlist.json"))
    assert report["exit_code"] == 2
    finding = report["entries"][0]["findings"][0]
    assert finding["state"] == "invalid-hook-invariants"
