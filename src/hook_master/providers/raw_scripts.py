"""Registrierungs-Definitionen fuer kanonische Roh-Skripte aus library/."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .agy import AgyProvider
from .claude import ClaudeProvider
from .codex import CodexProvider
from .invariants import validate_interpreter, validate_timeout
from .kimi import KimiProvider

CANONICAL_SCRIPTS: dict[str, dict[str, Any]] = {
    "guards": {
        "filename": "guards.py",
        "default_event": "PreToolUse",
        "python_args": ["-S", "-X", "utf8"],
        "timeout": 10,
        "matchers": {
            "claude": "Edit|Write|MultiEdit|NotebookEdit",
            "codex": "^apply_patch$",
            "kimi": "WriteFile|StrReplaceFile|DeleteFile|MoveFile",
            "agy": "Edit|Write|MultiEdit|NotebookEdit",
        },
        "status_message": "guards: pre-tool safety check",
    },
    # Lebt in lock-master (plugin/lock_guard.py), nicht in library/: --script ist Pflicht. Der Guard liest das
    # Tool-Payload selbst (Edit/Write/MultiEdit/NotebookEdit, Codex apply_patch, Kimi WriteFile/StrReplaceFile/
    # DeleteFile/MoveFile, dazu `git push` ueber Bash bei Claude und Codex) und lehnt ab, wenn ein fremder Lock
    # oder ein fremder Team-Brett-Claim das Ziel abdeckt. Ablehnung: Claude JSON, Codex/Kimi Exit 2 + stderr
    # (--actor waehlt den Vertrag). agy hat kein Tool-Ereignis: siehe "unsupported".
    "lock_guard": {
        "filename": "lock_guard.py",
        "external": "lock-master: plugin/lock_guard.py",
        "default_event": "PreToolUse",
        "python_args": ["-X", "utf8"],
        "script_args": ["pretooluse"],
        "actors": {"claude": "claude-code", "codex": "codex", "kimi": "kimi"},
        "timeout": 10,
        "matchers": {
            "claude": "Edit|Write|MultiEdit|NotebookEdit|Bash",
            "codex": "^(apply_patch|Bash)$",
            "kimi": "WriteFile|StrReplaceFile|DeleteFile|MoveFile",
        },
        "unsupported": {
            "agy": "agy kennt nur das Ereignis PreInvocation (vor dem Modellaufruf, ohne Tool-Ziel); "
            "ein Lock-Check pro Datei ist dort nicht moeglich",
        },
        "status_message": "lock-master: lock check",
    },
    "token_budget_guard": {
        "filename": "token_budget_guard.py",
        "default_event": "UserPromptSubmit",
        "agy_event": "PreInvocation",
        "python_args": ["-X", "utf8"],
        "timeout": 10,
        "matchers": {},
        "status_message": "token_budget_guard: prompt budget check",
    },
    "notaus_wake_check": {
        "filename": "notaus_wake_check.py",
        "default_event": "SessionStart",
        "agy_event": "PreInvocation",
        "python_args": ["-X", "utf8"],
        "timeout": 10,
        "matchers": {},
        "status_message": "notaus_wake_check: session start check",
    },
}

# Aliasse fuer Registry-IDs mit Bindestrich
_SCRIPT_ALIASES = {
    "lock-guard": "lock_guard",
    "token-budget-guard": "token_budget_guard",
    "notaus-wake-check": "notaus_wake_check",
}


def resolve_canonical_script(name_or_id: str) -> dict[str, Any]:
    key = _SCRIPT_ALIASES.get(name_or_id, name_or_id)
    if key not in CANONICAL_SCRIPTS:
        raise KeyError(
            f"Unbekanntes kanonisches Skript: '{name_or_id}'. "
            f"Bekannt: {sorted(list(CANONICAL_SCRIPTS.keys()) + list(_SCRIPT_ALIASES.keys()))}"
        )
    return dict(CANONICAL_SCRIPTS[key])


def format_raw_script_snippet(
    script_name_or_id: str,
    provider_name: str,
    script_path: str | Path | None = None,
    python_executable: str = "python",
    event_override: str | None = None,
    timeout_override: int | None = None,
) -> dict[str, Any]:
    """Erzeugt einen validierten Hook-Snippet fuer eines der kanonischen Roh-Skripte
    guards.py / token_budget_guard.py / notaus_wake_check.py oder fuer den lock-master-Guard
    (lock_guard, Skript liegt in lock-master: script_path ist dort Pflicht).
    """
    spec = resolve_canonical_script(script_name_or_id)
    provider_key = provider_name.lower().strip()
    if provider_key in spec.get("unsupported", {}):
        raise ValueError(
            f"'{script_name_or_id}' ist fuer Provider '{provider_key}' nicht moeglich: "
            f"{spec['unsupported'][provider_key]}"
        )
    if spec.get("external") and not script_path:
        raise ValueError(
            f"'{script_name_or_id}' liegt nicht in library/ ({spec['external']}): "
            "script_path (--script) ist Pflicht."
        )

    validate_interpreter(python_executable)

    timeout = timeout_override or spec["timeout"]
    validate_timeout(timeout)

    resolved_path = (
        Path(script_path)
        if script_path
        else Path(__file__).resolve().parents[3] / "library" / spec["filename"]
    )
    norm_path = str(resolved_path).replace("\\", "/")

    event = event_override or (
        spec.get("agy_event", spec["default_event"])
        if provider_key == "agy"
        else spec["default_event"]
    )
    matcher = spec["matchers"].get(provider_key)
    python_args = spec.get("python_args")
    status_msg = spec.get("status_message")
    script_args = list(spec.get("script_args", ()))
    if spec.get("actors"):
        if provider_key not in spec["actors"]:
            raise ValueError(
                f"Provider '{provider_name}' unterstuetzt keine automatische Snippet-Erzeugung fuer Skripte."
            )
        script_args += ["--actor", spec["actors"][provider_key]]
    script_args = script_args or None

    if provider_key == "claude":
        provider_claude = ClaudeProvider()
        return provider_claude.script_snippet(
            norm_path,
            event=event,
            python_executable=python_executable,
            python_args=python_args,
            matcher=matcher,
            script_args=script_args,
        )
    elif provider_key == "codex":
        provider_codex = CodexProvider()
        return provider_codex.script_snippet(
            norm_path,
            event=event,
            python_executable=python_executable,
            python_args=python_args,
            matcher=matcher,
            timeout=timeout,
            status_message=status_msg,
            script_args=script_args,
        )
    elif provider_key == "kimi":
        provider_kimi = KimiProvider()
        return provider_kimi.script_snippet(
            norm_path,
            event=event,
            python_executable=python_executable,
            python_args=python_args,
            matcher=matcher,
            timeout=timeout,
            script_args=script_args,
        )
    elif provider_key == "agy":
        provider_agy = AgyProvider()
        return provider_agy.script_snippet(
            norm_path,
            event=event,
            python_executable=python_executable,
            python_args=python_args,
            matcher=matcher,
            timeout=timeout,
        )
    else:
        raise ValueError(
            f"Provider '{provider_name}' unterstuetzt keine automatische Snippet-Erzeugung fuer Skripte."
        )


__all__ = [
    "CANONICAL_SCRIPTS",
    "format_raw_script_snippet",
    "resolve_canonical_script",
]
