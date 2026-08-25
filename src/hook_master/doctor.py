"""Hook-Doctor (HE2, T-20260825-519184830). Konzept-Nachbau nach dem
Hermes-Agent-Muster (analog `kimi doctor`), NICHT Code-Uebernahme -- Quelle:
T-20260825-152496601 (SOLVED).

Geht ueber registry.verify()/materialize.diff() hinaus: prueft zusaetzlich
Ausfuehrbarkeit (py_compile), mtime-Drift (materialisierte Kopie novher als
kanonische Quelle -> jemand hat direkt an der Kopie gearbeitet, ohne den
kanonischen Weg zu nehmen), JSON/TOML-Validitaet der Ziel-Configs und
Consent-Status. Fuer `kind=consumer`-Eintraege (memoryhooker/workflowhooker)
bewusst NUR Registrier-Integritaet -- es gibt dort kein kanonisches Skript,
also auch keinen Hash-/Exec-/mtime-Check zu tun.

Schweregrade: ok < warning < error. Exit-Code: 0 sauber, 1 nur Warnungen,
2 mindestens ein harter Fehler.
"""

from __future__ import annotations

import json
import py_compile
import time
from pathlib import Path
from typing import Any

from .consent import ConsentStore
from .model import expand_uri, sha256_file
from .registry import HookRegistry

_SEVERITY_ORDER = {"ok": 0, "warning": 1, "error": 2}


def _extract_config_path(config_path_field: str) -> Path | None:
    """`config_path` traegt oft einen erklaerenden Klammerzusatz (z. B.
    '~/.claude/settings.json (hooks.SessionStart)') -- den fuehrenden Pfad
    isolieren, bevor Existenz/Validitaet geprueft wird. Freitext-Platzhalter
    wie 'n/a (...)' liefern bewusst None (nichts zu pruefen, kein Fehler)."""
    raw = config_path_field.split(" (", 1)[0].strip()
    if not raw or raw in {"-", "n/a"} or raw.startswith("n/a"):
        return None
    return expand_uri(raw)


def _check_config_file(path: Path) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"path": str(path), "state": "missing"}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"path": str(path), "state": "unreadable", "error": str(exc)}
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            json.loads(text)
        elif suffix == ".toml":
            try:
                import tomllib  # Python 3.11+
            except ModuleNotFoundError:
                import tomli as tomllib  # type: ignore[no-redef]
            tomllib.loads(text)
        # anderes Format (z.B. .sh) -- nur Existenz+Lesbarkeit zaehlen hier.
        return {"path": str(path), "state": "valid"}
    except Exception as exc:  # noqa: BLE001 -- Parser-Fehler jeder Art melden, nicht crashen
        return {"path": str(path), "state": "invalid", "error": str(exc)}


def _check_executable(path: Path) -> dict[str, Any]:
    if path.suffix.lower() != ".py":
        return {"state": "skipped-not-python"}
    try:
        py_compile.compile(str(path), doraise=True)
        return {"state": "ok"}
    except py_compile.PyCompileError as exc:
        return {"state": "syntax-error", "error": str(exc)}


def check_entry(entry: dict[str, Any], *, consent: ConsentStore, timing: bool = False) -> dict[str, Any]:
    entry_id = entry["id"]
    source = entry["source"]
    findings: list[dict[str, Any]] = []
    severity = "ok"

    def bump(level: str) -> None:
        nonlocal severity
        if _SEVERITY_ORDER[level] > _SEVERITY_ORDER[severity]:
            severity = level

    # Config-Integritaet gilt fuer JEDEN Eintragstyp (auch kind=consumer).
    for target in entry.get("targets", []):
        cfg_path = _extract_config_path(target.get("config_path", ""))
        if cfg_path is None:
            continue
        result = _check_config_file(cfg_path)
        result.update({"check": "config", "agent": target["agent"]})
        if result["state"] in {"missing", "unreadable", "invalid"}:
            bump("error")
        findings.append(result)

    if entry["kind"] == "hook" and source["kind"] == "canonical":
        canonical = expand_uri(source["uri"])
        if canonical is None or not canonical.exists():
            findings.append({"check": "canonical", "state": "missing"})
            bump("error")
        else:
            actual_hash = sha256_file(canonical)
            expected_hash = source["hash"]["value"]
            hash_ok = actual_hash == expected_hash
            findings.append({"check": "canonical-hash", "state": "ok" if hash_ok else "mismatch"})
            if not hash_ok:
                bump("error")

            exec_result = _check_executable(canonical)
            findings.append({"check": "executable", **exec_result})
            if exec_result["state"] == "syntax-error":
                bump("error")

            if timing:
                started = time.perf_counter()
                py_compile.compile(str(canonical), doraise=False)
                findings.append({"check": "timing", "compile_seconds": round(time.perf_counter() - started, 4)})

            for target in entry.get("targets", []):
                deploy_path = target.get("deploy_path")
                if not deploy_path:
                    continue
                deployed = expand_uri(deploy_path)
                row: dict[str, Any] = {"check": "materialization", "agent": target["agent"], "deploy_path": str(deployed)}
                if deployed is None or not deployed.exists():
                    row["state"] = "not-deployed"
                    bump("warning")
                else:
                    deployed_hash = sha256_file(deployed)
                    row["state"] = "in-sync" if deployed_hash == actual_hash else "drifted"
                    if row["state"] == "drifted":
                        bump("warning")
                        # mtime-Drift ist nur bei tatsaechlichem Hash-Unterschied
                        # ein Signal ("jemand hat die deployte Kopie direkt
                        # bearbeitet") -- bei in-sync ist eine neuere
                        # deployed-mtime bloss der letzte deploy()-Lauf selbst,
                        # kein Befund (sonst false positive bei JEDEM Erst-Deploy).
                        if deployed.stat().st_mtime > canonical.stat().st_mtime:
                            row["mtime_drift"] = "deployed ist neuer als canonical -- lokale Aenderung nicht eingesammelt"
                findings.append(row)

        consented = consent.is_consented(entry_id)
        findings.append({"check": "consent", "state": "consented" if consented else "pending-consent"})
        if not consented:
            bump("warning")

    return {"id": entry_id, "kind": entry["kind"], "severity": severity, "findings": findings}


def run(
    registry: HookRegistry,
    *,
    entry_id: str | None = None,
    timing: bool = False,
    consent: ConsentStore | None = None,
) -> dict[str, Any]:
    consent = consent or ConsentStore()
    entries = registry.load()["entries"]
    if entry_id:
        entries = [e for e in entries if e["id"] == entry_id]
    reports = [check_entry(entry, consent=consent, timing=timing) for entry in entries]
    has_error = any(r["severity"] == "error" for r in reports)
    has_warning = any(r["severity"] == "warning" for r in reports)
    exit_code = 2 if has_error else (1 if has_warning else 0)
    return {"registry": str(registry.path), "entries": reports, "exit_code": exit_code}


__all__ = ["check_entry", "run"]
