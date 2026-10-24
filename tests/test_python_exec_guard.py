"""Representative Codex Bash and unified-exec payloads; no script is executed."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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
        "&C:\\work\\scan.py",
        '&"C:\\work dir\\scan.py"',
        "C:\\tools\\lock_scan.py --json",
        'Start-Process -FilePath "C:\\my tools\\lock_scan.py" -Wait',
        "Start-Process -FilePath:C:\\work\\scan.py -Wait",
        'Start-Process -FilePath:"C:\\work dir\\scan.py" -Wait',
        "Start-Process -Wait 'C:\\work\\scan.py'",
        "Start-Process -NoNewWindow 'C:\\work\\scan.py'",
        "saps -Wait 'C:\\work\\scan.py'",
        "Start-Process -WindowStyle Hidden -Wait 'C:\\work\\scan.py'",
        "Invoke-Item 'C:\\my tools\\lock_scan.py'",
        "Invoke-Item -LiteralPath:C:\\work\\scan.py",
        "Invoke-Item -LiteralPath:'C:\\work dir\\scan.py'",
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
        ["Start-Process", "-FilePath:C:\\work\\scan.py", "-Wait"],
        ["Start-Process", '-FilePath:"C:\\work dir\\scan.py"', "-Wait"],
        ["Invoke-Item", "-LiteralPath:C:\\work\\scan.py"],
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
        "# explanation; &C:\\work\\scan.py",
        "Write-Output done # explanation; &C:\\work\\scan.py",
        'Write-Output "&C:\\work\\scan.py"',
        "Set-Content -LiteralPath fixture.txt -Value @'\n& C:\\work\\scan.py\n'@",
        'Set-Content -LiteralPath fixture.txt -Value @"\n& "C:\\work dir\\scan.py"\n"@',
        "Start-Process -ArgumentList 'C:\\work\\scan.py' -Wait python.exe",
        "Get-Content C:\\tools\\lock_scan.py",
    ]
    for command in allowed:
        assert not guard.blocking_reason(payload(command)), command
    assert not guard.blocking_reason(payload(["python.exe", "C:\\tools\\lock_scan.py"]))
    assert guard.blocking_reason(payload(
        "Set-Content -Value @'\n& C:\\work\\scan.py\n'@; &C:\\work\\scan.py"
    ))


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


def test_windows_powershell_ast_syntax_oracle(tmp_path):
    """Parse only: no sample command is ever executed by PowerShell."""
    pwsh = shutil.which("pwsh")
    if not pwsh:
        pytest.skip("PowerShell AST unavailable on this runner")
    cases = [
        {"label": "amp", "code": r"&C:\work\scan.py"},
        {"label": "amp_quoted", "code": r'&"C:\work dir\scan.py"'},
        {"label": "start_colon", "code": r"Start-Process -FilePath:C:\work\scan.py -Wait"},
        {"label": "start_quoted", "code": r'Start-Process -FilePath:"C:\work dir\scan.py" -Wait'},
        {"label": "invoke_colon", "code": r"Invoke-Item -LiteralPath:C:\work\scan.py"},
        {"label": "comment", "code": r"# explanation; &C:\work\scan.py"},
        {"label": "here_string", "code": "Set-Content -LiteralPath fixture.txt -Value @'\n& C:\\work\\scan.py\n'@"},
        {"label": "literal", "code": r'Write-Output "&C:\work\scan.py"'},
        {"label": "invalid", "code": "&"},
    ]
    probe = tmp_path / "parse-only.ps1"
    probe.write_text(
        "$cases = $env:PY_GUARD_AST_CASES | ConvertFrom-Json\n"
        "foreach ($item in $cases) {\n"
        "  $tokens = $null; $errors = $null\n"
        "  $tree = [System.Management.Automation.Language.Parser]::ParseInput("
        "$item.code, [ref]$tokens, [ref]$errors)\n"
        "  $commands = @($tree.FindAll({param($n) "
        "$n -is [System.Management.Automation.Language.CommandAst]}, $true))\n"
        "  [pscustomobject]@{label=$item.label; errors=@($errors).Count; "
        "names=@($commands | ForEach-Object {$_.GetCommandName()}); "
        "invocations=@($commands | ForEach-Object {$_.InvocationOperator.ToString()}); "
        "parameters=@($commands | ForEach-Object {$_.CommandElements | "
        "Where-Object {$_ -is [System.Management.Automation.Language.CommandParameterAst]} | "
        "ForEach-Object {$_.ParameterName}})} | ConvertTo-Json -Compress\n"
        "}\n",
        encoding="utf-8",
    )
    environment = dict(os.environ, PY_GUARD_AST_CASES=json.dumps(cases))
    result = subprocess.run(
        [pwsh, "-NoProfile", "-File", str(probe)],
        capture_output=True, text=True, encoding="utf-8", env=environment,
        check=False, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    observed = {row["label"]: row for row in map(json.loads, result.stdout.splitlines())}
    for label in ("amp", "amp_quoted", "start_colon", "start_quoted", "invoke_colon"):
        assert observed[label]["errors"] == 0, label
    assert observed["amp"]["invocations"] == ["Ampersand"]
    assert observed["amp_quoted"]["invocations"] == ["Ampersand"]
    assert observed["start_colon"]["parameters"] == ["FilePath", "Wait"]
    assert observed["start_quoted"]["parameters"] == ["FilePath", "Wait"]
    assert observed["invoke_colon"]["parameters"] == ["LiteralPath"]
    assert observed["comment"]["names"] == []
    assert observed["here_string"]["errors"] == 0
    assert observed["here_string"]["names"] == ["Set-Content"]
    assert observed["literal"]["names"] == ["Write-Output"]
    assert observed["invalid"]["errors"] > 0
