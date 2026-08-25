# Security Policy / Sicherheitsrichtlinie

[🇩🇪 Deutsche Version](#deutsche-sicherheitsrichtlinie) | [🇬🇧 English Version](#english-security-policy)

---

## English Security Policy

### Core Security & Privacy Invariants

1. **Local-First & Zero-Egress Operation**: `hook-master` is designed for offline, local-first execution. It stores all authoritative metadata on the local filesystem (`~/.hook-master/registry.json` or a custom path via `HOOK_MASTER_REGISTRY_PATH`) and performs zero network telemetry or data exfiltration.
2. **Pointer-Only Metadata, Never Script Text in the Registry**: The registry stores metadata (id, event, agent targets, SHA-256 hashes) and points at canonical script files on disk. It **never** embeds script source text in `registry.json` itself (`model.FORBIDDEN_CONTENT_KEYS` rejects any attempt to do so).
3. **Executable Code Is a Different Trust Class Than Text — Handled Accordingly**: Unlike a text/policy pointer, a hook pointer resolves to code an agent will *execute*. `verify()` and `deploy --diff` compare the canonical file's SHA-256 hash against both the registered hash and the deployed copy on every check — drift is reported, never silently accepted.
4. **One-Way Materialization, No Silent Overwrite of the Canonical Source**: `deploy()` always copies canonical → deploy target, never the reverse. It will not read back changes made directly to a deployed copy into the registry — a drifted deployed file is reported by `diff()`, not auto-repaired, so a human decides whether the drift was intentional.
5. **Non-Elevation**: `hook-master` operates entirely in standard user space without requiring administrative or elevated privileges. It never modifies an agent's own settings/config file (`settings.json`, `hooks.json`, `config.toml`) automatically — repointing a live hook registration (e.g. the Codex `guards.py` cross-path fix in this module's initial release) is a deliberate, hash-verified, manually reviewed step, not something the CLI does on its own.
6. **Optional Transport, Never Required**: `adapters/system_gap.py` only activates if `system_gap_master` is importable; the registry and all deploy/diff/status/verify operations work fully offline and standalone without it (same invariant as the sibling module `policy-registry`, D-20260728-001).
7. **Doctor/Allowlist Fields Are Reserved, Not Yet Enforced**: `model.py` accepts an optional `doctor` object (`exec_check`, `mtime_policy`, `allowlist`) on each entry for a planned follow-up (Hook-Doctor + Consent-Allowlist, HE2). As of this release these fields are validated for shape but **not evaluated** by any check — do not rely on them for actual enforcement yet.

### Reporting a Vulnerability

If you discover a potential security vulnerability or integrity flaw in `hook-master`, please report it privately:

- **Primary Security Contact**: `security@ellmos.ai`
- **Umbrella Security Contact**: `lukas@open-bricks.org`
- **Maintainer Direct**: `support@lukasgeiger.com`
- **GitHub Security Advisories**: [Open Private Security Advisory](https://github.com/ellmos-ai/hook-master/security/advisories)

Please do not disclose security issues publicly via GitHub Issues or discussions until a fix has been released. We acknowledge receipt of security reports within 24 to 48 hours and coordinate release remediation promptly.

---

## Deutsche Sicherheitsrichtlinie

### Grundlegende Sicherheits- und Datenschutzinvariante

1. **Local-First & Zero-Egress-Betrieb**: `hook-master` ist für den vollständig lokalen Offline-Betrieb konzipiert. Alle autoritativen Metadaten werden im lokalen Dateisystem abgelegt (`~/.hook-master/registry.json` oder ein per `HOOK_MASTER_REGISTRY_PATH` konfigurierter Pfad). Es findet keinerlei Netzwerk-Telemetrie oder Datenabfluss statt.
2. **Reine Zeiger-Metadaten, niemals Skript-Volltext in der Registry**: Die Registry speichert Metadaten (id, event, Agent-Ziele, SHA-256-Hashes) und zeigt auf kanonische Skriptdateien auf der Platte. Sie bettet **niemals** Skript-Quelltext in `registry.json` selbst ein (`model.FORBIDDEN_CONTENT_KEYS` weist jeden Versuch zurück).
3. **Ausführbarer Code ist eine andere Vertrauensklasse als Text — entsprechend behandelt**: Anders als ein Text-/Policy-Zeiger löst ein Hook-Zeiger zu Code auf, den ein Agent *ausführt*. `verify()` und `deploy --diff` vergleichen den SHA-256-Hash der kanonischen Datei bei jeder Prüfung sowohl gegen den registrierten Hash als auch gegen die materialisierte Kopie — Drift wird gemeldet, nie stillschweigend hingenommen.
4. **Einweg-Materialisierung, kein stilles Überschreiben der kanonischen Quelle**: `deploy()` kopiert immer kanonisch → Zielort, nie umgekehrt. Direkt an einer materialisierten Kopie vorgenommene Änderungen werden NICHT zurück in die Registry gelesen — eine abweichende materialisierte Datei wird von `diff()` gemeldet, nicht automatisch repariert; ein Mensch entscheidet, ob die Abweichung beabsichtigt war.
5. **Keine Rechteausweitung (Non-Elevation)**: `hook-master` arbeitet vollständig im regulären Benutzerkontext ohne erhöhte Administratorrechte. Es ändert nie automatisch die eigene Config-Datei eines Agenten (`settings.json`, `hooks.json`, `config.toml`) — das Umbiegen einer laufenden Hook-Registrierung (z. B. der Codex-`guards.py`-Cross-Pfad-Fix im ersten Release dieses Moduls) ist ein bewusster, hash-geprüfter, manuell kontrollierter Schritt, kein automatisches CLI-Verhalten.
6. **Optionaler Transport, nie erforderlich**: `adapters/system_gap.py` aktiviert sich nur, wenn `system_gap_master` importierbar ist; die Registry und alle deploy/diff/status/verify-Operationen funktionieren vollständig offline und eigenständig auch ohne dieses Paket (dieselbe Invariante wie im Schwestermodul `policy-registry`, D-20260728-001).
7. **Doctor-/Allowlist-Felder sind reserviert, noch nicht durchgesetzt**: `model.py` akzeptiert ein optionales `doctor`-Objekt (`exec_check`, `mtime_policy`, `allowlist`) je Eintrag für ein geplantes Folgeticket (Hook-Doctor + Consent-Allowlist, HE2). Zum Stand dieses Releases werden diese Felder auf Form geprüft, aber von keinem Check **ausgewertet** — noch nicht auf tatsächliche Durchsetzung verlassen.

### Meldung von Sicherheitslücken

Wenn Sie eine potenzielle Sicherheitslücke oder einen Integritätsfehler in `hook-master` finden, melden Sie diesen bitte vertraulich:

- **Primärer Sicherheitskontakt**: `security@ellmos.ai`
- **Dachverband-Sicherheitskontakt**: `lukas@open-bricks.org`
- **Entwickler-Direktkontakt**: `support@lukasgeiger.com`
- **GitHub Security Advisories**: [Private Sicherheitsmeldung einreichen](https://github.com/ellmos-ai/hook-master/security/advisories)

Bitte eröffnen Sie keine öffentlichen GitHub-Issues für Sicherheitsvorfälle. Wir bestätigen den Eingang von Hinweisen innerhalb von 24 bis 48 Stunden und koordinieren die Behebung umgehend.
