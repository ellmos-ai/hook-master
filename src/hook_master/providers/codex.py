"""Codex-CLI-Provider fuer ~/.codex/hooks.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseProvider
from .invariants import format_script_args, quote_executable, validate_timeout

FORBIDDEN_DEFAULT_EVENT = "PreToolUse"


EXIT_CODE_PREFIX = "$global:LASTEXITCODE = 0; "
EXIT_CODE_SUFFIX = "; $hookOk = $?; if ($LASTEXITCODE) { exit $LASTEXITCODE }; if (-not $hookOk) { exit 1 }"


def powershell_command(command: str) -> str:
    """Build the Codex ``commandWindows`` form of a hook command.

    A leading quoted executable is invoked with ``&``. The command is then
    wrapped so that ``pwsh -Command`` exits with the native exit code:
    without it PowerShell reports every non-zero exit as 1, and Codex treats
    a guard's exit 2 as a failed hook and runs the tool call anyway.
    """
    stripped = command.lstrip()
    if stripped.startswith(EXIT_CODE_PREFIX):
        return command
    invoked = "& " + stripped if stripped.startswith(('"', "'")) else command
    return EXIT_CODE_PREFIX + invoked + EXIT_CODE_SUFFIX


_quote_executable = quote_executable


class CodexProvider(BaseProvider):
    name = "codex"
    events = ("SessionStart", "UserPromptSubmit")
    forbidden_events = (FORBIDDEN_DEFAULT_EVENT,)

    def is_available(self) -> bool:
        return True

    def format_hook(
        self,
        event: str,
        command: str,
        timeout: int = 10,
        status_message: str | None = None,
        matcher: str | None = None,
    ) -> dict[str, Any]:
        validate_timeout(timeout)
        hook_obj: dict[str, Any] = {
            "type": "command",
            "command": command,
            "commandWindows": powershell_command(command),
            "timeout": timeout,
        }
        if status_message:
            hook_obj["statusMessage"] = status_message
        entry: dict[str, Any] = {"hooks": [hook_obj]}
        if matcher:
            entry["matcher"] = matcher
        return entry

    def hook_snippet(
        self,
        python_executable: str = "python",
        module: str = "hook-master",
        events: tuple[str, ...] | None = None,
        timeout: int = 10,
        status_prefix: str | None = None,
        provider_arg: bool = False,
    ) -> dict[str, Any]:
        self.validate_command(python_executable, timeout)
        python_executable = _quote_executable(python_executable)
        target_events = events or self.events
        hooks_dict: dict[str, list[dict[str, Any]]] = {}
        for event in target_events:
            cmd = f"{python_executable} -m {module} hook-run {event}"
            if provider_arg:
                cmd += " --provider codex"
            status_msg = f"{status_prefix}: {event}" if status_prefix else None
            hooks_dict[event] = [
                self.format_hook(event, cmd, timeout=timeout, status_message=status_msg)
            ]
        for forbidden in self.forbidden_events:
            assert forbidden not in hooks_dict
        return {"hooks": hooks_dict}

    def pretooluse_blocker_snippet(
        self,
        python_executable: str = "python",
        module: str = "workflowhooker",
        matcher: str = "^apply_patch$",
        timeout: int = 10,
        status_message: str = "WorkflowHooker: action guard",
        provider_arg: bool = True,
    ) -> dict[str, Any]:
        self.validate_command(python_executable, timeout)
        python_executable = _quote_executable(python_executable)
        cmd = f"{python_executable} -m {module} hook-run PreToolUse"
        if provider_arg:
            cmd += " --provider codex"
        return {
            "hooks": {
                "PreToolUse": [
                    self.format_hook(
                        "PreToolUse",
                        cmd,
                        timeout=timeout,
                        status_message=status_message,
                        matcher=matcher,
                    )
                ]
            }
        }

    def script_snippet(
        self,
        script_path: str | Path,
        event: str,
        python_executable: str = "python",
        python_args: list[str] | None = None,
        matcher: str | None = None,
        timeout: int = 10,
        status_message: str | None = None,
        script_args: list[str] | None = None,
    ) -> dict[str, Any]:
        self.validate_command(python_executable, timeout)
        python_executable = _quote_executable(python_executable)
        args_str = f" {' '.join(python_args)}" if python_args else ""
        norm_path = str(script_path).replace("\\", "/")
        cmd = f'{python_executable}{args_str} "{norm_path}"' + format_script_args(script_args)
        return {
            "hooks": {
                event: [
                    self.format_hook(
                        event,
                        cmd,
                        timeout=timeout,
                        status_message=status_message,
                        matcher=matcher,
                    )
                ]
            }
        }


__all__ = [
    "CodexProvider",
    "EXIT_CODE_PREFIX",
    "EXIT_CODE_SUFFIX",
    "FORBIDDEN_DEFAULT_EVENT",
    "powershell_command",
]
