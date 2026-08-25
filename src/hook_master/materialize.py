"""Deploy/diff/status: the piece policy-registry's pattern does NOT need, because
a policy pointer is useful metadata on its own -- but a hook pointer is inert until
the actual script exists at the path an agent's settings.json/hooks.json/config.toml
references. `export_aggregated_view` (adapters/system_gap.py) writes a metadata
VIEW; this module writes the actual FILE.

Direction is fixed and one-way (Blueprint-Ticket, Punkt 3): canonical script lives
in this module's `library/`, deploy_path (e.g. ~/.claude/hooks/<name>.py) is the
MATERIALIZED copy. Never the reverse -- `deploy()` always overwrites deploy_path
from the canonical source, never the other way round.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .consent import ConsentStore
from .model import expand_uri, sha256_file
from .registry import HookRegistry


@dataclass
class DeployResult:
    entry_id: str
    agent: str
    deploy_path: str
    action: str  # "written" | "unchanged" | "skipped-no-canonical" | "skipped-missing-source" | "pending-consent"


def _canonical_path(entry: dict[str, Any]) -> Path | None:
    source = entry["source"]
    if source["kind"] != "canonical":
        return None
    return expand_uri(source["uri"])


def diff(registry: HookRegistry, *, entry_id: str | None = None) -> list[dict[str, Any]]:
    """Read-only: for every (entry, target) pair with a deploy_path, report whether
    the materialized copy matches the canonical hash. Never writes anything."""
    entries = registry.load()["entries"]
    if entry_id:
        entries = [e for e in entries if e["id"] == entry_id]
    results = []
    for entry in entries:
        canonical = _canonical_path(entry)
        for target in entry.get("targets", []):
            deploy_path = target.get("deploy_path")
            if not deploy_path:
                continue
            deployed = expand_uri(deploy_path)
            row = {"id": entry["id"], "agent": target["agent"], "deploy_path": str(deployed)}
            if canonical is None or not canonical.exists():
                row["state"] = "no-canonical-source"
            elif deployed is None or not deployed.exists():
                row["state"] = "not-deployed"
            else:
                canonical_hash = sha256_file(canonical)
                deployed_hash = sha256_file(deployed)
                row["state"] = "in-sync" if canonical_hash == deployed_hash else "drifted"
                row["canonical_hash"] = canonical_hash
                row["deployed_hash"] = deployed_hash
            results.append(row)
    return results


def deploy(
    registry: HookRegistry,
    *,
    entry_id: str | None = None,
    dry_run: bool = False,
    consent: ConsentStore | None = None,
) -> list[DeployResult]:
    """Copy canonical -> deploy_path for every target of matching entries.
    One-way, always overwrites the deployed copy. `dry_run=True` reports what
    WOULD happen without writing (used by the CLI's --dry-run flag).

    HE2 (T-20260825-519184830): a `kind=hook` entry with a canonical source is
    only ever materialized if `consent.is_consented(entry_id)` is true --
    fail-closed, see consent.py's module docstring. A brand-new, never-granted
    entry is reported as "pending-consent" and left untouched, never silently
    skipped-as-if-nothing-happened."""
    consent = consent or ConsentStore()
    entries = registry.load()["entries"]
    if entry_id:
        entries = [e for e in entries if e["id"] == entry_id]
    results: list[DeployResult] = []
    for entry in entries:
        canonical = _canonical_path(entry)
        for target in entry.get("targets", []):
            deploy_path = target.get("deploy_path")
            if not deploy_path:
                continue
            deployed = expand_uri(deploy_path)
            if canonical is None or not canonical.exists():
                results.append(DeployResult(entry["id"], target["agent"], str(deployed), "skipped-missing-source"))
                continue
            if not consent.is_consented(entry["id"]):
                results.append(DeployResult(entry["id"], target["agent"], str(deployed), "pending-consent"))
                continue
            if deployed.exists() and sha256_file(deployed) == sha256_file(canonical):
                results.append(DeployResult(entry["id"], target["agent"], str(deployed), "unchanged"))
                continue
            if not dry_run:
                deployed.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(canonical, deployed)
                shutil.copymode(canonical, deployed)
            results.append(DeployResult(entry["id"], target["agent"], str(deployed), "written"))
    return results


def status(registry: HookRegistry) -> dict[str, Any]:
    """Aggregated view combining registry.verify() (canonical file integrity) with
    diff() (materialization drift) -- one call for a human/CLI overview."""
    verify_result = registry.verify()
    diff_result = diff(registry)
    return {
        "registry": verify_result,
        "materialization": diff_result,
        "ok": verify_result["ok"] and all(row["state"] in {"in-sync", "no-canonical-source"} for row in diff_result),
    }


__all__ = ["DeployResult", "deploy", "diff", "status"]
