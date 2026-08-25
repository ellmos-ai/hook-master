"""Metadata-only pointer store. Same atomic-write/load discipline as
policy_registry.registry.PolicyRegistry -- copied deliberately (Nachtrag-2-Faustregel
aus dem source-resolver-Ticket gilt hier genauso: "was sich beim Kopieren
auseinanderentwickeln kann, wird nicht kopiert, sondern aufgerufen" -- aber
policy-registry ist ein FREMDES Modul mit eigenem Lebenszyklus, es als Laufzeit-
Abhaengigkeit zu importieren waere die falsche Kopplung fuer ein standalone-faehiges
Register. Der MECHANISMUS wird geteilt, der CODE bewusst dupliziert -- das ist exakt
der Fall, den das Options-A-Argument im Blueprint-Ticket macht: Vorbild, kein
Merge-Ziel.)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .model import SCHEMA, expand_uri, sha256_file, validate_entry


class RegistryError(RuntimeError):
    pass


def default_registry_path() -> Path:
    configured = os.environ.get("HOOK_MASTER_REGISTRY_PATH")
    if configured:
        return Path(os.path.expandvars(os.path.expanduser(configured)))
    return Path.home() / ".hook-master" / "registry.json"


class HookRegistry:
    """Metadata-only registry. Canonical script bytes stay at source.uri (or, for
    kind=consumer/external-module entries, there is no script at all -- the
    consumer owns its own registration format)."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_registry_path()

    def _empty(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "updated_at": None, "entries": []}

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RegistryError(f"Registry nicht lesbar: {self.path}: {exc}") from exc
        if data.get("schema") != SCHEMA or not isinstance(data.get("entries"), list):
            raise RegistryError(f"Ungueltiges Registry-Format: {self.path}")
        for entry in data["entries"]:
            validate_entry(entry)
        return data

    def save(self, data: dict[str, Any]) -> None:
        data["schema"] = SCHEMA
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        for entry in data["entries"]:
            validate_entry(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)

    def init(self) -> Path:
        if not self.path.exists():
            self.save(self._empty())
        return self.path

    def register(self, entry: dict[str, Any], *, replace: bool = False) -> dict[str, Any]:
        entry = validate_entry(dict(entry))
        data = self.load()
        matches = [i for i, item in enumerate(data["entries"]) if item["id"] == entry["id"]]
        if matches and not replace:
            raise RegistryError(f"Eintrag existiert bereits: {entry['id']}")
        if matches:
            data["entries"][matches[0]] = entry
        else:
            data["entries"].append(entry)
        data["entries"].sort(key=lambda item: item["id"])
        self.save(data)
        return entry

    def register_many(self, entries: Iterable[dict[str, Any]], *, replace: bool = False) -> list[dict[str, Any]]:
        data = self.load()
        by_id = {item["id"]: item for item in data["entries"]}
        registered = []
        for raw in entries:
            entry = validate_entry(dict(raw))
            if entry["id"] in by_id and not replace:
                raise RegistryError(f"Eintrag existiert bereits: {entry['id']}")
            by_id[entry["id"]] = entry
            registered.append(entry)
        data["entries"] = sorted(by_id.values(), key=lambda item: item["id"])
        self.save(data)
        return registered

    def get(self, entry_id: str) -> dict[str, Any] | None:
        return next((e for e in self.load()["entries"] if e["id"] == entry_id), None)

    def search(
        self, query: str = "", *, event: str | None = None, agent: str | None = None, kind: str | None = None
    ) -> list[dict[str, Any]]:
        needle = query.casefold()
        results = []
        for entry in self.load()["entries"]:
            haystack = " ".join(
                [entry["id"], entry["title"], entry.get("summary", ""), " ".join(entry.get("tags", []))]
            ).casefold()
            if needle and needle not in haystack:
                continue
            if event and entry["event"] != event:
                continue
            if agent and not any(t.get("agent") == agent for t in entry.get("targets", [])):
                continue
            if kind and entry["kind"] != kind:
                continue
            results.append(entry)
        return results

    def verify(self) -> dict[str, Any]:
        """Hash-check every kind=hook/source.kind=canonical entry against its
        canonical file on disk. This is the security-relevant check -- unlike
        policy-registry's verify(), a mismatch here means EXECUTABLE code drifted
        from what the registry attests, not just text."""
        entries = self.load()["entries"]
        checks = []
        for entry in entries:
            source = entry["source"]
            if source["kind"] != "canonical":
                checks.append({"id": entry["id"], "state": "not-canonical"})
                continue
            source_path = expand_uri(source["uri"])
            if source_path is None or not source_path.exists():
                checks.append({"id": entry["id"], "state": "missing"})
                continue
            expected = source["hash"]["value"]
            actual = sha256_file(source_path)
            checks.append({"id": entry["id"], "state": "ok" if actual == expected else "hash-mismatch", "actual": actual})
        return {
            "registry": str(self.path),
            "entries": len(entries),
            "checks": checks,
            "ok": all(item["state"] not in {"missing", "hash-mismatch"} for item in checks),
        }


__all__ = ["HookRegistry", "RegistryError"]
