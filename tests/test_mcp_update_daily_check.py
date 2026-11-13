"""mcp_update_daily_check: report line, background-run contract and fail-open."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "library" / "mcp_update_daily_check.py"

RED_LOG = (
    "  VERALTET  pkg-local   installiert=1 npm=2 repo=2\n"
    "  VERALTET  pkg-reg     mcp-registry=1 npm=2\n"
    "  Registry-Aktualität: ROT (veraltet=1, unklar=0)\n"
    "GESAMT: ROT\n"
)


def run(home: Path, *args: str, script: Path | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "PYTHONIOENCODING": "utf-8"}
    env["MCP_UPDATE_CHECK_SCRIPT"] = str(script or home / "missing.py")
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SOURCE), *args],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=60,
    )


def test_selftest():
    result = run(Path.cwd(), "--selftest")
    assert result.returncode == 0 and "selftest ok" in result.stdout


def test_missing_check_script_reports_and_does_not_spawn(tmp_path):
    result = run(tmp_path)
    assert result.returncode == 0
    assert "Pruefskript fehlt" in result.stdout
    assert not (tmp_path / ".claude" / "mcp_npm_check" / "started.txt").exists()


def test_run_writes_log_atomically_and_hook_reports_it(tmp_path):
    fake = tmp_path / "fake_check.py"
    fake.write_text(f"print({RED_LOG!r}, end='')\n", encoding="utf-8")
    assert run(tmp_path, "--run", script=fake).returncode == 0
    state = tmp_path / ".claude" / "mcp_npm_check"
    assert (state / "last.log").read_text(encoding="utf-8") == RED_LOG
    assert not (state / "last.tmp").exists()

    (state / "started.txt").write_text("fresh", encoding="utf-8")  # fresh stamp: hook must not spawn
    result = run(tmp_path, script=fake)
    assert result.returncode == 0
    assert "ROT" in result.stdout
    assert "lokal veraltet: pkg-local" in result.stdout
    assert "Veroeffentlichung offen): pkg-reg" in result.stdout


def test_no_result_with_fresh_stamp_does_not_claim_a_start(tmp_path):
    fake = tmp_path / "fake_check.py"
    fake.write_text("print('GESAMT: GRÜN')\n", encoding="utf-8")
    state = tmp_path / ".claude" / "mcp_npm_check"
    state.mkdir(parents=True)
    (state / "started.txt").write_text("fresh", encoding="utf-8")
    result = run(tmp_path, script=fake)
    assert result.returncode == 0
    assert "laeuft noch oder brach ohne Ergebnis ab" in result.stdout


def test_fails_open_on_unwritable_state(tmp_path):
    fake = tmp_path / "fake_check.py"
    fake.write_text("print('GESAMT: GRÜN')\n", encoding="utf-8")
    (tmp_path / ".claude" / "mcp_npm_check" / "started.txt").mkdir(parents=True)  # stamp cannot be written
    result = run(tmp_path, script=fake)
    assert result.returncode == 0
    assert "Hook-Fehler" in result.stdout
