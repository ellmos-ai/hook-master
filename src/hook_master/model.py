"""Entry schema for hook-master. Same pointer-only discipline as policy-registry
(registry.model), adapted for a domain where the pointed-to thing is executable
code, not text -- so `source.hash` is not optional-decoration here, it is the
thing `verify()`/`deploy --diff` build on.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

SCHEMA = "ellmos.hook-registry.v1"

# kind=hook: a concrete, materializable script (canonical or externally owned).
# kind=consumer: a registered module that owns its OWN hook-registration format
#   (memoryhooker, workflowhooker) -- hook-master tracks it as a pointer, never
#   as a script to deploy. See ARCHITECTURE-BEFUND in T-20260825-644007692: the
#   consumer's domain logic stays with the consumer, hook-master only catalogues
#   that it exists and which events/agents it covers.
ENTRY_KINDS = {"hook", "consumer"}

# Same event vocabulary already live in ~/.claude/settings.json / ~/.codex/hooks.json
# / ~/.kimi-code/config.toml -- not invented here, just enumerated so validate_entry
# can catch typos instead of silently accepting an event nothing will ever fire.
EVENTS = {
    "PreToolUse", "PostToolUse", "SessionStart", "SessionEnd",
    "UserPromptSubmit", "Stop", "PreCompact", "PostCompact",
    "SubagentStart", "SubagentStop",
    # Nicht event-basiert im engeren Sinn, aber real ein Hook-Anschlusspunkt:
    # Claude Codes `statusLine`-Konfigurationsfeld ruft ein Kommando kontinuierlich
    # auf, kein Lifecycle-Event. Aufgenommen statt es falsch in ein echtes Event
    # zu pressen (token_budget_statusline.py haengt genau hier).
    "StatusLine",
}

# Reused, not reinvented: this is exactly the vocabulary already used in
# .SYNC/hooks/adoption/*.json's `source` field per hook entry.
SOURCE_KINDS = {"canonical", "external-module", "inline", "local-copy", "local-only"}

STATUSES = {"active", "draft", "disabled"}

# Reused from policy-registry.model.ADOPTIONS, +"not-applicable" -- the hook
# adoption files already use this exact word for agents with no hook mechanism
# at all (e.g. antigravity/claude-desktop today).
ADOPTIONS = {"adopted", "partial", "pending", "exempt", "not-applicable"}

AGENTS = {"claude-code", "claude-desktop", "codex", "antigravity", "kimi"}

FORBIDDEN_CONTENT_KEYS = {"content", "body", "full_text", "fulltext", "payload", "script_text"}


class ValidationError(ValueError):
    pass


def expand_uri(uri: str) -> Path | None:
    if uri.startswith(("http://", "https://", "git+")):
        return None
    return Path(os.path.expandvars(os.path.expanduser(uri)))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def validate_entry(entry: dict[str, Any]) -> dict[str, Any]:
    required = {"id", "kind", "title", "event", "source", "targets", "consumers", "status", "adoption"}
    missing = sorted(required - entry.keys())
    if missing:
        raise ValidationError(f"Fehlende Felder: {', '.join(missing)}")
    forbidden = sorted(FORBIDDEN_CONTENT_KEYS & entry.keys())
    if forbidden:
        raise ValidationError(
            "Registry speichert keinen Skript-Volltext; unzulaessige Felder: " + ", ".join(forbidden)
        )

    if entry["kind"] not in ENTRY_KINDS:
        raise ValidationError(f"Unbekannter kind-Wert: {entry['kind']}")
    if entry["event"] not in EVENTS:
        raise ValidationError(f"Unbekannter event-Wert: {entry['event']} (bekannt: {sorted(EVENTS)})")
    if entry["status"] not in STATUSES:
        raise ValidationError(f"Unbekannter status-Wert: {entry['status']}")

    source = entry["source"]
    if not isinstance(source, dict) or source.get("kind") not in SOURCE_KINDS:
        raise ValidationError(f"source.kind fehlt oder unbekannt (erlaubt: {sorted(SOURCE_KINDS)})")
    if FORBIDDEN_CONTENT_KEYS & source.keys():
        raise ValidationError("source darf keinen Skript-Volltext enthalten")
    if source["kind"] == "canonical":
        if not source.get("uri"):
            raise ValidationError("source.kind=canonical verlangt source.uri (Pfad im Modul)")
        hash_value = source.get("hash")
        if not isinstance(hash_value, dict) or hash_value.get("algorithm") != "sha256":
            raise ValidationError("source.kind=canonical verlangt source.hash={algorithm: sha256, value: ...}")
        if not _is_sha256(hash_value.get("value", "")):
            raise ValidationError("source.hash.value ist kein gueltiger SHA-256-Hexwert")
    if source["kind"] == "external-module":
        if not source.get("module"):
            raise ValidationError("source.kind=external-module verlangt source.module (Paketname)")

    if entry["kind"] == "consumer" and source["kind"] != "external-module":
        raise ValidationError("kind=consumer verlangt source.kind=external-module")

    targets = entry["targets"]
    if not isinstance(targets, list):
        raise ValidationError("targets muss eine Liste sein")
    for target in targets:
        if not isinstance(target, dict):
            raise ValidationError("jeder targets-Eintrag muss ein Objekt sein")
        if target.get("agent") not in AGENTS:
            raise ValidationError(f"target.agent unbekannt: {target.get('agent')} (bekannt: {sorted(AGENTS)})")
        if not target.get("config_path"):
            raise ValidationError("target.config_path ist erforderlich (wo der Hook registriert ist)")
        # deploy_path ist NUR fuer kind=hook/source.kind=canonical Pflicht -- ein
        # consumer/external-module hat nichts, das materialisiert werden koennte.
        if entry["kind"] == "hook" and source["kind"] == "canonical" and not target.get("deploy_path"):
            raise ValidationError(
                f"target fuer agent={target.get('agent')} braucht deploy_path (canonical hook ohne Zielpfad)"
            )

    if not isinstance(entry["consumers"], list):
        raise ValidationError("consumers muss eine Liste sein")

    adoption = entry["adoption"]
    if not isinstance(adoption, dict):
        raise ValidationError("adoption muss ein Objekt {host: status} sein")
    for host, status in adoption.items():
        if status not in ADOPTIONS:
            raise ValidationError(f"adoption['{host}']: unbekannter Status {status!r} (erlaubt: {sorted(ADOPTIONS)})")

    # HE2-Vorbereitung (Hook-Doctor + Consent-Allowlist, bewusst NICHT hier
    # implementiert -- Folgeticket): Felder sind optional und WERDEN validiert,
    # wenn gesetzt, damit ein doctor-Check spaeter andocken kann, ohne das
    # Schema erneut zu aendern. Siehe README "Vorbereitete Doctor-Felder".
    doctor = entry.get("doctor")
    if doctor is not None:
        if not isinstance(doctor, dict):
            raise ValidationError("doctor muss ein Objekt sein, wenn gesetzt")
        if "exec_check" in doctor and not isinstance(doctor["exec_check"], bool):
            raise ValidationError("doctor.exec_check muss bool sein")
        if "mtime_policy" in doctor and doctor["mtime_policy"] not in (None, "warn-if-newer-than-deploy", "ignore"):
            raise ValidationError("doctor.mtime_policy: unbekannter Wert")
        if "allowlist" in doctor and doctor["allowlist"] is not None and not isinstance(doctor["allowlist"], list):
            raise ValidationError("doctor.allowlist muss eine Liste oder null sein")

    return entry
