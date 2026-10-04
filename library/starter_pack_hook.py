#!/usr/bin/env python3
"""SessionStart-Hook: injiziert das Starter-Pack-Rezept + Einstiegs-Skills.

Begleitet den Skill `starter-pack-hook-creator` (Repo `ellmos-ai/skills`). Neue Sessions
sollen die wichtigsten Skills KENNEN und GEZIELT LADEN -- ein Skill wird nicht
automatisch voll geladen, nur seine Beschreibung steht im Kontext. Dieser Hook
gibt deshalb ein kurzes Rezept (Entscheidungsbaum: wann welche Skill-Kategorie)
plus je Kategorie hoechstens drei Einstiegs-Skills aus einem Profil aus.

Profilkette (Reihenfolge wirkt wie eine Ueberlagerung, spaeter gewinnt):
    1. Umgebungsvariable STARTER_PACK_PROFILE (kommasepariert, z. B. "ellmos,private")
    2. Datei ~/.claude/starter-pack.profile (eine Zeile, kommasepariert)
    3. Default: "ellmos"

Profile liegen im DEPLOYTEN Skill-Ordner
    ~/.claude/skills/starter-pack-hook-creator/profiles/<name>.json
Fehlt ein Profil der Kette, wird es stillschweigend uebersprungen (fail-open) --
das ist der Normalfall auf einem frischen Host ohne private Profilschicht.

Kategorien werden ueber ihre `id` gemischt: ein spaeteres Profil ERSETZT eine
Kategorie vollstaendig (keine Addition), ein neuer `id`-Wert wird angehaengt.
So waechst die Ausgabe nicht automatisch mit der Kettenlaenge -- Budget bleibt
vorhersagbar unabhaengig davon, wie viele Profile geladen werden.

Fehlt ein in `entry` genannter Skill im Deployment (~/.claude/skills/<name>),
wird er in der Ausgabe uebersprungen, nicht als Fehler gemeldet.

Fail-open: Jeder interne Fehler endet mit Exit 0 und OHNE Ausgabe. Dieser Hook
ist eine Erinnerung, keine Sicherheitsgrenze -- er darf eine Session niemals
blockieren oder verzoegern.

Budget: Die Gesamtausgabe soll ~400 Tokens (grobe Naeherung: Zeichen/4) nicht
ueberschreiten (SKILL.md Abschnitt "Token-Budget"). `--measure` gibt auf
stderr die aktuelle Zeichen-/Naeherungs-Token-Zahl aus, ohne den Hook-Pfad zu
beruehren -- fuer die Verifikation beim Ausrollen.
"""

from __future__ import annotations

import json
import os
import sys

HOME = os.path.expanduser("~")
SKILLS_ROOT = os.path.join(HOME, ".claude", "skills")
SKILL_DIR = os.path.join(SKILLS_ROOT, "starter-pack-hook-creator")
PROFILES_DIR = os.path.join(SKILL_DIR, "profiles")
PROFILE_FILE = os.path.join(HOME, ".claude", "starter-pack.profile")
DEFAULT_PROFILE_CHAIN = ["ellmos"]
MAX_ENTRY_PER_CATEGORY = 3


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _profile_chain() -> list[str]:
    env_value = os.environ.get("STARTER_PACK_PROFILE", "").strip()
    if env_value:
        names = [n.strip() for n in env_value.split(",") if n.strip()]
        if names:
            return names
    try:
        if os.path.isfile(PROFILE_FILE):
            with open(PROFILE_FILE, encoding="utf-8") as handle:
                line = handle.readline().split("#", 1)[0].strip()
            names = [n.strip() for n in line.split(",") if n.strip()]
            if names:
                return names
    except Exception:
        pass
    return list(DEFAULT_PROFILE_CHAIN)


def _load_profile(name: str) -> dict | None:
    path = os.path.join(PROFILES_DIR, f"{name}.json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _skill_installed(skill_name: str) -> bool:
    skill_path = os.path.join(SKILLS_ROOT, skill_name)
    if not os.path.isdir(skill_path):
        return False
    return os.path.isfile(os.path.join(skill_path, "SKILL.md")) or os.path.isfile(
        os.path.join(skill_path, "CONTENT.md")
    )


def _merge_categories(profiles: list[dict]) -> list[dict]:
    """Later profile replaces a category with the same id wholesale; a new
    id is appended in first-seen order. Order of ids is fixed by first
    appearance so re-definition never reshuffles the output."""
    order: list[str] = []
    by_id: dict[str, dict] = {}
    for profile in profiles:
        categories = profile.get("categories")
        if not isinstance(categories, list):
            continue
        for category in categories:
            if not isinstance(category, dict):
                continue
            cat_id = category.get("id")
            if not cat_id:
                continue
            if cat_id not in by_id:
                order.append(cat_id)
            by_id[cat_id] = category
    return [by_id[cat_id] for cat_id in order]


def _recipe_path(profiles: list[dict]) -> str | None:
    for profile in profiles:
        recipe = profile.get("recipe")
        if isinstance(recipe, str) and recipe.strip():
            return os.path.join(SKILL_DIR, recipe.strip())
    return os.path.join(SKILL_DIR, "recipe.md")


def _read_recipe(path: str | None) -> str:
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().rstrip("\n")
    except Exception:
        return ""


def build_message(chain: list[str] | None = None) -> str:
    """Build the full starter-pack message. Returns "" if nothing could be
    assembled (e.g. no profile loaded at all) -- caller treats that as
    fail-open/no-op."""
    chain = chain if chain is not None else _profile_chain()
    loaded = [p for p in (_load_profile(name) for name in chain) if p]
    if not loaded:
        return ""

    lines: list[str] = []
    header_names = ",".join(p.get("name", "?") for p in loaded)
    lines.append(f"[Starter-Pack] Rezept (Profile: {header_names}):")

    recipe_text = _read_recipe(_recipe_path(loaded))
    if recipe_text:
        lines.append(recipe_text)

    merged_categories = _merge_categories(loaded)
    category_lines = []
    for category in merged_categories:
        # "when" steht nur im Profil (Dokumentation/andere Konsumenten) --
        # der Hook druckt es NICHT mit aus: die Frage steht bereits im
        # Rezepttext oben, eine zweite Nennung je Zeile wuerde das
        # ~400-Token-Budget ohne Zusatznutzen sprengen (gemessen: Ersatz
        # dieser Zeile allein senkte die Ausgabe von ~525 auf <400 Tokens).
        title = category.get("title") or category.get("id") or "?"
        entry = category.get("entry")
        entry = entry if isinstance(entry, list) else []
        installed = [s for s in entry if isinstance(s, str) and _skill_installed(s)]
        installed = installed[:MAX_ENTRY_PER_CATEGORY]
        if installed:
            skills_part = ", ".join(installed)
        else:
            skills_part = "skill-finder"
        line = f"- {title}: {skills_part}"
        category_lines.append(line)

    if category_lines:
        lines.append("")
        lines.extend(category_lines)

    return "\n".join(lines).strip()


def main() -> int:
    _ensure_utf8_stdio()
    # Hook-stdin (SessionStart payload) wird gelesen, aber nicht ausgewertet --
    # dieser Hook reagiert nicht auf Session-Details, nur auf das Profil.
    try:
        sys.stdin.read()
    except Exception:
        pass

    message = build_message()
    if not message:
        return 0

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": message,
                }
            },
            ensure_ascii=False,
        )
    )
    return 0


def _measure() -> int:
    message = build_message()
    chars = len(message)
    approx_tokens = chars / 4
    sys.stderr.write(
        f"starter_pack_hook: {chars} Zeichen, ~{approx_tokens:.0f} Tokens (Naeherung chars/4)\n"
    )
    sys.stderr.write("--- Ausgabe ---\n")
    sys.stderr.write(message + "\n")
    return 0


if __name__ == "__main__":
    if "--measure" in sys.argv:
        _ensure_utf8_stdio()
        raise SystemExit(_measure())
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        pass  # Fail-open: darf den Sessionstart niemals blockieren
    raise SystemExit(0)
