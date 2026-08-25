#!/usr/bin/env python3
"""Gebündelter PreToolUse-Guard: bach.db-Schreibschutz + destruktive Git-Befehle.

Warum gebündelt? Früher liefen `bach_db_guard.py` und `git_guard.py` als zwei
getrennte Hooks — also ZWEI Python-Interpreter bei JEDEM Bash-Aufruf. Gemessen
auf WORKSTATION-LG: ~575 ms Aufschlag pro Befehl, auch bei `ls`. Ein Prozess
statt zwei plus Start mit `-S` (kein site-Modul) drücken das auf ~165 ms.

Aufruf (settings.json):
    python -S -X utf8 "C:/Users/<USER>/.claude/hooks/guards.py"

Exit-Codes:
    0 = durchlassen        2 = BLOCKIEREN (Begründung auf stderr)

Fail-open: Jeder interne Fehler endet mit Exit 0. Ein kaputter Guard darf
niemals die Arbeit blockieren — er ist ein Schutzgeländer, keine
Sicherheitsgrenze. Die einzige echte Grenze wäre ein SQLite-Authorizer in
bach_api.
"""

import json
import re
import sys

WRITE_STATEMENT = re.compile(
    r"""\b(?:
          INSERT \s+ (?:OR\s+\w+\s+)? INTO
        | REPLACE \s+ INTO
        | UPDATE \s+ [\w."'\[\]`]+ \s+ SET
        | DELETE \s+ FROM
        | DROP \s+ (?:TABLE|INDEX|VIEW|TRIGGER)
        | ALTER \s+ TABLE
        | CREATE \s+ (?:TABLE|INDEX|VIEW|TRIGGER)
        | TRUNCATE \s+ TABLE
    )\b""",
    re.IGNORECASE | re.VERBOSE,
)
READ_ONLY = re.compile(r"mode=ro\b|immutable=1", re.IGNORECASE)
MENTIONS_SQLITE = re.compile(r"\bsqlite3(?:\.connect|\.exe)?\b", re.IGNORECASE)
MENTIONS_BACH_DB = re.compile(r"bach\.db\b", re.IGNORECASE)
USES_BACH_API = re.compile(r"bach_api|from\s+core\.|from\s+hub\.", re.IGNORECASE)
DIRECT_SQLITE_CLI = re.compile(r"\bsqlite3(?:\.exe)?\s+[^\r\n]*bach\.db\b", re.IGNORECASE)

DESTRUCTIVE_GIT = re.compile(
    r"\bgit\s+(?:"
    r"push\b[^\r\n]*(?:\s-f\b|--force\b)|"
    r"reset\s+--hard\b|"
    r"clean\s+-[^\s]*(?:f|d|x)[^\s]*|"
    r"branch\s+-D\b"
    r")",
    re.IGNORECASE,
)


def check_bach_db(command: str) -> str:
    """Gibt eine Begründung zurück, wenn blockiert werden soll — sonst ''."""
    if not (MENTIONS_SQLITE.search(command) and MENTIONS_BACH_DB.search(command)):
        return ""
    if READ_ONLY.search(command) and not DIRECT_SQLITE_CLI.search(command):
        return ""
    if not WRITE_STATEMENT.search(command):
        return ""
    if USES_BACH_API.search(command) and not DIRECT_SQLITE_CLI.search(command):
        return ""
    return (
        "BLOCK - direkter schreibender Zugriff auf bach.db. "
        "Schreiben ausschließlich über bach_api oder die BACH-CLI."
    )


def check_git(command: str) -> str:
    if DESTRUCTIVE_GIT.search(command):
        return f"GIT-GUARD: Destruktive Operation erkannt und blockiert. Befehl: {command}"
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command", "")
    if not isinstance(command, str) or not command:
        return 0

    for reason in (check_bach_db(command), check_git(command)):
        if reason:
            print(reason, file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(0)
