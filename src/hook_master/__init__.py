"""hook-master -- local-first pointer registry + materialization for agent hooks.

Sibling module to policy-registry, same mechanic (pointer-only registry, optional
system-gap-master transport, standalone without the ecosystem), applied to a
structurally different but analogous domain: hooks are EXECUTABLE code, not text,
so this module also adds an explicit deploy/diff/status materialization step that
policy-registry does not need (a policy pointer is useful as metadata alone; a hook
pointer is useless until the actual script exists at the path an agent's config
references).
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
