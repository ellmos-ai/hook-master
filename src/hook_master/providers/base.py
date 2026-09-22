"""Gemeinsames Provider-Protokoll, Basisklassen und Validierung."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from .invariants import (
    InterpreterAliasError,
    InvalidTimeoutError,
    validate_interpreter,
    validate_timeout,
)


@runtime_checkable
class Provider(Protocol):
    name: str

    def is_available(self) -> bool:
        ...


class BaseProvider:
    name: str = "base"
    events: tuple[str, ...] = ()
    forbidden_events: tuple[str, ...] = ()

    def is_available(self) -> bool:
        return True

    def validate_command(
        self,
        python_executable: str = "python",
        timeout: int | float | None = None,
    ) -> Path:
        resolved = validate_interpreter(python_executable)
        if timeout is not None:
            validate_timeout(timeout)
        return resolved


class UnimplementedProvider(BaseProvider):
    """Dokumentierter Stub fuer einen Provider, dessen Hook-Bindung noch
    nicht ermittelt ist (README: 'je Anbieter zu ermitteln, nicht zu raten')."""

    name = "unimplemented"
    reason = "Hook-Bindung fuer diesen Anbieter ist noch nicht ermittelt."

    def is_available(self) -> bool:
        return False


class ManualProvider(BaseProvider):
    """Kein Hook -- stellt nur eine CLI bereit, die der Agent manuell aufruft.
    Immer verfuegbar: garantiert, dass die Provider-Kette nie leerlaeuft."""

    name = "manual"

    def is_available(self) -> bool:
        return True


__all__ = [
    "BaseProvider",
    "InterpreterAliasError",
    "InvalidTimeoutError",
    "ManualProvider",
    "Provider",
    "UnimplementedProvider",
    "validate_interpreter",
    "validate_timeout",
]
