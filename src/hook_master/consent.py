"""Erstnutzungs-Consent-Allowlist (HE2, T-20260825-519184830). Konzept-Nachbau
nach dem Hermes-Agent-Muster (nicht Code-Uebernahme, siehe Quellticket
T-20260825-152496601): analog zu App-Erstinstallations-Berechtigungen wird ein
NEUER Hook nicht stillschweigend aktiv, sondern muss einmalig explizit bestaetigt
werden, bevor `deploy()` ihn materialisiert.

Zwei bewusst UNTERSCHIEDLICHE Fehlerhaltungen, kein Widerspruch:
- Lesen ist fail-open: eine fehlende/kaputte allowlist.json wirft NIE eine
  Exception -- ein kaputtes Consent-File darf den ganzen `hook-master`-Betrieb
  nicht lahmlegen (dieselbe Fail-open-Haltung wie guards.py selbst: ein
  kaputter Schutzmechanismus blockiert nicht die Arbeit).
- Die DEPLOY-Entscheidung ist fail-closed: fehlt ein Eintrag oder ist er nicht
  explizit `consented=true`, gilt er als NICHT freigegeben -- Unsicherheit
  fuehrt zu "nicht deployen", nie zu "deployen, weil unklar".
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "ellmos.hook-consent.v1"


@dataclass
class ConsentRecord:
    consented: bool
    consented_at: str | None
    consented_by: str | None
    note: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "consented": self.consented,
            "consented_at": self.consented_at,
            "consented_by": self.consented_by,
            "note": self.note,
        }


class ConsentStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else self.default_path()

    @staticmethod
    def default_path() -> Path:
        configured = os.environ.get("HOOK_MASTER_ALLOWLIST_PATH")
        if configured:
            return Path(os.path.expandvars(os.path.expanduser(configured)))
        return Path.home() / ".hook-master" / "allowlist.json"

    def load(self) -> dict[str, ConsentRecord]:
        """Fail-open: jede Lesestoerung (Datei fehlt, kaputtes JSON, falsches
        Schema) liefert eine LEERE Allowlist zurueck statt einer Exception."""
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("schema") != SCHEMA or not isinstance(data.get("entries"), dict):
                return {}
            return {
                entry_id: ConsentRecord(
                    consented=bool(record.get("consented", False)),
                    consented_at=record.get("consented_at"),
                    consented_by=record.get("consented_by"),
                    note=record.get("note"),
                )
                for entry_id, record in data["entries"].items()
            }
        except (OSError, json.JSONDecodeError):
            return {}

    def save(self, records: dict[str, ConsentRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema": SCHEMA,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "entries": {entry_id: record.to_dict() for entry_id, record in records.items()},
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)

    def is_consented(self, entry_id: str) -> bool:
        """Fail-closed: kein Eintrag ODER `consented != true` bedeutet 'nein'."""
        record = self.load().get(entry_id)
        return record is not None and record.consented

    def grant(self, entry_id: str, *, by: str = "user", note: str | None = None) -> ConsentRecord:
        records = self.load()
        record = ConsentRecord(
            consented=True, consented_at=datetime.now(timezone.utc).isoformat(), consented_by=by, note=note
        )
        records[entry_id] = record
        self.save(records)
        return record

    def revoke(self, entry_id: str) -> None:
        records = self.load()
        if entry_id in records:
            records[entry_id].consented = False
            self.save(records)

    def seed_grandfathered(self, entry_ids: list[str], *, note: str) -> list[ConsentRecord]:
        """Bereits vor Existenz der Allowlist deployte Eintraege als
        'grandfathered' markieren -- explizit dokumentiert, kein stilles
        Uebergehen der Consent-Pflicht."""
        records = self.load()
        granted = []
        for entry_id in entry_ids:
            record = ConsentRecord(
                consented=True,
                consented_at=datetime.now(timezone.utc).isoformat(),
                consented_by="grandfathered",
                note=note,
            )
            records[entry_id] = record
            granted.append(record)
        self.save(records)
        return granted


__all__ = ["ConsentRecord", "ConsentStore"]
