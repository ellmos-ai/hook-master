# TODO.md — Active work

**Version:** 0.2.0<br>
**Updated:** 2026-09-23<br>
**Reason:** Turnusgemäße Modulpflege, Pfad A Release-Gate-Härtung & Plan-D-Parität (AI MODULES CARE)<br>
**Purpose:** Track only work that remains open and provide status visibility.

## STATUS

| Category | Status | Evidence / next gate |
|---|---|---|
| Core Registry & Pointer Mechanics | DONE | 100% lokale, zeigerbasierte Registry (`~/.hook-master/registry.json`), deterministische Einweg-Materialisierung (`deploy`/`diff`/`status`) und SHA-256-Integritätsprüfung (alle Tests grün). |
| Consent Gate (HE2) & Allowlist | DONE | Fail-Closed Erstnutzungs-Consent (`allowlist.json`), `grandfathered` Migration bestehender Skripte und Schutz vor unautorisierter Materialisierung verifiziert. |
| Hook-Doctor Diagnostics | DONE | Diagnostik für Hash-Übereinstimmung, `py_compile`-Syntaxvalidierung, Ziel-Konfigurationsvalidität (JSON/TOML) und mtime-Drifterkennung implementiert. |
| Seam Adapters | DONE | Optionale Transport-Seams für `system-gap-master` und Sync-View-Export (`.SYNC/hooks`) verifiziert; vollständige Standalone-Lauffähigkeit ohne Abhängigkeiten. |
| Release Hygiene & Gate Compliance | DONE | 10/10 Final Gates bestanden (.gitignore, Sprachreinheit, persönliche Pfadneutralität via `Path.home()`, STATUS-Tabelle, PEP 639 License Inventory). |
| Discoverability & Visual Architecture | DONE | Bilinguales README (DE/EN) mit echten deutschen Umlauten, Mermaid-Architektur- und Sequenzdiagramme, `llms.txt`-Discovery und Level-1-SBOM (`THIRD_PARTY_LICENSES.md`). |
| Multi-Agent Ecosystem Integration | OPEN | Laufende Synchronisation der kanonischen Hook-Skripte (`library/*.py`) mit neuen Agenten-Versionen (Claude Code, Codex, Antigravity, Kimi). |
| Public Release Gate | USER | MIT License und gesetzlicher Haftungshinweis (§ 521 BGB) hinterlegt; finale Freigabe für öffentliche Sichtbarkeit obliegt dem Nutzer. |

## Formalized next tasks

- [ ] **TASK-HM-01: Kontinuierliche Hook-Bibliotheks-Parität** (`effort=low`, `scope=ecosystem`, priority `normal`).
  - **Ziel:** Regelmäßige Überprüfung und Erweiterung der kanonischen Hook-Skripte in `library/` bei API-Änderungen der Ziel-Agenten (Claude Code, Codex, Antigravity).
  - **Definition of Done:** `hook-master doctor` meldet `ok` für alle registrierten Targets auf Workstation und Laptop.

- [ ] **TASK-HM-02: Erweiterte Hook-Metriken & Timing-Profile** (`effort=medium`, `scope=diagnostics`, priority `low`).
  - **Ziel:** Optionales Profiling der Hook-Ausführungszeiten im `doctor`-Subsystem zur frühzeitigen Erkennung von Latenz-Spitzen bei PreToolUse-Guards.
  - **Definition of Done:** `hook-master doctor --timing` liefert strukturierte Millisekunden-Reports.

- [x] **TASK-HM-03: Release-Hygiene & Final-Gate-Härtung (v0.2.0)** (`effort=low`, `scope=hygiene`, priority `high`).
  - **Ergebnis:** Alle 10 Final Gates bestanden (10/10 PASS), Pfadneutralität in `library/precompact_state.py` auf `Path.home()` gehärtet, PEP 561 `py.typed` Marker hinterlegt, CLI-Modulaufruf via `python -m hook_master` ergänzt, Plan-D-Spiegelung und Modulkatalog synchronisiert.

---
<!-- REMEMBER: ENDUSERTEXTE BEKOMMEN ECHTE UMLAUTE Ü Ö Ä ß -->
