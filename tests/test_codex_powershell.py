"""Regression: Codex commands must invoke quoted executables in PowerShell and keep their exit code."""
import json
import shutil
import subprocess
import sys

import pytest

from hook_master.providers.codex import (
    EXIT_CODE_PREFIX,
    EXIT_CODE_SUFFIX,
    CodexProvider,
    powershell_command,
)


def wrapped(command: str) -> str:
    return EXIT_CODE_PREFIX + command + EXIT_CODE_SUFFIX


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
    assert handler["commandWindows"] == wrapped("& " + handler["command"])


@pytest.mark.parametrize("command", ["python -m probe", '& "python.exe" -m probe', "echo 'done'"])
def test_existing_commands_are_preserved_inside_the_exit_code_wrapper(command):
    handler = CodexProvider().format_hook("SessionStart", command)["hooks"][0]
    assert handler["commandWindows"] == wrapped(command)


def test_wrapping_is_idempotent():
    once = powershell_command('"python.exe" -m probe')
    assert powershell_command(once) == once


def _powershell(shell: str) -> str:
    executable = shutil.which(shell)
    if not executable:
        pytest.skip(f"{shell} is not available")
    return executable


def _run(executable: str, command: str, stdin: str = "{}") -> subprocess.CompletedProcess:
    return subprocess.run(
        [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        input=stdin, capture_output=True, text=True, timeout=30,
    )


@pytest.mark.parametrize("shell", ["pwsh", "powershell"])
def test_generated_script_runs_in_powershell_with_json_stdin(tmp_path, shell):
    executable = _powershell(shell)
    script = tmp_path / "hook script.py"
    script.write_text("import sys,json; print(json.dumps(json.load(sys.stdin)))", encoding="utf-8")
    handler = CodexProvider().script_snippet(
        script, "SessionStart", python_executable=f'"{sys.executable}"'
    )["hooks"]["SessionStart"][0]["hooks"][0]
    result = _run(executable, handler["commandWindows"], '{"source":"compact"}')
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout) == {"source": "compact"}


@pytest.mark.parametrize("shell", ["pwsh", "powershell"])
@pytest.mark.parametrize("code", [0, 1, 2, 3])
def test_powershell_keeps_the_native_exit_code(tmp_path, shell, code):
    # Without the wrapper `pwsh -Command` turns exit 2 into 1, and Codex runs a blocked tool call.
    executable = _powershell(shell)
    script = tmp_path / "guard script.py"
    script.write_text(
        f"import sys\nsys.stdin.read()\nprint('GUARD: reason', file=sys.stderr)\nsys.exit({code})\n",
        encoding="utf-8",
    )
    handler = CodexProvider().script_snippet(
        script, "PreToolUse", python_executable=f'"{sys.executable}"', matcher="^shell_command$"
    )["hooks"]["PreToolUse"][0]["hooks"][0]
    result = _run(executable, handler["commandWindows"])
    assert result.returncode == code, result.stderr
    assert "GUARD: reason" in result.stderr


@pytest.mark.parametrize("shell", ["pwsh", "powershell"])
def test_failing_powershell_expression_still_exits_nonzero(shell):
    executable = _powershell(shell)
    command = powershell_command("Get-Item -LiteralPath 'Z:/hook-master/does/not/exist' -ErrorAction Continue")
    assert _run(executable, command).returncode == 1


def test_unquoted_python_path_with_spaces_is_quoted(tmp_path):
    python = tmp_path / "python directory" / "python.exe"
    python.parent.mkdir()
    python.write_bytes(b"synthetic nonzero interpreter")
    handler = CodexProvider().script_snippet(
        "hook.py", "SessionStart", python_executable=str(python)
    )["hooks"]["SessionStart"][0]["hooks"][0]
    assert handler["command"].startswith(f'"{python}" ')
    assert handler["commandWindows"].startswith(EXIT_CODE_PREFIX + f'& "{python}" ')
