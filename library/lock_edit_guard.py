#!/usr/bin/env python3
"""PreToolUse-Hook: Edit-Schutz durch lock-master -- OHNE zweite Implementierung.

Dieses Skript ist nur der Anschluss: es sucht lock-masters `plugin/lock_guard.py` und fuehrt es mit
denselben Argumenten aus (z. B. `pretooluse --actor codex`). Alle Lock-Semantik (Datei-Locks, Fencing,
Team-Brett-Claims, apply_patch-/Kimi-Ziele, Ablehnungsvertrag je Akteur) liegt dort und nur dort.

Gegenstueck zu lock_push_guard.py (Push-Schutz, Repo-Root-Locks): dieser Hook bewacht Datei-Aenderungen
(Claude Edit/Write/MultiEdit/NotebookEdit, Codex apply_patch, Kimi WriteFile/StrReplaceFile/DeleteFile/
MoveFile). `git push` bleibt bei lock_push_guard.

Fundort von lock_guard.py, erster Treffer gewinnt:
    1. Umgebungsvariable ELLMOS_LOCK_MASTER (Repo-Wurzel, Plugin-Wurzel oder die Datei selbst)
    2. <Laufwerk>/_Local_DEV/repos/lock-master und ~/_Local_DEV/repos/lock-master (Plan-D-Klon)
    3. Claude-Code-Plugin-Cache ~/.claude/plugins/cache/**/ellmos-lock-master/*/ (neueste Version)

Nicht gefunden: eine Zeile auf stderr, Exit 0 -- dieselbe Haltung wie hooks/run.sh des Plugins (die Lock-Pruefung ist
dann inaktiv, und das wird laut gesagt, nicht verschwiegen). Fehler IM Guard lehnt der Guard selbst fail-closed ab.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

RELATIVE = Path("plugin") / "lock_guard.py"


def candidates() -> list[Path]:
    found: list[Path] = []
    env = os.environ.get("ELLMOS_LOCK_MASTER", "").strip()
    if env:
        base = Path(env).expanduser()
        found += [base, base / RELATIVE, base / "lock_guard.py"]
    anchor = Path(sys.executable).anchor or Path.home().anchor
    for root in (Path(anchor) / "_Local_DEV" / "repos", Path.home() / "_Local_DEV" / "repos"):
        found.append(root / "lock-master" / RELATIVE)
    cache = Path.home() / ".claude" / "plugins" / "cache"
    if cache.is_dir():
        versions = sorted(cache.glob(f"**/ellmos-lock-master/*/{RELATIVE.as_posix()}"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        found += versions
    return found


def locate() -> Path | None:
    for path in candidates():
        if path.is_file() and path.name == "lock_guard.py":
            return path
    return None


def main(argv: list[str]) -> int:
    script = locate()
    if script is None:
        print("lock_edit_guard: lock-master's plugin/lock_guard.py not found (set ELLMOS_LOCK_MASTER); "
              "lock checks are inactive", file=sys.stderr)
        return 0
    sys.argv = [str(script), *argv[1:]]
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
