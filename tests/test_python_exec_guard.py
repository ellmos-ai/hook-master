"""Representative Codex Bash and unified-exec payloads; no script is executed."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "library" / "python_exec_guard.py"
SPEC = importlib.util.spec_from_file_location("python_exec_guard", SOURCE)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def payload(command, key="command"):
    return {"tool_name": "Bash", "tool_input": {key: command}}


def test_interpreterless_launch_forms_block():
    commands = [
        "& 'C:\\tools\\lock_scan.py' --json",
        "C:\\tools\\lock_scan.py --json",
        'Start-Process -FilePath "C:\\my tools\\lock_scan.py" -Wait',
        "Start-Process -Wait 'C:\\work\\scan.py'",
        "Start-Process -NoNewWindow 'C:\\work\\scan.py'",
        "saps -Wait 'C:\\work\\scan.py'",
        "Start-Process -WindowStyle Hidden -Wait 'C:\\work\\scan.py'",
        "Invoke-Item 'C:\\my tools\\lock_scan.py'",
        'cmd /c start "" "C:\\my tools\\lock_scan.py"',
        'cmd /c "start "" "C:\\my tools\\lock_scan.py""',
        "Write-Output ready; & 'C:\\tools\\lock_scan.py' --json",
        "if ($ready) { & 'C:\\tools\\lock_scan.py' }",
        'pwsh -NoProfile -Command "& C:\\tools\\lock_scan.py"',
        "Write-Output done # no command; & C:\\work\\scan.py\n& C:\\work\\scan.py",
        "& C:\\work\\scan.py # diagnostic comment",
    ]
    for command in commands:
        assert guard.blocking_reason(payload(command)), command
        assert guard.blocking_reason(payload(command, "cmd")), command


def test_argv_payload_and_explicit_interpreters():
    assert guard.blocking_reason(payload(["C:\\tools\\lock_scan.py", "--json"]))
    assert guard.blocking_reason(payload(["pwsh", "-Command", "& C:\\tools\\lock_scan.py"]))
    assert guard.blocking_reason(payload(["cmd", "/c", "start", "", "C:\\my tools\\lock_scan.py"]))
    for words in (
        ["Start-Process", "-Wait", "C:\\work\\scan.py"],
        ["Start-Process", "-NoNewWindow", "C:\\work\\scan.py"],
        ["saps", "-Wait", "C:\\work\\scan.py"],
    ):
        assert guard.blocking_reason(payload(words))
    allowed = [
        "python C:\\tools\\lock_scan.py --json",
        '& "C:\\Program Files\\Python312\\python.exe" "C:\\my tools\\lock_scan.py"',
        'Start-Process -FilePath "C:\\Program Files\\Python312\\python.exe" -ArgumentList "C:\\my tools\\lock_scan.py" -Wait',
        'Write-Output "Start-Process C:\\tools\\lock_scan.py"',
        "# & C:\\tools\\lock_scan.py",
        "# explanation; & C:\\work\\scan.py",
        "Write-Output done # explanation; & C:\\work\\scan.py",
        "&script.py",
        "Start-Process -ArgumentList 'C:\\work\\scan.py' -Wait python.exe",
        "Get-Content C:\\tools\\lock_scan.py",
    ]
    for command in allowed:
        assert not guard.blocking_reason(payload(command)), command
    assert not guard.blocking_reason(payload(["python.exe", "C:\\tools\\lock_scan.py"]))


def test_hook_exit_contract():
    blocked = subprocess.run(
        [sys.executable, str(SOURCE)],
        input=json.dumps(payload("& C:\\tools\\lock_scan.py")),
        text=True, capture_output=True, check=False,
    )
    assert blocked.returncode == 2
    assert "PYTHON-EXEC-GUARD" in blocked.stderr
    allowed = subprocess.run(
        [sys.executable, str(SOURCE)],
        input=json.dumps(payload("python C:\\tools\\lock_scan.py")),
        text=True, capture_output=True, check=False,
    )
    assert allowed.returncode == 0
