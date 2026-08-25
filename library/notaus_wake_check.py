#!/usr/bin/env python3
"""SessionStart-Hook: prueft beim Start JEDER neuen Session/Subagenten-Session,
ob der Sparmodus-System-Zustand (~/.claude/state/sparmodus_state.json,
Feld `mode`) auf "notaus" steht, und ob die dort festgelegte Aufwachbedingung
erfuellt ist.

Seit Ticket T-20260824-643372292 gibt es NUR NOCH diese eine Zustandsdatei
fuer das gesamte Sparmodus-System (mode: off | manual-spar | auto-spar |
notaus) -- keine separate notaus_state.json mehr (Migration: die fruehere
Datei wird, falls vorhanden, nicht mehr gelesen; ein frischer Notaus-Eintritt
schreibt ausschliesslich in sparmodus_state.json, siehe
token_budget_guard.py und Skill notaus).

Aufwachlogik (siehe Skill notaus/SKILL.md):
- Ist ein Reset-Zeitpunkt bekannt (`resets_at`, aus rate_limits.*.resets_at
  uebernommen), gilt: vor `wake_at` bleibt JEDE neue Session geparkt (nur
  State pruefen, keine neue Arbeit beginnen).
- Ist kein Reset-Zeitpunkt bekannt (`leader_only: true`), gilt die
  5-Stunden-Leader-Ping-Regel: nur eine als Leader verstandene Session
  wacht alle 5h kurz auf und prueft, ob wieder Guthaben da ist.
- Ist der Zustand nicht lesbar, nicht vorhanden, oder `mode` != "notaus",
  greift dieser Hook NICHT ein (fail-open) -- normale Sessionstart-
  Verarbeitung laeuft weiter.

Waehrend einer laufenden Session kann `token_budget_guard.py`
(UserPromptSubmit) den Notaus-Zustand bereits automatisch aufheben, sobald
sich die Bridge-Datei erholt zeigt -- dieser Hook ist der Sicherheitsnetz-Weg
fuer den Fall, dass genau das beim naechsten Sessionstart noch nicht
geschehen ist (z. B. weil zwischenzeitlich keine Session mit aktiver
Statusline lief).
"""

from __future__ import annotations

import json
import os
import sys
import time


STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "state")
SPARMODUS_STATE_PATH = os.path.join(STATE_DIR, "sparmodus_state.json")


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> int:
    _ensure_utf8_stdio()
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    state = _read_json(SPARMODUS_STATE_PATH)
    if state.get("mode") != "notaus":
        return 0  # kein Notaus aktiv -> normaler Sessionstart, kein Hinweis

    now = time.time()
    wake_at = state.get("wake_at")
    resets_at = state.get("resets_at")
    reason = state.get("reason", "")
    set_at = state.get("set_at")
    prior_mode = state.get("prior_mode") or "off"

    known_wake_target = wake_at if isinstance(wake_at, (int, float)) else resets_at

    if isinstance(known_wake_target, (int, float)) and now >= float(known_wake_target):
        msg = (
            "NOTAUS-STATE gefunden, aber Aufwachzeitpunkt ist erreicht "
            f"({time.strftime('%Y-%m-%d %H:%M', time.localtime(known_wake_target))} lokal). "
            "Diese Session darf pruefen, ob wieder Guthaben verfuegbar ist "
            "(Bridge-Datei ~/.claude/state/token_budget.json). Ist das "
            "Guthaben wieder da, Abschnitt 'Aufheben' aus Skill notaus "
            f"ausfuehren (Rueckkehr zu Modus '{prior_mode}') statt den Zustand "
            "zu ignorieren."
        )
    else:
        wake_hint = (
            f"geplantes Aufwachen um {time.strftime('%Y-%m-%d %H:%M', time.localtime(known_wake_target))} lokal"
            if isinstance(known_wake_target, (int, float))
            else "kein bekannter Reset-Zeitpunkt -> nur der Leader weckt sich alle 5h kurz"
        )
        msg = (
            f"NOTAUS AKTIV seit {set_at or '?'} ({reason or 'Grund nicht vermerkt'}), "
            f"vorheriger Modus '{prior_mode}'. {wake_hint}. Diese Session sollte "
            "GEPARKT bleiben: keine neue Arbeit beginnen, laufende Delegationen "
            "nicht erweitern, nur den Zustand pruefen und ggf. auf das naechste "
            "Aufwachfenster verweisen. Details: Skill 'notaus'."
        )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": msg,
        }
    }))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        pass  # Fail-open: darf den Sessionstart niemals blockieren
    raise SystemExit(0)
