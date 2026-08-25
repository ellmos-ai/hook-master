# Changelog

## [0.1.0] - 2026-08-25

Erstversion. Gebaut fuer H1=A (USMC-Notiz 923, Blueprint-Ticket
`T-20260825-644007692`): Hook-Bibliothek als eigenes Modul statt nur
`.SYNC/hooks`, nach dem Vorbild `policy-registry` (Options-A-Entscheidung
dort: eigenes Modul statt Merge in policy-registry -- ausfuehrbarer Code
und Text-Policies bleiben getrennte Vertrauensklassen).

- Pointer-only Registry (`model.py`/`registry.py`), gleiche Mechanik wie
  `policy_registry.registry` -- bewusst dupliziert statt als Laufzeit-
  Abhaengigkeit importiert (Vorbild, kein Merge-Ziel).
- `kind=hook` (kanonisches Skript + SHA-256 + per-Agent Deploy-Ziele) und
  `kind=consumer` (externes Modul mit eigener Registrierungslogik, z. B.
  memoryhooker/workflowhooker).
- NEU gegenueber policy-registry: `materialize.py` (deploy/diff/status) --
  Einweg-Kopie kanonisch -> deploy_path, nie umgekehrt. Ein Hook-Zeiger ist
  ohne diesen Schritt wirkungslos (anders als ein Policy-Zeiger).
- `adapters/sync_hooks.py` + `adapters/system_gap.py`: optionaler Transport
  nach `.SYNC/hooks/registry/<slot>.json`, gated auf `system_gap_master`-
  Importierbarkeit, nie erforderlich.
- Vorbereitete, aber NICHT durchgesetzte `doctor`-Felder
  (exec_check/mtime_policy/allowlist) je Eintrag fuer das Folgeticket HE2
  (Hook-Doctor + Consent-Allowlist).
- Erste 7 Eintraege registriert: 5 kanonische Hooks
  (notaus-wake-check, token-budget-guard, precompact-state,
  token-budget-statusline, guards) + 2 Konsumenten (memoryhooker,
  workflowhooker, importiert aus `.SYNC/hooks/adoption/laptop.json`).
- Codex-Cross-Pfad-Fix: `guards.py` lag kanonisch nur unter
  `~/.claude/hooks/`, aber Codex' `~/.codex/hooks.json` zeigte hart
  dorthin. Jetzt: kanonische Kopie in `library/guards.py`, materialisiert
  nach `~/.claude/hooks/guards.py` (Claude, unveraendert) UND NEU nach
  `~/.codex/hooks/guards.py` (Codex, eigener Pfad). `hooks.json`
  umgebogen auf den neuen Pfad -- verifiziert byte-identisch (Hash-Match)
  und live smoke-getestet (Exit 0 vor und nach der Umstellung, identisches
  Verhalten), Backup unter `hooks.json.bak-20260825`.
- 37/37 Tests gruen, ruff clean.
