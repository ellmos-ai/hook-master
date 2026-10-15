"""Regression: Codex commands must invoke quoted executables in PowerShell."""
import json
import shutil
import subprocess
import sys

import pytest

from hook_master.providers.codex import CodexProvider


@pytest.mark.parametrize("variant", ["hook", "script", "blocker", "raw"])
def test_quoted_executable_gets_windows_call_operator(variant):
    provider = CodexProvider()
    python = f'"{sys.executable}"'
    if variant == "hook":
        snippet = provider.hook_snippet(python_executable=python)
    elif variant == "script":
        snippet = provider.script_snippet("hook script.py", "SessionStart", python_executable=python)
    elif variant == "blocker":
        snippet = provider.pretooluse_blocker_snippet(python_executable=python)
    else:
        snippet = {"hooks": {"SessionStart": [provider.format_hook("SessionStart", python + ' "hook script.py"')]}}
    handler = next(iter(snippet["hooks"].values()))[0]["hooks"][0]
    assert handler["command"].startswith(python)
    assert handler["commandWindows"] == "& " + handler["command"]


@pytest.mark.parametrize("command", ["python -m probe", '& "python.exe" -m probe', "echo 'done'"])
def test_existing_commands_are_preserved(command):
    handler = CodexProvider().format_hook("SessionStart", command)["hooks"][0]
    assert handler["commandWindows"] == command


@pytest.mark.parametrize("shell", ["pwsh", "powershell"])
def test_generated_script_runs_in_powershell_with_json_stdin(tmp_path, shell):
    executable = shutil.which(shell)
    if not executable:
        pytest.skip(f"{shell} is not available")
    script = tmp_path / "hook script.py"
    script.write_text("import sys,json; print(json.dumps(json.load(sys.stdin)))", encoding="utf-8")
    handler = CodexProvider().script_snippet(
        script, "SessionStart", python_executable=f'"{sys.executable}"'
    )["hooks"]["SessionStart"][0]["hooks"][0]
    result = subprocess.run(
        [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", handler["commandWindows"]],
        input='{"source":"compact"}', capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout) == {"source": "compact"}


def test_unquoted_python_path_with_spaces_is_quoted(tmp_path):
    python = tmp_path / "python directory" / "python.exe"
    python.parent.mkdir()
    python.write_bytes(b"synthetic nonzero interpreter")
    handler = CodexProvider().script_snippet(
        "hook.py", "SessionStart", python_executable=str(python)
    )["hooks"]["SessionStart"][0]["hooks"][0]
    assert handler["command"].startswith(f'"{python}" ')
    assert handler["commandWindows"].startswith(f'& "{python}" ')
