"""library/lock_edit_guard.py: finds lock-master's lock_guard.py and runs it, with no lock logic of its own."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

SHIM = Path(__file__).resolve().parents[1] / "library" / "lock_edit_guard.py"


def run(env_extra, args=("pretooluse", "--actor", "codex"), payload="{}"):
    env = {**os.environ, **env_extra}
    return subprocess.run([sys.executable, str(SHIM), *args], input=payload, capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=60)


def fake_guard(tmp_path, code):
    plugin = tmp_path / "lock-master" / "plugin"
    plugin.mkdir(parents=True)
    (plugin / "lock_guard.py").write_text(code, encoding="utf-8")
    return tmp_path / "lock-master"


def test_arguments_stdin_and_exit_code_reach_the_guard(tmp_path):
    root = fake_guard(tmp_path, "import sys\nprint(sys.argv[1:], sys.stdin.read())\nsys.exit(2)\n")
    done = run({"ELLMOS_LOCK_MASTER": str(root)}, payload="PAYLOAD")
    assert done.returncode == 2
    assert "['pretooluse', '--actor', 'codex'] PAYLOAD" in done.stdout


def test_env_may_name_the_repo_the_plugin_dir_or_the_file(tmp_path):
    root = fake_guard(tmp_path, "import sys\nsys.exit(3)\n")
    for value in (root, root / "plugin", root / "plugin" / "lock_guard.py"):
        assert run({"ELLMOS_LOCK_MASTER": str(value)}).returncode == 3, value


def test_missing_lock_master_says_so_and_does_not_block(tmp_path):
    done = run({"ELLMOS_LOCK_MASTER": str(tmp_path / "nowhere"), "USERPROFILE": str(tmp_path), "HOME": str(tmp_path)})
    if "lock checks are inactive" not in done.stderr:  # a real lock-master clone sits in a default location
        pytest.skip("lock-master found through a default location")
    assert done.returncode == 0


def test_real_lock_master_denies_a_foreign_lock_when_present(tmp_path):
    probe = run({}, payload=json.dumps({"tool_name": "Read", "tool_input": {}}))
    if "lock checks are inactive" in probe.stderr:
        pytest.skip("no lock-master on this host")
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "LOCK.txt").write_text(
        f"owner: gemini@OTHERHOST\nhost: OTHERHOST\ncreated: {datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}\n"
        "expires_after: 24h\nmode: hard\n", encoding="utf-8")
    payload = json.dumps({"tool_name": "StrReplaceFile", "cwd": str(tmp_path), "session_id": "s1",
                          "tool_input": {"path": "a.py"}})
    args = ("pretooluse", "--actor", "kimi")
    denied = run({}, args, payload)
    if denied.returncode == 0:
        pytest.skip("the lock-master found on this host predates 1.8 (no Kimi tools / --actor)")
    assert denied.returncode == 2 and "foreign active lock" in denied.stderr
    (tmp_path / "LOCK.txt").rename(tmp_path / "LOCK.off")
    assert run({}, args, payload).returncode == 0  # negative control: no lock, no denial
