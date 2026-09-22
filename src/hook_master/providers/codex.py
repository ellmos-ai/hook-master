"""Codex-CLI-Provider fuer ~/.codex/hooks.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseProvider
from .invariants import validate_timeout

FORBIDDEN_DEFAULT_EVENT = "PreToolUse"


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
            "commandWindows": command,
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
    ) -> dict[str, Any]:
        self.validate_command(python_executable, timeout)
        args_str = f" {' '.join(python_args)}" if python_args else ""
        norm_path = str(script_path).replace("\\", "/")
        cmd = f'{python_executable}{args_str} "{norm_path}"'
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


__all__ = ["CodexProvider", "FORBIDDEN_DEFAULT_EVENT"]
