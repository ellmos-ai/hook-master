"""Antigravity (agy) Provider: erzeugt Hook-Konfiguration als Dict/JSON."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseProvider

FORBIDDEN_DEFAULT_EVENT = "PreToolUse"


class AgyProvider(BaseProvider):
    name = "agy"
    events = ("PreInvocation",)
    forbidden_events = (FORBIDDEN_DEFAULT_EVENT,)

    def is_available(self) -> bool:
        return True

    def format_hook(self, command: str, matcher: str | None = None) -> dict[str, Any]:
        if matcher:
            return {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}
        return {"type": "command", "command": command}

    def script_snippet(
        self,
        script_path: str | Path,
        event: str = "PreInvocation",
        python_executable: str = "python",
        python_args: list[str] | None = None,
        matcher: str | None = None,
        timeout: int | float | None = None,
    ) -> dict[str, Any]:
        self.validate_command(python_executable, timeout)
        args_str = f" {' '.join(python_args)}" if python_args else ""
        norm_path = str(script_path).replace("\\", "/")
        cmd = f'{python_executable}{args_str} "{norm_path}"'
        return {"hooks": {event: [self.format_hook(cmd, matcher=matcher)]}}


__all__ = ["AgyProvider", "FORBIDDEN_DEFAULT_EVENT"]
