"""Kimi-Code-CLI-Provider fuer ~/.kimi-code/config.toml ([[hooks]])."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseProvider
from .invariants import format_script_args, quote_executable, validate_timeout

FORBIDDEN_DEFAULT_EVENT = "PreToolUse"


class KimiProvider(BaseProvider):
    name = "kimi"
    events = ("UserPromptSubmit",)
    forbidden_events = (FORBIDDEN_DEFAULT_EVENT,)

    def is_available(self) -> bool:
        return (Path.home() / ".kimi-code" / "config.toml").exists()

    def format_hook(
        self,
        event: str,
        command: str,
        timeout: int = 15,
        matcher: str | None = None,
    ) -> dict[str, Any]:
        validate_timeout(timeout)
        entry: dict[str, Any] = {"event": event, "command": command, "timeout": timeout}
        if matcher:
            entry["matcher"] = matcher
        return entry

    def script_snippet(
        self,
        script_path: str | Path,
        event: str,
        python_executable: str = "python",
        python_args: list[str] | None = None,
        matcher: str | None = None,
        timeout: int = 15,
        script_args: list[str] | None = None,
    ) -> dict[str, Any]:
        self.validate_command(python_executable, timeout)
        python_executable = quote_executable(python_executable)
        args_str = f" {' '.join(python_args)}" if python_args else ""
        norm_path = str(script_path).replace("\\", "/")
        cmd = f'{python_executable}{args_str} "{norm_path}"' + format_script_args(script_args)
        return {"hooks": [self.format_hook(event, cmd, timeout=timeout, matcher=matcher)]}


__all__ = ["KimiProvider", "FORBIDDEN_DEFAULT_EVENT"]
