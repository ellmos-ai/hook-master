"""library/lock_edit_guard.py: finds lock-master's lock_guard.py in trusted places and runs it, with no lock logic of its own."""
from __future__ import annotations

import importlib.util
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


def fake_guard(base: Path, code: str) -> Path:
    plugin = base / "plugin"
    plugin.mkdir(parents=True)
    (plugin / "lock_guard.py").write_text(code, encoding="utf-8")
    return base


def home_env(home: Path, **extra) -> dict:
    """An environment whose home is `home` and without an explicit ELLMOS_LOCK_MASTER."""
    return {"HOME": str(home), "USERPROFILE": str(home), "ELLMOS_LOCK_MASTER": "", **extra}


def load_shim():
    spec = importlib.util.spec_from_file_location("lock_edit_guard_under_test", SHIM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_arguments_stdin_and_exit_code_reach_the_guard(tmp_path):
    root = fake_guard(tmp_path / "lock-master", "import sys\nprint(sys.argv[1:], sys.stdin.read())\nsys.exit(2)\n")
    done = run({"ELLMOS_LOCK_MASTER": str(root)}, payload="PAYLOAD")
    assert done.returncode == 2
    assert "['pretooluse', '--actor', 'codex'] PAYLOAD" in done.stdout


def test_env_may_name_the_repo_the_plugin_dir_or_the_file(tmp_path):
    root = fake_guard(tmp_path / "lock-master", "import sys\nsys.exit(3)\n")
    for value in (root, root / "plugin", root / "plugin" / "lock_guard.py"):
        assert run({"ELLMOS_LOCK_MASTER": str(value)}).returncode == 3, value


def test_explicit_location_may_lie_outside_home(tmp_path):
    root = fake_guard(tmp_path / "elsewhere" / "lock-master", "import sys\nsys.exit(3)\n")
    home = tmp_path / "home"
    home.mkdir()
    assert run(home_env(home, ELLMOS_LOCK_MASTER=str(root))).returncode == 3


def test_home_clone_and_plugin_cache_are_found(tmp_path):
    home = tmp_path / "home"
    fake_guard(home / "_Local_DEV" / "repos" / "lock-master", "import sys\nsys.exit(4)\n")
    assert run(home_env(home)).returncode == 4
    cached = home / ".claude" / "plugins" / "cache" / "mkt" / "ellmos-lock-master" / "1.8.0"
    fake_guard(cached, "import sys\nsys.exit(5)\n")
    assert run(home_env(home)).returncode == 5  # the plugin cache wins over the clone


def test_nothing_outside_home_is_searched_without_the_env_variable(tmp_path, monkeypatch):
    """The drive root (C:/_Local_DEV/...) is not a candidate: other accounts can create folders there."""
    shim = load_shim()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("ELLMOS_LOCK_MASTER", raising=False)
    found = shim.candidates()
    assert found, "there must be default locations"
    for path in found:
        path.relative_to(tmp_path)  # raises when a candidate lies outside the home


def test_owned_by_user_refuses_paths_outside_home(tmp_path):
    shim = load_shim()
    home = tmp_path / "home"
    inside = fake_guard(home / "x", "pass\n") / "plugin" / "lock_guard.py"
    outside = fake_guard(tmp_path / "other", "pass\n") / "plugin" / "lock_guard.py"
    assert shim.owned_by_user(inside, home)
    assert not shim.owned_by_user(outside, home)  # negative control


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_group_or_world_writable_location_is_not_executed(tmp_path):
    home = tmp_path / "home"
    root = fake_guard(home / "_Local_DEV" / "repos" / "lock-master", "import sys\nsys.exit(4)\n")
    assert run(home_env(home)).returncode == 4  # negative control: same place, safe permissions
    os.chmod(root / "plugin", 0o777)
    done = run(home_env(home))
    assert done.returncode == 0 and "trusted location" in done.stderr


def test_missing_lock_master_says_so_and_does_not_block(tmp_path):
    done = run(home_env(tmp_path))
    assert done.returncode == 0 and "lock checks are inactive" in done.stderr


def test_real_lock_master_denies_a_foreign_lock_when_present(tmp_path):
    probe = run({}, payload=json.dumps({"tool_name": "Read", "tool_input": {}}))
    if "lock checks are inactive" in probe.stderr:
        pytest.skip("no lock-master in a trusted location on this host (set ELLMOS_LOCK_MASTER)")
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
