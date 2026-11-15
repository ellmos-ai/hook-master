#!/usr/bin/env python3
"""SessionStart-Hook: prueft beim Start JEDER neuen Session/Subagenten-Session,
ob der Sparmodus-System-Zustand (~/.claude/state/sparmodus_state.json,
Feld `mode`) auf "notaus" steht, und ob die dort festgelegte Aufwachbedingung
erfuellt ist.

Zustandsdatei: ~/.claude/state/sparmodus_state.json (mode: off | manual-spar | auto-spar | notaus).

Aufwachlogik (siehe Skill notaus/SKILL.md):
- Ist ein Reset-Zeitpunkt bekannt (`resets_at`), gilt: vor `wake_at` bleibt JEDE
  neue Session geparkt (nur State pruefen, keine neue Arbeit beginnen).
- Ist kein Reset-Zeitpunkt bekannt (`leader_only: true`), gilt die
  5-Stunden-Leader-Ping-Regel: nur eine als Leader verstandene Session
  wacht alle 5h kurz auf und prueft, ob wieder Guthaben da ist.
- Ist der Zustand nicht lesbar, nicht vorhanden, oder `mode` != "notaus",
  greift dieser Hook NICHT ein (fail-open) -- normale Sessionstart-Verarbeitung laeuft weiter.
  Gibt es allerdings fuer die aktuelle Session noch offene geparkte Worker, wird
  die Aufhebung erinnert.

Altlasten- und Sitzungsschutz (Ticket T-20261115-791506015):
- Geparkte Worker fremder Sitzungen oder verwaiste Altlasten (> 24h / ohne session_id)
  blockieren fremde, neu startende Sitzungen NICHT mehr mit irrefuehrenden Hinweisen.
"""

from __future__ import annotations

import json
import os
import sys
import time

STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "state")
SPARMODUS_STATE_PATH = os.path.join(STATE_DIR, "sparmodus_state.json")
MAX_PARK_AGE_SECONDS = 24 * 3600  # 24 Stunden


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


def _pending_resume_hint(
    state: dict,
    current_session_id: str | None = None,
    now: float | None = None,
) -> str:
    """Beschreibt geparkte Worker mit Session-Bindung und Altlasten-Schutz."""
    parts = []
    goals = state.get("paused_goals")
    agents = state.get("paused_agents")
    if isinstance(goals, list) and goals:
        parts.append(f"{len(goals)} pausierte Goals")
    elif isinstance(goals, dict) and goals:
        parts.append("erhaltener Goal-Parkvermerk")

    if isinstance(agents, list) and agents:
        parts.append(f"{len(agents)} geparkte Worker")
    elif isinstance(agents, dict):
        cur_now = time.time() if now is None else now
        pending = []
        for name, entry in agents.items():
            if not isinstance(entry, dict) or entry.get("resumed_at"):
                continue
            entry_sid = entry.get("session_id")
            parked_at = entry.get("parked_at")
            is_stale = False
            if isinstance(parked_at, (int, float)) and not isinstance(parked_at, bool):
                if cur_now - float(parked_at) > MAX_PARK_AGE_SECONDS:
                    is_stale = True

            if current_session_id and current_session_id != "unknown":
                if entry_sid == current_session_id:
                    pending.append(name)
            else:
                if not is_stale:
                    pending.append(name)

        if pending:
            parts.append(f"{len(pending)} geparkte Worker")

    if not parts:
        return ""
    return " Aufhebung ausstehend (" + ", ".join(parts) + "); zuerst den vollständigen Parkkreis reaktivieren."


def main() -> int:
    _ensure_utf8_stdio()
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}
    session_id = str(payload.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or "unknown")

    state = _read_json(SPARMODUS_STATE_PATH)
    if state.get("mode") != "notaus":
        pending = _pending_resume_hint(state, current_session_id=session_id)
        if pending:
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": pending.strip(),
                }
            }))
        return 0

    now = time.time()
    wake_at = state.get("wake_at")
    resets_at = state.get("resets_at")
    reason = state.get("reason", "")
    set_at = state.get("set_at")
    prior_mode = state.get("prior_mode") or "off"
    pending_hint = _pending_resume_hint(state, current_session_id=session_id)

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
            + pending_hint
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
            + pending_hint
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
