#!/usr/bin/env python3
"""PreToolUse-Hook: Edit-Schutz durch lock-master -- OHNE zweite Implementierung.

Dieses Skript ist nur der Anschluss: es sucht lock-masters `plugin/lock_guard.py` und fuehrt es mit
denselben Argumenten aus (z. B. `pretooluse --actor codex`). Alle Lock-Semantik (Datei-Locks, Fencing,
Team-Brett-Claims, apply_patch-/Kimi-Ziele, Ablehnungsvertrag je Akteur) liegt dort und nur dort.

Gegenstueck zu lock_push_guard.py (Push-Schutz, Repo-Root-Locks): dieser Hook bewacht Datei-Aenderungen
(Claude Edit/Write/MultiEdit/NotebookEdit, Codex apply_patch, Kimi WriteFile/StrReplaceFile/DeleteFile/
MoveFile). `git push` bleibt bei lock_push_guard.

SICHERHEIT: Gefundener Code wird AUSGEFUEHRT. Deshalb gibt es nur Fundorte, die dem Benutzer gehoeren:
    1. Umgebungsvariable ELLMOS_LOCK_MASTER (Repo-Wurzel, Plugin-Wurzel oder die Datei selbst): ausdrueckliche
       Entscheidung des Benutzers, wird nicht weiter geprueft
    2. Claude-Code-Plugin-Cache ~/.claude/plugins/cache/**/ellmos-lock-master/*/ (neueste Version)
    3. ~/_Local_DEV/repos/lock-master
Alles ausser 1 muss unter dem Home-Verzeichnis liegen; unter POSIX gehoeren Datei und ihre Ordner bis zum Home dem
Benutzer und sind fuer Gruppe und andere nicht beschreibbar. Laufwerkswurzeln (etwa C:/_Local_DEV) werden NICHT
durchsucht: dort koennen unter Windows auch andere angemeldete Konten Ordner anlegen. Unter Windows genuegt die
Beschraenkung auf das Benutzerprofil, das mit den Windows-Voreinstellungen fuer andere Standardkonten nicht beschreibbar
ist; eine Owner-SID-Pruefung braeuchte Win32-Aufrufe und brachte dort keinen zusaetzlichen Schutz. Liegt der Klon an einer
Laufwerkswurzel, ELLMOS_LOCK_MASTER setzen.

Nicht gefunden: eine Zeile auf stderr, Exit 0 -- dieselbe Haltung wie hooks/run.sh des Plugins (die Lock-Pruefung ist
dann inaktiv, und das wird laut gesagt, nicht verschwiegen). Fehler IM Guard lehnt der Guard selbst fail-closed ab.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

RELATIVE = Path("plugin") / "lock_guard.py"


def explicit() -> list[Path]:
    env = os.environ.get("ELLMOS_LOCK_MASTER", "").strip()
    if not env:
        return []
    base = Path(env).expanduser()
    return [base, base / RELATIVE, base / "lock_guard.py"]


def default_locations() -> list[Path]:
    home = Path.home()
    cache = home / ".claude" / "plugins" / "cache"
    found: list[Path] = []
    if cache.is_dir():
        found += sorted(cache.glob(f"**/ellmos-lock-master/*/{RELATIVE.as_posix()}"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    found.append(home / "_Local_DEV" / "repos" / "lock-master" / RELATIVE)
    return found


def candidates() -> list[Path]:
    return explicit() + default_locations()


def owned_by_user(path: Path, home: Path) -> bool:
    """Under home; on POSIX also owned by the user and not writable by group or others, the file and every folder
    up to home."""
    try:
        resolved, home = path.resolve(), home.resolve()
        resolved.relative_to(home)
    except (OSError, ValueError):
        return False
    if os.name != "posix":
        return True  # the profile is not writable for other accounts, see the module docstring
    for item in (resolved, *resolved.parents):
        if item == home.parent:
            break
        info = item.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o022:
            return False
    return True


def locate() -> Path | None:
    for path in explicit():
        if path.is_file() and path.name == "lock_guard.py":
            return path
    home = Path.home()
    for path in default_locations():
        if path.is_file() and path.name == "lock_guard.py" and owned_by_user(path, home):
            return path
    return None


def main(argv: list[str]) -> int:
    script = locate()
    if script is None:
        print("lock_edit_guard: lock-master's plugin/lock_guard.py not found in a trusted location (set "
              "ELLMOS_LOCK_MASTER); lock checks are inactive", file=sys.stderr)
        return 0
    sys.argv = [str(script), *argv[1:]]
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        if exc.code is None:
            return 0
        if isinstance(exc.code, int):
            return exc.code
        print(exc.code, file=sys.stderr)  # sys.exit("text"): the text is the message, the status is 1
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
