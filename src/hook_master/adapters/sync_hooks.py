"""Bridge to the pre-existing .SYNC/hooks/{README.md,adoption/*.json} layout
(gemessen 2026-08-25: 9 dokumentierte Hooks + adoption/{laptop,workstation}.json).
Mirrors policy_registry.adapters.sync_policies exactly: import pointers from the
legacy flat-file layout, export an aggregated read-only view back into it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..registry import HookRegistry


def import_adoption_pointers(
    registry: HookRegistry, sync_root: str | Path, *, slot: str, replace: bool = False
) -> dict[str, Any]:
    """One-time migration helper: read .SYNC/hooks/adoption/<slot>.json's existing
    per-actor hook lists and register ONE consumer entry per external-module
    (memoryhooker, workflowhooker), aggregating every agent/event that references
    it. Does NOT invent script paths for canonical/local-copy/inline hooks --
    those need someone to actually read the file and register it deliberately
    (see the 4 sparmodus/notaus hooks registered by hand in this ticket); they
    are returned in `skipped` for review, never silently guessed."""
    adoption_file = Path(sync_root) / "adoption" / f"{slot}.json"
    data = json.loads(adoption_file.read_text(encoding="utf-8"))
    known_ids = {e["id"] for e in registry.load()["entries"]}
    modules: dict[str, dict[str, Any]] = {}
    skipped: list[str] = []

    for actor_name, actor in data.get("actors", {}).items():
        for hook in actor.get("hooks", []):
            hook_id = hook["id"]
            if hook.get("source") != "external-module":
                skipped.append(f"{actor_name}:{hook_id} (source={hook.get('source')}, manuelle Registrierung noetig)")
                continue
            module = hook_id.split(":", 1)[0] if ":" in hook_id else hook_id
            entry_id = f"consumer:{module}"
            if entry_id in known_ids:
                skipped.append(f"{actor_name}:{hook_id} (consumer:{module} bereits registriert)")
                continue
            record = modules.setdefault(
                module,
                {
                    "id": entry_id,
                    "kind": "consumer",
                    "title": module,
                    "summary": f"Externes Modul mit eigener Hook-Registrierungslogik, aus {slot}-Adoption uebernommen.",
                    "event": hook["event"],
                    "source": {"kind": "external-module", "module": module},
                    "targets": [],
                    "consumers": [module],
                    "status": "active",
                    "adoption": {slot: "adopted"},
                    "tags": ["imported", slot],
                },
            )
            target = {"agent": actor_name, "config_path": actor.get("settings", "-")}
            if target not in record["targets"]:
                record["targets"].append(target)

    registered = registry.register_many(list(modules.values()), replace=replace) if modules else []
    return {"registered": registered, "skipped": skipped}


def export_aggregated_view(registry: HookRegistry, sync_root: str | Path, *, slot: str) -> Path:
    """Metadata-only host view, written into the EXISTING .SYNC/hooks structure --
    never requires system-gap-master, works purely as a file write."""
    root = Path(sync_root)
    target = root / "registry" / f"{slot}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    data = registry.load()
    view = {
        "schema": "ellmos.hook-registry-view.v1",
        "slot": slot,
        "authority": "local-hook-registry",
        "registry_path": str(registry.path),
        "updated_at": data["updated_at"],
        "entries": data["entries"],
        "note": "Metadaten/Pointer, kein Skript-Volltext. Kanonische Skripte liegen im hook-master-Modul.",
    }
    target.write_text(json.dumps(view, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


__all__ = ["import_adoption_pointers", "export_aggregated_view"]
