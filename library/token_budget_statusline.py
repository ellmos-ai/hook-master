#!/usr/bin/env python3
"""Statusline script: liest das Claude-Code-Statusline-JSON (stdin) und legt
einen kleinen Bridge-Snapshot ab, den andere Hooks (z. B. token_budget_guard.py)
lesen koennen, ohne selbst eine Statusline zu sein.

WARUM UEBER DIE STATUSLINE, NICHT UEBER EINEN HOOK:
Kein dokumentiertes Hook-Event (SessionStart/PreToolUse/PostToolUse/
UserPromptSubmit/Stop/PreCompact/...) enthaelt Token-, Kosten- oder
Limit-Felder (verifiziert gegen code.claude.com/docs/en/hooks, 2026-08-24).
NUR das Statusline-JSON traegt reale Nutzungsdaten, insbesondere
`rate_limits.five_hour.used_percentage` -- exakt das "Session-Limit", das der
User mit den Stufen 50/20/10 meint (Claude.ai Pro/Max, kontobasiert, daher
gueltig fuer ALLE Sessions/Agenten auf diesem Account, nicht nur fuer die
Session, die die Statusline gerade rendert).

EINSCHRAENKUNG (ehrlich dokumentiert, kein Ueberversprechen):
- `rate_limits` erscheint laut Doku erst NACH der ersten API-Antwort der
  Session und NUR fuer Claude.ai-Abonnenten (Pro/Max) -- kann fehlen.
- Die Statusline laeuft nur in einer interaktiven Terminal-Session mit
  aktivierter Statusline (settings.json -> statusLine). Hintergrund-/
  Subagenten-Sessions rendern typischerweise keine eigene Statusline, koennen
  aber diese Bridge-Datei LESEN, weil der Prozentwert account-, nicht
  session-gebunden ist.
- Dieses Skript SCHREIBT nur; es trifft keine Sparmodus-/Notaus-Entscheidung
  selbst (das macht token_budget_guard.py bzw. die Skills sparmodus/notaus).

Fail-open: jeder interne Fehler bricht die Statusline-Anzeige nicht ab.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from typing import Any


STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "state")
BRIDGE_PATH = os.path.join(STATE_DIR, "token_budget.json")


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _atomic_write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def _pct(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bar(pct: float, width: int = 10) -> str:
    filled = max(0, min(width, int(pct * width // 100)))
    return "#" * filled + "-" * (width - filled)


def main() -> int:
    _ensure_utf8_stdio()
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    rate_limits = payload.get("rate_limits") or {}
    five_hour = rate_limits.get("five_hour") or {}
    seven_day = rate_limits.get("seven_day") or {}
    context_window = payload.get("context_window") or {}

    five_pct = _pct(five_hour.get("used_percentage"))
    seven_pct = _pct(seven_day.get("used_percentage"))
    ctx_pct = _pct(context_window.get("used_percentage"))

    snapshot = {
        "written_at": time.time(),
        "session_id": payload.get("session_id"),
        "model": (payload.get("model") or {}).get("display_name"),
        "five_hour": {
            "used_percentage": five_pct,
            "resets_at": five_hour.get("resets_at"),
        },
        "seven_day": {
            "used_percentage": seven_pct,
            "resets_at": seven_day.get("resets_at"),
        },
        "context_window": {"used_percentage": ctx_pct},
        "source": "statusline",
    }

    try:
        _atomic_write_json(BRIDGE_PATH, snapshot)
    except Exception:
        pass  # Bridge-Schreibfehler duerfen die Statusline nie zum Absturz bringen

    model_name = snapshot["model"] or "?"
    parts = [f"[{model_name}]"]
    if ctx_pct is not None:
        parts.append(f"ctx {int(ctx_pct)}%")
    if five_pct is not None:
        parts.append(f"5h {_bar(five_pct)} {five_pct:.0f}%")
    if seven_pct is not None:
        parts.append(f"7d {seven_pct:.0f}%")
    print(" | ".join(parts))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail-open: bei jedem unerwarteten Fehler wenigstens eine leere Zeile,
        # damit die Statusline nie komplett verschwindet oder haengt.
        try:
            print("")
        except Exception:
            pass
        raise SystemExit(0)
