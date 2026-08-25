#!/usr/bin/env python3
"""UserPromptSubmit-Hook: liest den Bridge-Snapshot von
token_budget_statusline.py und faehrt das Sparmodus-System (Ticket
T-20260824-552689035, -733240216, -643372292).

MODUS-FELD (~/.claude/state/sparmodus_state.json, EINZIGE Zustandsdatei
fuer das gesamte System -- keine Parallel-Standards):
  mode: "off" | "manual-spar" | "auto-spar" | "notaus"

VERHALTEN JE MODUS:
- "off": rein ADVISORY. Der Hook meldet Stufenuebergaenge (Kurztext ab
  `kurztext_used_pct`, Hinweis auf /spar bzw. /notaus ab `sparmodus_used_pct`
  bzw. `notaus_used_pct`), veraendert den Modus aber NICHT selbst. Das ist
  der Ausgangszustand und entspricht T-20260824-552689035/-733240216.
- "auto-spar": kontinuierliche Ueberwachung, vom User per /auto-spar on
  bewusst fuer die restliche Session bewaffnet. Bleibt bei Erholung AUF
  "auto-spar" (bewaffnet, nur aktuell ruhig) -- schaltet nur nach "notaus"
  hoch und von dort wieder zurueck auf "auto-spar", nie von selbst auf "off".
- "manual-spar": per /spar on EINMALIG manuell ausgeloest. Von hier aus
  automatische Eskalation nach "notaus" bei Erreichen der Notaus-Schwelle,
  automatisches Ende (zurueck auf "off") bei voller Erholung (Stufe 0).
- "notaus": haelt IMMER `prior_mode` (was vor der Eskalation aktiv war:
  "off" -- bei direktem manuellen /notaus --, "manual-spar" oder
  "auto-spar"). Bei voller Erholung (Stufe 0) automatische Rueckkehr zu
  `prior_mode` (oder "off" falls keiner vermerkt) -- das entspricht
  Abschnitt "Aufheben" in notaus/SKILL.md. Der Hook flippt dabei NUR den
  State und `wake_at`/`resets_at`; die eigentlichen Aufheben-Schritte (USMC-
  RESUME lesen/fortschreiben, Teammates per SendMessage reaktivieren,
  Normalbetrieb melden) sind Sache des Agenten -- ein Hook kann keine
  LLM-Tools aufrufen. Der Hook liefert dafuer eine klare Anweisung als
  `additionalContext`.

Stufe 1 (Kurztext) bleibt IMMER rein informativ (kein Modus-Feld dafuer) --
in "manual-spar"/"auto-spar"/"notaus" ist Kurztext ohnehin Teil des jeweiligen
Skills, daher wird die separate Kurztext-Meldung dort unterdrueckt (keine
widerspruechliche Doppelmeldung).

Schwellen konfigurierbar ueber ~/.claude/hooks/token_budget_config.json
(Fail-open: Datei/Feld fehlt oder ungueltig -> hartcodierter Default unten).

WICHTIGER VORBEHALT (unveraendert seit T-20260824-552689035): Dieser Hook
kann den Limit-Stand NICHT selbst lesen -- kein Hook-Event traegt Token-/
Kostenfelder. Er liest ausschliesslich die Bridge-Datei, die eine
interaktive Statusline-Session zuletzt geschrieben hat. Fehlt/ist sie
veraltet, bleibt dieser Hook STUMM (fail-open) und veraendert KEINEN Modus --
der garantierte, hiervon unabhaengige Weg bleiben die manuellen Aufrufe
/spar, /auto-spar, /notaus (User-Vorgabe 2026-08-24).
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
DEFAULT_STALE_AFTER_SECONDS = 30 * 60
DEFAULT_REMIND_EVERY_N_PROMPTS = 20

FIVE_HOUR_SECONDS = 5 * 60 * 60

ADVISORY_MESSAGES = {
    1: (
        "TOKEN-BUDGET STUFE 1 (Kurztext, Modus 'off'): 5h-Session-Limit >= "
        "{kurztext:.0f}% verbraucht. Kurze, knappe Antworten (siehe Skill "
        "knappform); keine neuen grossen Initiativen ohne Notwendigkeit."
    ),
    2: (
        "TOKEN-BUDGET STUFE 2 (Modus 'off'): 5h-Session-Limit >= "
        "{sparmodus:.0f}% verbraucht (<={remaining2:.0f}% verbleibend). "
        "Fuehre jetzt /spar aus (Skill sparmodus), falls noch nicht aktiv, "
        "oder /auto-spar fuer dauerhafte automatische Ueberwachung."
    ),
    3: (
        "TOKEN-BUDGET STUFE 3 (Modus 'off'): 5h-Session-Limit >= "
        "{notaus:.0f}% verbraucht (<={remaining3:.0f}% verbleibend). Fuehre "
        "JETZT /notaus aus (Skill notaus): USMC-State sichern, laufende "
        "Teammates in Wartestellung versetzen, Aufwachzeit festlegen."
    ),
}


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


def _compute_transition(mode: str, stage: int) -> str | None:
    """Liefert den neuen Modus, oder None wenn keine Modusaenderung ansteht."""
    if mode == "off":
        return None  # rein advisory, keine Selbstschaltung
    if mode in ("auto-spar", "manual-spar"):
        if stage == 3:
            return "notaus"
        if mode == "manual-spar" and stage == 0:
            return "off"  # Auto-Ende bei voller Erholung
        return None  # auto-spar bleibt bewaffnet; manual-spar bei Stufe 1/2 unveraendert
    if mode == "notaus":
        if stage == 0:
            return "__RECOVER__"  # Ziel wird aus prior_mode aufgeloest
        return None
    return None


def main() -> int:
    _ensure_utf8_stdio()
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}
    session_id = str(payload.get("session_id") or "unknown")

    thresholds, stale_after, remind_every = _load_thresholds()

    bridge = _read_json(BRIDGE_PATH)
    written_at = bridge.get("written_at")
    if not isinstance(written_at, (int, float)):
        return 0  # keine lesbare Bridge-Datei -> stumm, kein Stand behauptet, kein Modus geaendert
    if time.time() - float(written_at) > stale_after:
        return 0  # veralteter Snapshot -> stumm statt Annahme

    used_pct = ((bridge.get("five_hour") or {}).get("used_percentage"))
    resets_at = ((bridge.get("five_hour") or {}).get("resets_at"))
    if used_pct is None:
        used_pct = ((bridge.get("seven_day") or {}).get("used_percentage"))
        resets_at = ((bridge.get("seven_day") or {}).get("resets_at"))
    if used_pct is None:
        return 0  # Konto ohne rate_limits-Feld (kein Pro/Max) -> stumm

    try:
        used_pct = float(used_pct)
    except (TypeError, ValueError):
        return 0

    stage = _stage_for(used_pct, thresholds)
    remaining2 = max(0.0, 100.0 - thresholds["sparmodus_used_pct"])
    remaining3 = max(0.0, 100.0 - thresholds["notaus_used_pct"])

    sparmodus_state = _read_json(SPARMODUS_STATE_PATH)
    if not sparmodus_state or "mode" not in sparmodus_state:
        sparmodus_state = _default_sparmodus_state()
    mode = sparmodus_state.get("mode") or "off"

    guard_state = _read_json(GUARD_STATE_PATH)
    per_session: dict[str, Any] = guard_state.get("sessions") or {}
    entry = per_session.get(session_id) or {"last_stage": 0, "last_mode": "off", "prompt_count": 0}
    last_stage = int(entry.get("last_stage", 0))
    last_mode = entry.get("last_mode", "off")
    prompt_count = int(entry.get("prompt_count", 0)) + 1

    message = None

    if mode == "off":
        # Reiner Advisory-Pfad (unveraendert seit T-20260824-552689035/-733240216).
        if stage in (2, 3) and stage != last_stage:
            template = ADVISORY_MESSAGES[stage]
            message = template.format(
                kurztext=thresholds["kurztext_used_pct"],
                sparmodus=thresholds["sparmodus_used_pct"],
                notaus=thresholds["notaus_used_pct"],
                remaining2=remaining2,
                remaining3=remaining3,
            )
            prompt_count = 0
        elif stage == 1 and stage != last_stage:
            message = ADVISORY_MESSAGES[1].format(kurztext=thresholds["kurztext_used_pct"])
            prompt_count = 0
        elif stage >= 1 and prompt_count >= remind_every:
            template = ADVISORY_MESSAGES.get(stage, ADVISORY_MESSAGES[1])
            message = template.format(
                kurztext=thresholds["kurztext_used_pct"],
                sparmodus=thresholds["sparmodus_used_pct"],
                notaus=thresholds["notaus_used_pct"],
                remaining2=remaining2,
                remaining3=remaining3,
            )
            prompt_count = 0
    else:
        # Aktive Ueberwachung: der Hook darf den Modus selbst schalten.
        target = _compute_transition(mode, stage)
        if target is not None:
            if target == "__RECOVER__":
                recover_to = sparmodus_state.get("prior_mode") or "off"
                sparmodus_state = {
                    "mode": recover_to,
                    "prior_mode": None,
                    "set_at": time.strftime("%Y-%m-%d %H:%M"),
                    "set_by": "hook",
                    "reason": f"Automatische Rueckkehr aus notaus, 5h-Stand {used_pct:.0f}% (erholt)",
                    "wake_at": None,
                    "resets_at": None,
                    "leader_only": None,
                }
                message = (
                    f"AUTOMATISCHE RUECKKEHR aus NOTAUS (5h-Stand {used_pct:.0f}%, "
                    f"erholt) -> neuer Modus '{recover_to}'. Fuehre JETZT Abschnitt "
                    "'Aufheben' aus Skill notaus aus: notaus_state-Vermerk ist "
                    "bereits gesetzt, aber USMC-RESUME lesen+fortschreiben, "
                    "erreichbare Teammates per SendMessage reaktivieren und "
                    "Normalbetrieb an den User melden bleiben Aufgabe dieser "
                    "Session."
                )
            elif target == "notaus":
                wake_at = float(resets_at) if isinstance(resets_at, (int, float)) and resets_at else time.time() + FIVE_HOUR_SECONDS
                leader_only = not (isinstance(resets_at, (int, float)) and resets_at)
                sparmodus_state = {
                    "mode": "notaus",
                    "prior_mode": mode,
                    "set_at": time.strftime("%Y-%m-%d %H:%M"),
                    "set_by": "hook",
                    "reason": f"Automatische Eskalation aus '{mode}', 5h-Stand {used_pct:.0f}%",
                    "wake_at": wake_at,
                    "resets_at": resets_at if isinstance(resets_at, (int, float)) else None,
                    "leader_only": leader_only,
                }
                wake_hint = (
                    f"Aufwachen um {time.strftime('%Y-%m-%d %H:%M', time.localtime(wake_at))} lokal"
                    if not leader_only
                    else "kein bekannter Reset-Zeitpunkt -> 5h-Leader-Ping"
                )
                message = (
                    f"AUTOMATISCHE ESKALATION -> NOTAUS (5h-Stand {used_pct:.0f}%, "
                    f"aus Modus '{mode}'). {wake_hint}. Fuehre JETZT Ablauf 1.-3. "
                    "aus Skill notaus aus: USMC-State sichern, erreichbare "
                    "Teammates per SendMessage parken, Aufwachbedingung ist im "
                    "State bereits gesetzt."
                )
            elif target == "off":
                sparmodus_state = _default_sparmodus_state()
                sparmodus_state["set_at"] = time.strftime("%Y-%m-%d %H:%M")
                sparmodus_state["set_by"] = "hook"
                sparmodus_state["reason"] = f"Automatisches Ende manual-spar, 5h-Stand {used_pct:.0f}% (erholt)"
                message = (
                    f"AUTOMATISCHES ENDE Sparmodus (5h-Stand {used_pct:.0f}%, "
                    "erholt) -> Modus 'off'. session_override in "
                    "orchestrator/config.json zuruecksetzen, sofern gesetzt."
                )
            _atomic_write_json(SPARMODUS_STATE_PATH, sparmodus_state)
            mode = sparmodus_state["mode"]
        elif stage != last_stage or (stage >= 1 and prompt_count >= remind_every):
            # Kein Modus-Uebergang, aber sichtbarer Stufenwechsel innerhalb des
            # aktiven Modus -- kurzer Statushinweis, keine Kurztext-Doppelmeldung.
            message = (
                f"Sparmodus-System aktiv (Modus '{mode}'), 5h-Stand {used_pct:.0f}%. "
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
