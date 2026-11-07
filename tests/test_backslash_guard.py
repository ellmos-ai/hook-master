"""backslash_guard: block decisions and the stdin/exit-code contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "library" / "backslash_guard.py"


def run(stdin: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SOURCE)],
        input=stdin, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )


def payload(command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


@pytest.mark.parametrize("command", [
    "python - <<'EOF'\np = \"C:\\work\\repos\"\nEOF",  # drive path, single backslashes
    "printf '%s' 'A\\\\B'",                           # doubled backslash
    "cat > notes.md <<'EOF'\nclone: C:\\\\work\\\\repos\nEOF",
])
def test_blocks_with_reason(command):
    result = run(payload(command))
    assert result.returncode == 2
    assert "backslash_guard" in result.stderr


@pytest.mark.parametrize("command", [
    "git -C C:/work/repos status",
    "grep -n 'a\\.b' file.txt",
    "sed -n 's/\\n//' file.txt",
    "echo 'C:\\x' # backslash-ok",
])
def test_allows(command):
    result = run(payload(command))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("stdin", ["", "{}", "not json", json.dumps({"tool_input": None})])
def test_fails_open(stdin):
    assert run(stdin).returncode == 0


def test_selftest():
    result = subprocess.run([sys.executable, "-X", "utf8", str(SOURCE), "--selftest"],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and "selftest ok" in result.stdout
