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
import shlex
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


_TRENNER = {";", "&", "&&", "|", "||", "\n"}


def _segmente(text: str) -> list[str]:
    """Zerlegt eine Kommandozeile an ECHTEN Trennern in Einzelkommandos.

    Warum nicht per Zeichenklasse: ';' und '&' treten auch auf, ohne ein
    Kommando zu beenden -- in Umleitungen wie 2>&1 und in zitierten
    Argumenten wie 'HEAD:refs/heads/a;b'. Wer dort trennt, verliert das
    Force-Flag aus dem Blick und laesst einen echten Force-Push durch
    (T-20260913-235210967).

    Faellt shlex aus (unbalancierte Anfuehrungszeichen o. ae.), wird die
    ganze Zeile als EIN Segment zurueckgegeben: dann greift wieder das
    breite Verhalten von vorher, das lieber zu viel blockt als zu wenig.
    """
    try:
        segments = []
        # Zeilenweise, BEVOR shlex laeuft: shlex zaehlt den Zeilenumbruch zum
        # Whitespace und liefert ihn nie als Token. Wuerde man die Tokens
        # zeilenuebergreifend zusammenfuegen, stuende das naechste Kommando
        # nicht mehr am Segmentanfang -- und _CMD_POS verlangt genau das.
        for zeile in text.splitlines():
            # posix=False ist der Kern: shlex laesst die Anfuehrungszeichen am
            # Token stehen. Nur ein NACKTES ';' oder '&' ist damit ein Trenner --
            # ein zitiertes bleibt "';'" und trennt nicht. Mit posix=True wurde
            # aus dem gueltigen Refnamen 'git push origin & --force' ein Trenner,
            # und der Force-Push rutschte durch (zweiter Review-Blocker).
            lex = shlex.shlex(zeile, posix=False, punctuation_chars=True)
            lex.whitespace_split = True
            current = []
            vorheriges = ""
            for token in lex:
                # Ein per Backslash maskierter Trenner beendet KEIN Kommando --
                # shlex liefert ihn als zwei Tokens ('\' und ';'), und wer dort
                # trennt, verliert das Force-Flag aus dem Segment
                # (dritter Review-Blocker).
                escaped = vorheriges.endswith("\\")
                vorheriges = token
                if token in _TRENNER and not escaped:
                    seg = " ".join(current).strip()
                    if seg:
                        segments.append(seg)
                    current = []
                else:
                    # Erst NACH der Trenner-Entscheidung entquoten: der Mustertext
                    # soll 'git push "-f"' wie 'git push -f' sehen.
                    current.append(token.strip("'\""))
                    continue
                if escaped:
                    current.append(token)
            seg = " ".join(current).strip()
            if seg:
                segments.append(seg)
        return segments
    except Exception:
        return [text]


# ------------------------------------------------------- git in OneDrive ----
# Am 2026-07-26 loeschte ein `git pull --rebase` mit anschliessendem
# `git checkout -B main origin/main` im OneDrive-Arbeitsbaum des CRM-Projekts
# 6039 Dateien (T-20260924-532136326): Der Rebase checkt zuerst den Remote-Stand
# aus und entfernt dabei alles, was nur im lokalen Commit steht; das Zuruecksetzen
# des Branches machte den Verlust endgueltig. Forschungsprojekte behalten ihr .git
# bewusst in OneDrive (Plan-D-Ausnahme), deshalb sind dort alle Git-Operationen,
# die den Arbeitsbaum umschreiben oder einen Branch versetzen, nur mit
# ausdruecklicher Freigabe erlaubt: `ONEDRIVE_GIT_OK=1 git ...` im Befehl.
# Fail-closed: Ist das Zielverzeichnis nicht bestimmbar, wird geblockt.
ONEDRIVE_OK = re.compile(r"(?:^|[\s;&|(])ONEDRIVE_GIT_OK=1\b")
_ONEDRIVE_PATH = re.compile(r"(?:^|[\\/])onedrive(?:[\\/]|$)", re.IGNORECASE)
_RISKY_SUB = re.compile(
    r"^(?:"
    r"pull\b|"
    r"rebase\b(?!\s+--(?:abort|quit)\b)|"
    r"reset\b.*\s--(?:hard|keep|merge)\b|"
    r"checkout\b.*(?:\s-[A-Za-z]*[Bf]\b|\s--force\b|\s--\s|\s--$|\s\.(?:\s|$))|"
    r"switch\b.*\s(?:-[A-Za-z]*[Cf]\b|--force-create\b|--discard-changes\b|--force\b)|"
    r"restore\b|"
    r"merge\b(?!\s+--(?:abort|quit)\b)|"
    r"branch\b.*\s(?:-f\b|--force\b)"
    r")"
)


def _onedrive_join(base: str, path: str) -> str:
    path = path.strip("'\"")
    if re.match(r"^(?:[A-Za-z]:[\\/]|/|~)", path) or not base:
        return path
    return base.rstrip("\\/") + "/" + path


def check_onedrive_git(command: str, cwd: str) -> str:
    """Blockt arbeitsbaum-/branch-umschreibende Git-Befehle in OneDrive-Pfaden."""
    if not command or ONEDRIVE_OK.search(command) or "git" not in command:
        return ""
    current = cwd or ""
    for seg in _segmente(executable_text(command)):
        try:
            lex = shlex.shlex(seg, posix=False)
            lex.whitespace_split = True
            words = [w.strip("'\"") for w in lex]  # posix=False: Backslashes in Windows-Pfaden bleiben
        except ValueError:
            words = seg.split()
        while words and re.match(r"^\w+=", words[0]):
            words = words[1:]
        if not words:
            continue
        if words[0] == "cd" and len(words) > 1:
            current = _onedrive_join(current, words[1])
            continue
        if words[0] not in ("git", "git.exe"):
            continue
        target, i = current, 1
        while i < len(words) and words[i].startswith("-"):
            if words[i] in ("-C", "-c") and i + 1 < len(words):
                if words[i] == "-C":
                    target = _onedrive_join(target, words[i + 1])
                i += 2
            elif words[i].startswith(("--git-dir=", "--work-tree=")):
                target = _onedrive_join(target, words[i].split("=", 1)[1])
                i += 1
            else:
                i += 1
        sub = " ".join(words[i:])
        if not _RISKY_SUB.search(sub):
            continue
        if target and not _ONEDRIVE_PATH.search(target.replace("\\", "/")):
            continue
        where = target or "unbekanntes Verzeichnis (fail-closed)"
        return (
            "ONEDRIVE-GIT-GUARD: 'git " + sub[:80] + "' in " + where + " blockiert. "
            "In OneDrive-Repos koennen pull/rebase/reset/checkout/merge Dateien loeschen "
            "(CRM-Verlust 26.07.2026). Erst sichern (git branch rescue/<datum> HEAD), "
            "dann bewusst freigeben mit 'ONEDRIVE_GIT_OK=1 git ...'."
        )
    return ""


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
    text = executable_text(command)
    if any(DESTRUCTIVE_GIT.search(seg) for seg in _segmente(text)):
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

    cwd = payload.get("cwd", "")
    for reason in (check_bach_db(command), check_git(command),
                   check_onedrive_git(command, cwd if isinstance(cwd, str) else "")):
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
