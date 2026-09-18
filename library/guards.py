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
bach_api (BACH-Task, siehe .SYNC/BACH-DB-SCHUTZ.md).

Die Einzelskripte bach_db_guard.py / git_guard.py bleiben als eigenständig
testbare Module bestehen; dieses Modul importiert ihre Logik nicht, sondern
hält sie bewusst dupliziert, damit ein Fehler in einem Guard den anderen nicht
mitreisst. Änderungen bitte hier UND dort nachziehen.
"""

import json
import re
import sys

# ---------------------------------------------------------------- bach.db ----
# Echte schreibende SQL-Statements — mit Kontext, nicht als blosses Stichwort.
# (Frühere Fassung matchte das nackte Wort ALTER und blockierte damit jedes
#  Skript, in dem das deutsche Wort "Alter" vorkam. Belegt am 2026-07-13.)
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

# -------------------------------------------------------------------- git ----
# Heredoc-Bloecke: quoted/backslash-Delimiter => Body ist Literal (keine Ausfuehrung);
# unquoted Delimiter => Bash expandiert $(...) und `...` im Body, nur das bleibt relevant.
_HEREDOC = re.compile(
    r"<<-?\s*(?P<q>['\"]?)(?P<bs>\\?)(?P<tag>\w+)(?P=q)[^\n]*\n(?P<body>.*?)^[ \t]*(?P=tag)[ \t]*\r?$",
    re.DOTALL | re.MULTILINE,
)
_SUBST = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")

# Nur an Kommandoposition: Zeilenanfang, nach Verkettungs-/Substitutionsoperator, nach
# einem Ausfuehrungs-Wrapper oder nach `-c "` (bash -c / sh -c) — optional mit VAR=wert-
# Praefix und git-Globaloptionen. Prosa, Kommentare, Commit-Messages und Heredoc-Nutztext
# ueber destruktive Befehle werden dadurch NICHT mehr geblockt (T-20260902-850607132;
# dieselbe Haertung wie WRITE_STATEMENT am 2026-07-13, nur fuer die git-Seite).
_CMD_POS = (
    r"(?:^|[;&|(`]|\$\(|\b(?:then|do|else|eval|exec|sudo|xargs|nohup|time|command|env)\b|-c\s*[\"']?)"
    r"\s*"
)
_ENV_PREFIX = r"(?:\w+=\S*\s+)*"
_GIT_OPTS = r"(?:-[Cc]\s+\S+\s+|--git-dir=\S+\s+|--work-tree=\S+\s+)*"
DESTRUCTIVE_GIT = re.compile(
    _CMD_POS + _ENV_PREFIX + r"git\s+" + _GIT_OPTS + r"(?:"
    r"push\b[^\r\n]*(?:\s-f\b|--force\b)|"
    r"reset\s+--hard\b|"
    r"clean\s+-[^\s]*(?:f|d|x)[^\s]*|"
    r"branch\s+(?-i:-D)\b"  # case-sensitiv: `-d` ist das sichere Loeschen
    r")",
    re.IGNORECASE | re.MULTILINE,
)


def executable_text(command: str) -> str:
    """Entfernt Heredoc-Nutztext; aus unquoted Heredocs bleiben nur Command-Substitutions."""
    def repl(m):
        if m.group("q") or m.group("bs"):
            return "\n"
        subs = [a or b for a, b in _SUBST.findall(m.group("body"))]
        return "\n" + "\n".join(subs) + "\n"
    return _HEREDOC.sub(repl, command)


def check_bach_db(command: str) -> str:
    """Gibt eine Begründung zurück, wenn blockiert werden soll — sonst ''."""
    if not (MENTIONS_SQLITE.search(command) and MENTIONS_BACH_DB.search(command)):
        return ""
    if READ_ONLY.search(command) and not DIRECT_SQLITE_CLI.search(command):
        return ""  # rein lesend
    if not WRITE_STATEMENT.search(command):
        return ""  # kein echtes Schreib-Statement (nur Prosa/Stichwort)
    if USES_BACH_API.search(command) and not DIRECT_SQLITE_CLI.search(command):
        return ""  # legitimer Weg
    return (
        "BLOCK - direkter schreibender Zugriff auf bach.db. "
        "Schreiben ausschließlich über bach_api oder die BACH-CLI."
    )


def check_git(command: str) -> str:
    if DESTRUCTIVE_GIT.search(executable_text(command)):
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
    except Exception:  # fail-open
        raise SystemExit(0)
