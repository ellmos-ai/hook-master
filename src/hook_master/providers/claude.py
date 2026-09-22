"""Claude-Code-Provider: erzeugt die Hook-Konfiguration als Dict/JSON.

Installation ist ein dokumentierter manueller Schritt -- hook_snippet() liefert
den Baustein fuer settings.json.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseProvider

FORBIDDEN_DEFAULT_EVENT = "PreToolUse"


class ClaudeProvider(BaseProvider):
    name = "claude"
    events = ("SessionStart", "UserPromptSubmit")
    forbidden_events = (FORBIDDEN_DEFAULT_EVENT,)

    def is_available(self) -> bool:
        return True

    def format_hook(self, event: str, command: str, matcher: str | None = None) -> dict[str, Any]:
        hook_obj = {"type": "command", "command": command}
        entry: dict[str, Any] = {"hooks": [hook_obj]}
        if matcher:
            entry["matcher"] = matcher
        return entry

    def hook_snippet(
        self,
        python_executable: str = "python",
        module: str = "hook-master",
        events: tuple[str, ...] | None = None,
        provider_arg: bool = False,
    ) -> dict[str, Any]:
        self.validate_command(python_executable)
        target_events = events or self.events
        hooks_dict: dict[str, list[dict[str, Any]]] = {}
        for event in target_events:
            cmd = f"{python_executable} -m {module} hook-run {event}"
            if provider_arg:
                cmd += " --provider claude"
            hooks_dict[event] = [self.format_hook(event, cmd)]
        for forbidden in self.forbidden_events:
            assert forbidden not in hooks_dict, (
                f"ClaudeProvider darf niemals {forbidden}-Hooks erzeugen (README-Kernregel)."
            )
        return {"hooks": hooks_dict}

    def pretooluse_blocker_snippet(
        self,
        python_executable: str = "python",
        module: str = "workflowhooker",
        matcher: str = "Edit|Write|MultiEdit|NotebookEdit",
        provider_arg: bool = True,
    ) -> dict[str, Any]:
        self.validate_command(python_executable)
        cmd = f"{python_executable} -m {module} hook-run PreToolUse"
        if provider_arg:
            cmd += " --provider claude"
        return {
            "hooks": {
                "PreToolUse": [self.format_hook("PreToolUse", cmd, matcher=matcher)]
            }
        }

    def script_snippet(
        self,
        script_path: str | Path,
        event: str,
        python_executable: str = "python",
        python_args: list[str] | None = None,
        matcher: str | None = None,
    ) -> dict[str, Any]:
        self.validate_command(python_executable)
        args_str = f" {' '.join(python_args)}" if python_args else ""
        norm_path = str(script_path).replace("\\", "/")
        cmd = f'{python_executable}{args_str} "{norm_path}"'
        return {"hooks": {event: [self.format_hook(event, cmd, matcher=matcher)]}}


__all__ = ["ClaudeProvider", "FORBIDDEN_DEFAULT_EVENT"]
