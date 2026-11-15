#!/usr/bin/env python3
"""UserPromptSubmit-Hook: liest den Bridge-Snapshot von
token_budget_statusline.py und faehrt das Sparmodus-System (Ticket
T-20260824-552689035, -733240216, -643372292, T-20261115-791506015).

MODUS-FELD (~/.claude/state/sparmodus_state.json, EINZIGE Zustandsdatei
fuer das gesamte System -- keine Parallel-Standards):
  mode: "off" | "manual-spar" | "auto-spar" | "notaus"

VERHALTEN JE MODUS:
- "off": rein ADVISORY. Der Hook meldet Stufenuebergaenge (Kurztext ab
  `kurztext_used_pct`, Hinweis auf /spar bzw. /notaus ab `sparmodus_used_pct`
  bzw. `notaus_used_pct`), veraendert den Modus aber NICHT selbst.
- "auto-spar": kontinuierliche Ueberwachung, vom User per /auto-spar on
  bewusst fuer die restliche Session bewaffnet. Bleibt bei Erholung AUF
  "auto-spar" (bewaffnet, nur aktuell ruhig) -- schaltet nur nach "notaus"
  hoch und von dort wieder zurueck auf "auto-spar", nie von selbst auf "off".
- "manual-spar": per /spar on EINMALIG manuell ausgeloest. Von hier aus
  automatische Eskalation nach "notaus" bei Erreichen der Notaus-Schwelle,
  automatisches Ende (zurueck auf "off") nur bei voller Erholung BEIDER Fenster
  (5h und 7d auf Stufe 0).
- "notaus": haelt IMMER `prior_mode` (was vor der Eskalation aktiv war:
  "off" -- bei direktem manuellen /notaus --, "manual-spar" oder
  "auto-spar"). Bei Erholung automatische Rueckkehr zu `prior_mode` (oder "off"
  falls keiner vermerkt; bleibt Stufe 2 durch das Wochenfenster aktiv, faellt
  er mindestens auf "manual-spar").

ZWEI-FENSTER-STUFENLOGIK (Ticket T-20261115-791506015):
- Jedes Fenster (5h und 7d) wird gegen seine eigenen Schwellen geprueft.
- Massgeblich fuer die Gesamtstufe ist `max(stage_5h, stage_7d)`.
- Fehlende Fenster (z.B. five_hour = None) werden als Stufe 0 gewertet,
  ohne das andere Fenster zu verdecken.
- Meldungstexte benennen wahrheitsgemaess das ausloesende Fenster
  (5h-Session-Limit vs. 7d-Wochenlimit vs. beide Fenster).

Schwellen konfigurierbar ueber ~/.claude/hooks/token_budget_config.json
(Fail-open: Datei/Feld fehlt oder ungueltig -> hartcodierter Default unten).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from typing import Any

STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "state")
HOOKS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
BRIDGE_PATH = os.path.join(STATE_DIR, "token_budget.json")
GUARD_STATE_PATH = os.path.join(STATE_DIR, "token_budget_guard_state.json")
SPARMODUS_STATE_PATH = os.path.join(STATE_DIR, "sparmodus_state.json")
CONFIG_PATH = os.path.join(HOOKS_DIR, "token_budget_config.json")

DEFAULT_THRESHOLDS = {
    "kurztext_used_pct": 50.0,
    "sparmodus_used_pct": 80.0,
    "notaus_used_pct": 90.0,
}
# Wochenfenster (seven_day) mit eigenen Schwellen (T-20261115-791506015):
# Sparmodus ab 80 % Wochenverbrauch (<=20 % Rest), Notaus ab 97 % (<=3 % Rest, [U 2026-10-13]).
DEFAULT_WEEKLY_THRESHOLDS = {
    "kurztext_used_pct": 80.0,
    "sparmodus_used_pct": 80.0,
    "notaus_used_pct": 97.0,
}
DEFAULT_STALE_AFTER_SECONDS = 30 * 60
DEFAULT_REMIND_EVERY_N_PROMPTS = 20
MAX_PARK_AGE_SECONDS = 24 * 3600  # Altlasten aelter als 24h gelten als verwaist

FIVE_HOUR_SECONDS = 5 * 60 * 60


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


def _load_thresholds() -> tuple[dict, int, int]:
    cfg = _read_json(CONFIG_PATH)
    thresholds = dict(DEFAULT_THRESHOLDS)
    raw_thresholds = cfg.get("thresholds") if isinstance(cfg.get("thresholds"), dict) else {}
    for key in DEFAULT_THRESHOLDS:
        value = raw_thresholds.get(key)
        try:
            if value is not None:
                thresholds[key] = float(value)
        except (TypeError, ValueError):
            pass  # ungueltiger Wert -> Default bleibt bestehen (fail-open)

    stale_after = DEFAULT_STALE_AFTER_SECONDS
    try:
        raw_stale = cfg.get("stale_after_seconds")
        if raw_stale is not None:
            stale_after = int(raw_stale)
    except (TypeError, ValueError):
        pass

    remind_every = DEFAULT_REMIND_EVERY_N_PROMPTS
    try:
        raw_remind = cfg.get("remind_every_n_prompts")
        if raw_remind is not None:
            remind_every = int(raw_remind)
    except (TypeError, ValueError):
        pass

    return thresholds, stale_after, remind_every


def _load_weekly_thresholds() -> dict:
    """Schwellen fuer das Wochenfenster aus `thresholds_seven_day` (fail-open auf Defaults)."""
    cfg = _read_json(CONFIG_PATH)
    weekly = dict(DEFAULT_WEEKLY_THRESHOLDS)
    raw = cfg.get("thresholds_seven_day") if isinstance(cfg.get("thresholds_seven_day"), dict) else {}
    for key in DEFAULT_WEEKLY_THRESHOLDS:
        try:
            if raw.get(key) is not None:
                weekly[key] = float(raw[key])
        except (TypeError, ValueError):
            pass
    return weekly


def _stage_for(used_pct: float, thresholds: dict) -> int:
    if used_pct >= thresholds["notaus_used_pct"]:
        return 3
    if used_pct >= thresholds["sparmodus_used_pct"]:
        return 2
    if used_pct >= thresholds["kurztext_used_pct"]:
        return 1
    return 0


def _default_sparmodus_state() -> dict:
    return {
        "mode": "off",
        "prior_mode": None,
        "set_at": None,
        "set_by": None,
        "reason": None,
        "wake_at": None,
        "resets_at": None,
        "leader_only": None,
    }


def _preserve_park_fields(previous: dict, current: dict) -> dict:
    """Carry the notaus ownership markers across an automatic state reset."""
    for key in ("paused_goals", "paused_agents"):
        if key in previous:
            current[key] = previous[key]
    return current


def _pending_resume_hint(
    state: dict,
    current_session_id: str | None = None,
    now: float | None = None,
) -> str:
    """Beschreibt geparkte Worker mit Session-Bindung und Altlasten-Schutz.

    Filterkriterien (T-20261115-791506015):
    - Bereits reaktivierte Worker (resumed_at gesetzt) werden ignoriert.
    - Fremde Worker (session_id != current_session_id) blockieren fremde Sitzungen nicht.
    - Verwaiste Altlasten ohne session_id oder aelter als MAX_PARK_AGE_SECONDS
      werden in neuen Sitzungen nicht als offener Parkkreis gemeldet.
    """
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


def _format_advisory_message(
    stage: int,
    stage_5h: int,
    stage_7d: int,
    used_5h: float | None,
    used_7d: float | None,
    thresholds: dict,
    weekly_thresholds: dict,
) -> str:
    """Erzeugt wahrheitsgemaesse Advisory-Meldungen ohne Falschbenennung des Fensters."""
    if stage == 1:
        if stage_7d >= 1 and stage_5h < 1:
            val_str = f"{used_7d:.0f}%" if used_7d is not None else ""
            desc = f"7d-Wochenlimit >= {weekly_thresholds['kurztext_used_pct']:.0f}% verbraucht ({val_str})"
        elif stage_5h >= 1 and stage_7d < 1:
            val_str = f"{used_5h:.0f}%" if used_5h is not None else ""
            desc = f"5h-Session-Limit >= {thresholds['kurztext_used_pct']:.0f}% verbraucht ({val_str})"
        else:
            desc = f"5h-Session-Limit ({used_5h:.0f}%) und 7d-Wochenlimit ({used_7d:.0f}%) >= Kurztext-Schwelle verbraucht"
        return (
            f"TOKEN-BUDGET STUFE 1 (Kurztext, Modus 'off'): {desc}. "
            "Kurze, knappe Antworten (siehe Skill knappform); keine neuen grossen Initiativen ohne Notwendigkeit."
        )
    elif stage == 2:
        if stage_7d >= 2 and stage_5h < 2:
            rem = max(0.0, 100.0 - (used_7d if used_7d is not None else weekly_thresholds["sparmodus_used_pct"]))
            val_str = f"{used_7d:.0f}%" if used_7d is not None else ""
            desc = f"7d-Wochenlimit >= {weekly_thresholds['sparmodus_used_pct']:.0f}% verbraucht ({val_str}, <={rem:.0f}% verbleibend)"
        elif stage_5h >= 2 and stage_7d < 2:
            rem = max(0.0, 100.0 - (used_5h if used_5h is not None else thresholds["sparmodus_used_pct"]))
            val_str = f"{used_5h:.0f}%" if used_5h is not None else ""
            desc = f"5h-Session-Limit >= {thresholds['sparmodus_used_pct']:.0f}% verbraucht ({val_str}, <={rem:.0f}% verbleibend)"
        else:
            desc = f"5h-Session-Limit ({used_5h:.0f}%) und 7d-Wochenlimit ({used_7d:.0f}%) >= Spar-Schwelle verbraucht"
        return (
            f"TOKEN-BUDGET STUFE 2 (Modus 'off'): {desc}. "
            "Fuehre jetzt /spar aus (Skill sparmodus), falls noch nicht aktiv, "
            "oder /auto-spar fuer dauerhafte automatische Ueberwachung."
        )
    elif stage == 3:
        if stage_7d >= 3 and stage_5h < 3:
            rem = max(0.0, 100.0 - (used_7d if used_7d is not None else weekly_thresholds["notaus_used_pct"]))
            val_str = f"{used_7d:.0f}%" if used_7d is not None else ""
            desc = f"7d-Wochenlimit >= {weekly_thresholds['notaus_used_pct']:.0f}% verbraucht ({val_str}, <={rem:.0f}% verbleibend)"
        elif stage_5h >= 3 and stage_7d < 3:
            rem = max(0.0, 100.0 - (used_5h if used_5h is not None else thresholds["notaus_used_pct"]))
            val_str = f"{used_5h:.0f}%" if used_5h is not None else ""
            desc = f"5h-Session-Limit >= {thresholds['notaus_used_pct']:.0f}% verbraucht ({val_str}, <={rem:.0f}% verbleibend)"
        else:
            desc = f"5h-Session-Limit ({used_5h:.0f}%) und 7d-Wochenlimit ({used_7d:.0f}%) >= Notaus-Schwelle verbraucht"
        return (
            f"TOKEN-BUDGET STUFE 3 (Modus 'off'): {desc}. "
            "Fuehre JETZT /notaus aus (Skill notaus): USMC-State sichern, laufende "
            "Teammates in Wartestellung versetzen, Aufwachzeit festlegen."
        )
    return ""


def _stands_summary(used_5h: float | None, used_7d: float | None) -> str:
    parts = []
    if used_5h is not None:
        parts.append(f"5h-Stand {used_5h:.0f}%")
    if used_7d is not None:
        parts.append(f"Wochen-Stand {used_7d:.0f}%")
    return ", ".join(parts) if parts else "Limits unbekannt"


def _compute_transition(
    mode: str,
    stage: int,
    *,
    five_hour_stage: int | None = None,
    seven_day_stage: int | None = None,
    sparmodus_state: dict | None = None,
    now: float | None = None,
) -> str | None:
    """Liefert den neuen Modus, oder None wenn keine Modusaenderung ansteht."""
    if mode == "off":
        return None  # rein advisory, keine Selbstschaltung
    if mode in ("auto-spar", "manual-spar"):
        if stage == 3:
            return "notaus"
        if mode == "manual-spar":
            # Automatisches Ende von manual-spar nur wenn stage == 0 (BEIDE Fenster erholt!)
            if stage == 0:
                return "off"
        return None  # auto-spar bleibt bewaffnet; manual-spar bei Stufe 1/2 unveraendert
    if mode == "notaus":
        if stage == 3:
            return None
        # Das 5h-Fenster gilt erst bei Stufe 0 (< kurztext_used_pct) als erholt.
        if five_hour_stage is not None and five_hour_stage > 0:
            return None
        if isinstance(sparmodus_state, dict) and sparmodus_state.get("set_by") == "user":
            wake_at = sparmodus_state.get("wake_at")
            current_now = time.time() if now is None else now
            if (
                isinstance(wake_at, (int, float))
                and not isinstance(wake_at, bool)
                and current_now < float(wake_at)
                and (five_hour_stage is None or stage > 0)
            ):
                return None
        if stage < 3:
            return "__RECOVER__"  # Ziel aus prior_mode; Stufe 2 (Woche) haelt mindestens Sparmodus
        return None
    return None


def main() -> int:
    _ensure_utf8_stdio()
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}
    session_id = str(payload.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or "unknown")

    thresholds, stale_after, remind_every = _load_thresholds()
    weekly_thresholds = _load_weekly_thresholds()

    bridge = _read_json(BRIDGE_PATH)
    written_at = bridge.get("written_at")
    if not isinstance(written_at, (int, float)):
        return 0  # keine lesbare Bridge-Datei -> stumm, kein Stand behauptet, kein Modus geaendert
    if time.time() - float(written_at) > stale_after:
        return 0  # veralteter Snapshot -> stumm statt Annahme

    five_hour_entry = bridge.get("five_hour") or {}
    seven_day_entry = bridge.get("seven_day") or {}
    raw_5h = five_hour_entry.get("used_percentage")
    raw_7d = seven_day_entry.get("used_percentage")

    used_5h = float(raw_5h) if isinstance(raw_5h, (int, float)) and not isinstance(raw_5h, bool) else None
    used_7d = float(raw_7d) if isinstance(raw_7d, (int, float)) and not isinstance(raw_7d, bool) else None

    if used_5h is None and used_7d is None:
        return 0  # Konto ohne rate_limits-Feld (kein Pro/Max) -> stumm

    five_hour_stage_raw = _stage_for(used_5h, thresholds) if used_5h is not None else None
    stage_5h = five_hour_stage_raw if five_hour_stage_raw is not None else 0
    stage_7d = _stage_for(used_7d, weekly_thresholds) if used_7d is not None else 0
    stage = max(stage_5h, stage_7d)

    resets_5h = five_hour_entry.get("resets_at")
    resets_7d = seven_day_entry.get("resets_at")
    if stage_7d > stage_5h:
        resets_at = resets_7d
    elif stage_5h > stage_7d:
        resets_at = resets_5h
    else:
        resets_at = resets_7d or resets_5h

    stands_summary = _stands_summary(used_5h, used_7d)

    sparmodus_state = _read_json(SPARMODUS_STATE_PATH)
    if not sparmodus_state or "mode" not in sparmodus_state:
        sparmodus_state = _default_sparmodus_state()
    mode = sparmodus_state.get("mode") or "off"

    guard_state = _read_json(GUARD_STATE_PATH)
    per_session: dict[str, Any] = guard_state.get("sessions") or {}
    entry = per_session.get(session_id) or {"last_stage": 0, "last_mode": "off", "prompt_count": 0}
    last_stage = int(entry.get("last_stage", 0))
    prompt_count = int(entry.get("prompt_count", 0)) + 1

    message = None

    if mode == "off":
        if stage in (1, 2, 3) and stage != last_stage:
            message = _format_advisory_message(
                stage, stage_5h, stage_7d, used_5h, used_7d, thresholds, weekly_thresholds
            )
            prompt_count = 0
        elif stage >= 1 and prompt_count >= remind_every:
            message = _format_advisory_message(
                stage, stage_5h, stage_7d, used_5h, used_7d, thresholds, weekly_thresholds
            )
            prompt_count = 0
    else:
        target = _compute_transition(
            mode,
            stage,
            five_hour_stage=five_hour_stage_raw,
            seven_day_stage=stage_7d,
            sparmodus_state=sparmodus_state,
        )
        if target is not None:
            previous_sparmodus_state = sparmodus_state
            if target == "__RECOVER__":
                recover_to = sparmodus_state.get("prior_mode") or "off"
                if stage == 2 and recover_to == "off":
                    recover_to = "manual-spar"  # Sparschwelle noch erreicht: nur der Notaus faellt
                recover_label = "erholt" if stage == 0 else "unter Notaus-Schwelle"
                sparmodus_state = _preserve_park_fields(previous_sparmodus_state, {
                    "mode": recover_to,
                    "prior_mode": None,
                    "set_at": time.strftime("%Y-%m-%d %H:%M"),
                    "set_by": "hook",
                    "reason": f"Automatische Rueckkehr aus notaus, {stands_summary} ({recover_label})",
                    "wake_at": None,
                    "resets_at": None,
                    "leader_only": None,
                })
                pending_hint = _pending_resume_hint(sparmodus_state, current_session_id=session_id)
                message = (
                    f"AUTOMATISCHE RUECKKEHR aus NOTAUS ({stands_summary}, "
                    f"{recover_label}) -> neuer Modus '{recover_to}'. Fuehre JETZT Abschnitt "
                    "'Aufheben' aus Skill notaus aus: notaus_state-Vermerk ist "
                    "bereits gesetzt, aber USMC-RESUME lesen+fortschreiben, "
                    "erreichbare Teammates per SendMessage reaktivieren und "
                    "Normalbetrieb an den User melden bleiben Aufgabe dieser "
                    f"Session.{pending_hint}"
                )
            elif target == "notaus":
                wake_at = float(resets_at) if isinstance(resets_at, (int, float)) and resets_at else time.time() + FIVE_HOUR_SECONDS
                leader_only = not (isinstance(resets_at, (int, float)) and resets_at)
                sparmodus_state = _preserve_park_fields(previous_sparmodus_state, {
                    "mode": "notaus",
                    "prior_mode": mode,
                    "set_at": time.strftime("%Y-%m-%d %H:%M"),
                    "set_by": "hook",
                    "reason": f"Automatische Eskalation aus '{mode}', {stands_summary}",
                    "wake_at": wake_at,
                    "resets_at": resets_at if isinstance(resets_at, (int, float)) else None,
                    "leader_only": leader_only,
                })
                wake_hint = (
                    f"Aufwachen um {time.strftime('%Y-%m-%d %H:%M', time.localtime(wake_at))} lokal"
                    if not leader_only
                    else "kein bekannter Reset-Zeitpunkt -> 5h-Leader-Ping"
                )
                message = (
                    f"AUTOMATISCHE ESKALATION -> NOTAUS ({stands_summary}, "
                    f"aus Modus '{mode}'). {wake_hint}. Fuehre JETZT Ablauf 1.-3. "
                    "aus Skill notaus aus: USMC-State sichern, erreichbare "
                    "Teammates per SendMessage parken, Aufwachbedingung ist im "
                    "State bereits gesetzt."
                )
            elif target == "off":
                sparmodus_state = _preserve_park_fields(
                    previous_sparmodus_state, _default_sparmodus_state()
                )
                sparmodus_state["set_at"] = time.strftime("%Y-%m-%d %H:%M")
                sparmodus_state["set_by"] = "hook"
                sparmodus_state["reason"] = f"Automatisches Ende manual-spar, {stands_summary} (erholt)"
                message = (
                    f"AUTOMATISCHES ENDE Sparmodus ({stands_summary}, "
                    "erholt) -> Modus 'off'. session_override in "
                    "orchestrator/config.json zuruecksetzen, sofern gesetzt."
                )
            _atomic_write_json(SPARMODUS_STATE_PATH, sparmodus_state)
            mode = sparmodus_state["mode"]
        elif stage != last_stage or (stage >= 1 and prompt_count >= remind_every):
            message = (
                f"Sparmodus-System aktiv (Modus '{mode}'), {stands_summary}. "
                "Keine Modusaenderung noetig."
            )
            prompt_count = 0

    entry = {
        "last_stage": stage,
        "last_mode": mode,
        "prompt_count": prompt_count,
        "updated_at": time.time(),
    }
    per_session[session_id] = entry
    guard_state["sessions"] = per_session
    _atomic_write_json(GUARD_STATE_PATH, guard_state)

    if message:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": message,
            }
        }))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        pass  # Fail-open: dieser Hook darf den Prompt niemals blockieren
    raise SystemExit(0)
