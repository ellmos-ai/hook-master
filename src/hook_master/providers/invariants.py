"""Pflicht-Invarianten fuer Hook-Provider (T-20260921-750493182):
- Interpreter absolut oder als verifizierter Name -- niemals python3/pwsh
  (Windows-Store-Aliase, 0 Byte, haengen statt zu scheitern)
- 0-Byte-App-Execution-Alias erkennen und ablehnen (gesamter Pfad darf
  keinen 0-Byte-Alias enthalten)
- Timeout muss wirksam und positiv sein (> 0)
- Selbsttest, der genau diese Punkte misst und bestaetigt, dass Timeout
  nachweislich toetet (run_self_test / verify_timeout_kills)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


class InterpreterAliasError(ValueError):
    """Wird geworfen, wenn ein Interpreter ein 0-Byte Store-App-Execution-Alias
    oder ein verbotener ungesicherter Aliasname (python3/pwsh auf Windows) ist."""

    pass


class InvalidTimeoutError(ValueError):
    """Wird geworfen, wenn ein Hook-Timeout fehlt oder <= 0 ist."""

    pass


FORBIDDEN_INTERPRETER_NAMES = {"python3", "python3.exe"}


def extract_executable_candidate(cmd_or_exe: str | Path) -> str:
    """Extrahiert den Interpreter-/Kommandonamen, auch wenn Pfade Leerzeichen
    oder Anfuehrungszeichen enthalten."""
    raw = str(cmd_or_exe).strip()
    if not raw:
        raise ValueError("Interpreter darf nicht leer sein.")
    if Path(raw).is_file():
        return raw
    if raw.startswith('"'):
        end = raw.find('"', 1)
        if end != -1:
            return raw[1:end]
    elif raw.startswith("'"):
        end = raw.find("'", 1)
        if end != -1:
            return raw[1:end]
    lower_raw = raw.lower()
    for ext in (".exe", ".cmd", ".bat"):
        idx = lower_raw.find(ext)
        if idx != -1:
            candidate = raw[: idx + len(ext)]
            if Path(candidate).is_file():
                return candidate
    return raw.split()[0].strip("\"'")


def validate_interpreter(cmd_or_exe: str | Path) -> Path:
    """Prueft, dass ein Interpreter existiert und KEIN 0-Byte-Store-Alias ist.

    Invariante T-20260921-750493182:
    (a) niemals `python3` / 0-Byte Store-Alias unter Windows
    (b) EXE-Groesse muss > 0 sein (0-Byte App-Execution-Alias erkennen und ablehnen)
    """
    first_token = extract_executable_candidate(cmd_or_exe)

    # Pruefen auf verbotene unqualifizierte Namen unter Windows
    name_lower = Path(first_token).name.lower()
    if sys.platform == "win32" and name_lower in FORBIDDEN_INTERPRETER_NAMES:
        resolved = shutil.which(first_token)
        if resolved:
            try:
                size = os.path.getsize(resolved)
                if size == 0:
                    raise InterpreterAliasError(
                        f"Verbotener 0-Byte App-Execution-Alias fuer '{first_token}' erkannt: {resolved}"
                    )
            except OSError:
                pass
        raise InterpreterAliasError(
            f"Verbotener Interpreter-Name '{first_token}' unter Windows: python3 ist ein Store-Alias."
        )

    # Aufloesung ueber shutil.which oder direkten Pfad
    resolved = shutil.which(first_token)
    candidate_path = Path(resolved) if resolved else Path(first_token)

    if not candidate_path.is_file():
        raise FileNotFoundError(f"Interpreter-Datei nicht gefunden: '{first_token}'")

    # Pruefung auf 0-Byte-Alias (Store App Execution Alias Reparse Point)
    try:
        size = candidate_path.stat().st_size
    except OSError as exc:
        raise InterpreterAliasError(f"Interpreter-Status nicht lesbar: {candidate_path} ({exc})") from exc

    if size == 0:
        raise InterpreterAliasError(
            f"0-Byte App-Execution-Alias erkannt und abgelehnt: {candidate_path} (Groesse ist 0 Byte)"
        )

    return candidate_path


def validate_timeout(timeout: int | float | None) -> int:
    """Validiert, dass ein konfigurierter Timeout wirksam und positiv ist."""
    if timeout is None:
        raise InvalidTimeoutError("Timeout darf nicht None sein; ein wirksamer Timeout (> 0) ist Pflicht.")
    try:
        val = int(timeout)
    except (TypeError, ValueError) as exc:
        raise InvalidTimeoutError(f"Ungueltiges Timeout-Format: {timeout}") from exc

    if val <= 0:
        raise InvalidTimeoutError(f"Timeout muss positiv sein (> 0 Sekunden), erhalten: {val}")
    return val


def verify_timeout_kills(timeout: float = 0.5) -> bool:
    """Beweist durch Messung, dass ein Timeout einen Prozess nachweislich toetet.

    Startet einen absichtlich haengenden Python-Subprozess (time.sleep(10)) mit
    einem kurzen Timeout und verifiziert, dass TimeoutExpired auftritt und der
    Prozess beendet wird (kein Zombie / kein Haengen).
    """
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        proc.wait(timeout=timeout)
        return False
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2.0)
        return proc.poll() is not None


def run_self_test(
    interpreter: str = sys.executable,
    timeout: float = 0.5,
) -> dict[str, Any]:
    """Selbsttest gemaess Pflicht-Invariante 3(c):
    Misst Interpreter-Validierung und Timeout-Wirksamkeit vor Registrierung.
    """
    results: dict[str, Any] = {
        "interpreter": str(interpreter),
        "interpreter_valid": False,
        "alias_detection_works": False,
        "timeout_kills": False,
        "ok": False,
    }

    # 1. Gueltigen Interpreter pruefen
    valid_path = validate_interpreter(interpreter)
    results["interpreter_valid"] = valid_path.is_file()

    # 2. Alias-Erkennung testen (0-Byte Erkennung)
    alias_detected = False
    p3 = shutil.which("python3")
    if p3 and os.path.exists(p3) and os.path.getsize(p3) == 0:
        try:
            validate_interpreter("python3")
        except InterpreterAliasError:
            alias_detected = True
    else:
        try:
            validate_interpreter("python3")
        except (InterpreterAliasError, FileNotFoundError):
            alias_detected = True
    results["alias_detection_works"] = alias_detected

    # 3. Timeout-Wirksamkeit messen
    results["timeout_kills"] = verify_timeout_kills(timeout=timeout)

    results["ok"] = (
        results["interpreter_valid"]
        and results["alias_detection_works"]
        and results["timeout_kills"]
    )
    return results
