"""Gemeinsame Provider-Adapter-Schicht fuer Agent-Hooks (T-20260921-750493182).

Vereinheitlicht die Provider-Registrierungs-Formate (claude/codex/kimi/agy)
als gemeinsame Schicht in hook-master, ueber die sowohl Domaenenmodule
(memoryhooker, workflowhooker) als auch kanonische Roh-Skripte (guards.py,
token_budget_guard.py, notaus_wake_check.py) registriert werden.
"""

from __future__ import annotations

from typing import Any

from .agy import AgyProvider
from .base import (
    BaseProvider,
    InterpreterAliasError,
    InvalidTimeoutError,
    ManualProvider,
    Provider,
    UnimplementedProvider,
    validate_interpreter,
    validate_timeout,
)
from .claude import ClaudeProvider
from .codex import CodexProvider
from .git import GitProvider
from .invariants import run_self_test, verify_timeout_kills
from .kimi import KimiProvider
from .raw_scripts import (
    CANONICAL_SCRIPTS,
    format_raw_script_snippet,
    resolve_canonical_script,
)

PROVIDER_REGISTRY: dict[str, Provider] = {
    "claude": ClaudeProvider(),
    "codex": CodexProvider(),
    "git": GitProvider(),
    "manual": ManualProvider(),
    "kimi": KimiProvider(),
    "agy": AgyProvider(),
}


def resolve_provider(
    order: list[str] | Any = None,
    registry: dict[str, Provider] | None = None,
) -> Provider:
    """Erster verfuegbarer Provider in der Reihenfolge gewinnt (Fallback-Kette)."""
    reg = registry or PROVIDER_REGISTRY
    order_list = getattr(order, "order", order)
    if not order_list:
        order_list = ["claude", "codex", "kimi", "agy", "git", "manual"]
    for name in order_list:
        provider = reg.get(name)
        if provider is not None and provider.is_available():
            return provider
    return reg.get("manual", ManualProvider())


__all__ = [
    "CANONICAL_SCRIPTS",
    "PROVIDER_REGISTRY",
    "AgyProvider",
    "BaseProvider",
    "ClaudeProvider",
    "CodexProvider",
    "GitProvider",
    "InterpreterAliasError",
    "InvalidTimeoutError",
    "KimiProvider",
    "ManualProvider",
    "Provider",
    "UnimplementedProvider",
    "format_raw_script_snippet",
    "resolve_canonical_script",
    "resolve_provider",
    "run_self_test",
    "validate_interpreter",
    "validate_timeout",
    "verify_timeout_kills",
]
