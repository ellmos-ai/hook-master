"""Git-Provider-Stub: universeller Fallback (ROADMAP v0.2+)."""

from __future__ import annotations

from .base import UnimplementedProvider


class GitProvider(UnimplementedProvider):
    name = "git"
    reason = "Git-Hook-Installation ist fuer v0.1 bewusst nicht gebaut (siehe ROADMAP v0.2+)."


__all__ = ["GitProvider"]
