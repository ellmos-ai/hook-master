# Changelog

## [Unreleased]

### Final Gate Hardening, Personal Path Neutrality & Module Execution (2026-09-23) [Pfad A / AI MODULES CARE]
- **Final Gate 1-10 Compliance (10/10 PASS):** Achieved 10/10 PASS on canonical `final_gate_check.py` release readiness verification.
- **Personal Path Neutrality (Gate 7):** Refactored `library/precompact_state.py` fallback USMC DB path to dynamic `Path.home()` instead of hardcoded personal user path.
- **Formalized Task Governance (Gate 10):** Added canonical `TODO.md` with standardized `## STATUS` table and formalized tasks (`TASK-HM-01` to `TASK-HM-03`).
- **PEP 561 Typing & Module Execution:** Added `py.typed` marker file and `src/hook_master/__main__.py` to support `python -m hook_master` alongside CLI entry point.
- **Contract Verification:** Added `TODO.md` and PEP 561 assertions to `tests/test_metadata.py` (all tests green).

### Fixed
- **Cross-platform `run_self_test()` alias detection (T-20260921-750493182, Runde 3):** `run_self_test()["alias_detection_works"]` tested the alias-rejection invariant by calling `validate_interpreter("python3")` and expecting an exception on every platform. On Linux/macOS `python3` is a legitimate, real interpreter, so `validate_interpreter()` correctly did **not** raise there — meaning the self-test (and therefore `hook-master doctor --self-test`, exit code 2 on failure) was permanently broken on non-Windows. Fixed by testing the platform-independent 0-byte-size invariant directly against a synthetic temp-file candidate instead of the incidental "python3" name. `validate_interpreter()` itself was already correct and needed no change. Added tests that simulate all three target platforms via `monkeypatch.setattr(sys, "platform", ...)` so the Windows-only forbidden-name branch and the cross-platform alias check are both exercised on every CI runner, not only the one matching the real host OS.
- **Ambient-path test fixture broke `doctor` tests on any host without `~/.claude/settings.json`:** The shared `hook_entry` fixture (`tests/conftest.py`) pointed its `config_path` at the real `~/.claude/settings.json` instead of an isolated file. On a developer machine that happens to run Claude Code the file exists and is valid, so `doctor.check_entry()`'s config check silently passed; on a clean CI runner home directory it is `missing`, which `doctor.check_entry()` correctly treats as a hard error — inflating the severity/exit code of every test using this fixture (`test_healthy_consented_entry_is_ok`, `test_pending_consent_is_warning_not_error`, `test_not_deployed_is_warning`, `test_mtime_drift_flagged_when_deployed_edited_directly`). This was invisible until now because CI never ran to completion (private-repo dependency block, see above). Fixed by giving the fixture its own isolated, always-valid `tmp_path`-based config file, matching the pattern already used in `test_consumer_entry_only_checks_config_integrity`.


### Technical Hygiene, CI Lifecycle Workflows, Lock Defense & Level 1 SBOM Audit (2026-09-22) [Pfad A]
- **Multi-OS CI Matrix & Lifecycle Workflows:** Added hardened GitHub Actions workflows:
  - `ci.yml`: Multi-OS (`ubuntu-latest`, `windows-latest`, `macos-latest`) and multi-version Python (`3.10`, `3.11`, `3.12`, `3.13`) test and lint matrix with a 15-minute runaway timeout guardrail, concurrency cancellation, and compileall bytecode verification.
  - `stale.yml`: Automated daily triage for inactive issues and PRs (30 days stale, 7 days close) with 10-minute timeout.
  - `welcome.yml`: Contributor first-interaction onboarding with 5-minute timeout and least-privilege permissions.
- **Multi-Host Cloud-Sync & Concurrency Lock Defense:** Hardened `.gitignore` against cloud sync conflict patterns (`*conflicted copy*`, `*-WORKSTATION*`, `*-ASUS*`, `*-LAPTOP*`, `*.orig`, `*.rej`), canonical multi-agent lock artifacts (`LOCK`, `LOCK.*`, `LOCK*.txt`, `.automation-lock`), and transient test/build caches (`.hypothesis/`, `.turbo/`, `.nyc_output/`, `uv.lock`).
- **Attribution & Transparency Notice:** Added canonical root `NOTICE` file attributing Lukas Geiger, `ellmos-ai`, and the `open-bricks` open-source umbrella.
- **Level 1 SBOM Transparency & Governance Invariants:** Added `THIRD_PARTY_LICENSES.md` documenting zero external runtime dependencies (100% Python Standard Library PSFL-2.0), permissive testing/build tooling, unprivileged `RunAsInvoker` non-elevation certification, and 10 architecture invariants (`INV-LOCAL-01` to `INV-SLA-10`).
- **PEP 621 Standard Packaging & Pytest Hardening:** Updated `pyproject.toml` with `license-files` declaration, expanded `project.urls` (Notice, Third-Party Licenses, Bug Tracker, Marketing Log, LLM Ready), and hardened `pytest.ini_options` (`minversion = "7.0"`, `norecursedirs`). Version strictly preserved at `0.2.0` (T-20260920-167562623).
- **Statutory Liability Disclaimer & Security SLAs:** Standardized German statutory liability disclaimer (§ 521 BGB Gefälligkeitsrecht) and binding dual security SLAs (48-hour response, 5-day triage) across `README.md`, `README_de.md`, and `SECURITY.md`.
- **AI Agent Context & Discovery Parity:** Updated `llms.txt` with timestamp `2026-09-22`, updated test baseline, and cross-references to `NOTICE` and `THIRD_PARTY_LICENSES.md`.
- **Extended Contract Verification Suite:** Expanded `tests/test_metadata.py` to assert house files existence, NOTICE integrity, SBOM structure, CI workflow hardening, .gitignore coverage, and legal disclaimers.

### Notaus-Aufhebung verlustfrei (2026-09-20)
- **Notaus-Aufhebung verlustfrei:** `token_budget_guard.py` übernimmt die
  Parkvermerke `paused_goals` und `paused_agents` bei automatischen
  State-Übergängen und meldet eine ausstehende Aufhebung. Der
  `notaus_wake_check.py` macht erhaltene Parkkreise beim nächsten Wecken
  sichtbar, statt sie still zu übergehen.
- **Tests:** Regressionstests decken den automatischen Rücklauf mit
  pausierten Goals/Workern und die Wake-Meldung ab.

## [0.2.0] - 2026-08-25 (Ergänzt 2026-09-10)

### Pfad B Discoverability, Mermaid-Architektur & Metadaten (2026-09-10)
- **Mermaid-Architektur & Sequenzdiagramm:** Interaktive Visualisierungen für kanonische Speicherung, Registry-Pointers, Fail-Closed Consent-Gate (HE2), Doctor-Diagnostik und Einweg-Materialisierung zu Ziel-Agenten (Claude Code, Codex, Antigravity, Kimi).
- **Zweisprachige Nutzerführung (DE/EN):** Synchronisierte READMEs mit Anker-Inhaltsverzeichnis, funktionierenden Badge-Links und konsistentem Sprachwechsler.
- **Ökosystem-Matrix:** Strukturierte Verknüpfung der verwandten Module (`policy-registry`, `memoryhooker`, `workflowhooker`, `system-gap-master`, `source-resolver`, `lock-master`, `ticket-master`, `DevCenter`, `CodeBox`, `open-bricks`).
- **AI-Discovery:** Aktualisierung von `llms.txt` auf Prüfstand 2026-09-10 mit detaillierter Dateistruktur und CLI-Befehlsübersicht.
- **Metadaten-Vertragstests:** Erweiterung von `tests/test_metadata.py` um Diagramm-, Badge- und Sprachparitätstests.

HE2 (T-20260825-519184830, User-Entscheid HE2=ja, USMC-Notiz 923): Hook-Doctor
+ Erstnutzungs-Consent-Allowlist. Konzept-Nachbau nach dem Hermes-Agent-Muster
(Quelle: T-20260825-152496601, SOLVED), keine Code-Uebernahme. Baut wie
beauftragt auf hook-master auf (nicht parallel dazu entwickelt).

- `doctor.py`: neuer Diagnosebefehl `hook-master doctor [--id] [--timing]`.
  Prueft je `kind=hook`/canonical-Eintrag: Existenz+Hash-Match kanonisch
  <-> deployed (baut auf registry.verify()/materialize.diff() auf, geht
  aber darueber hinaus), Ausfuehrbarkeit (py_compile), Materialisierungs-
  zustand, mtime-Drift (NUR gemeldet zusammen mit tatsaechlichem Hash-
  Unterschied -- ein blosser "gerade deployed"-Zeitstempel ist der
  Normalzustand nach jedem deploy() und waere sonst ein Fehlalarm bei
  JEDEM Erst-Deploy, empirisch beim eigenen Testlauf gefunden und
  korrigiert), JSON/TOML-Validitaet der Ziel-Configs. Fuer `kind=consumer`
  NUR die Config-Pruefung -- kein kanonisches Skript, also kein Hash-/
  Exec-/mtime-Check. Schweregrad ok<warning<error, Exit-Code 0/1/2.
- `consent.py`: neue `allowlist.json` (State, nicht Registry) --
  `hook-master consent <id>`/`consent-status`. `deploy()` materialisiert
  einen NIE freigegebenen `kind=hook`-Eintrag nicht mehr, sondern meldet
  `pending-consent`. Lesen fail-open (kaputte/fehlende Datei -> leere
  Allowlist, keine Exception), Deploy-Entscheidung fail-closed (unbekannt
  = nein). Die 7 Eintraege aus 0.1.0 wurden explizit als
  `consented_by: "grandfathered"` mit Vermerk geseedet -- kein stilles
  Uebergehen der neuen Pflicht.
- `doctor`-Feld in `model.py` (aus 0.1.0) bleibt bewusst unveraendert und
  unausgewertet -- die tatsaechliche HE2-Umsetzung lebt vollstaendig in
  `doctor.py`/`consent.py`, nicht in diesem reservierten Schemafeld.
  README/SECURITY klargestellt, damit das nicht verwechselt wird.
- 20 neue Tests (test_consent.py, test_doctor.py, erweiterte Consent-Gate-
  Faelle in test_materialize.py) -- 57/57 gruen, ruff clean.
- `provides` um `hook.doctor`/`hook.consent` erweitert.

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
