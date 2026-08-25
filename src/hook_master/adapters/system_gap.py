from __future__ import annotations

from pathlib import Path

from ..registry import HookRegistry
from .sync_hooks import export_aggregated_view


def available() -> bool:
    try:
        import system_gap_master  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return False
    return True


def publish_view(registry: HookRegistry, sync_root: str | Path, *, slot: str) -> Path:
    """Optional seam for a system-gap installation. The registry remains
    authoritative; this writes only a metadata view into the existing
    .SYNC/hooks structure and never requires system-gap-master for offline
    operation (same invariant as policy_registry.adapters.system_gap)."""
    return export_aggregated_view(registry, Path(sync_root), slot=slot)


__all__ = ["available", "publish_view"]
