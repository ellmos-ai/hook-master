# Contributing to hook-master / Mitwirken an hook-master

Welcome! We welcome contributions to `hook-master` (Local-first pointer registry and one-way materialization for agent hooks from [ellmos-ai](https://github.com/ellmos-ai) under the [open-bricks](https://github.com/open-bricks) umbrella). To maintain deterministic execution, fail-closed consent verification, air-gapped process isolation, single-writer filesystem safety, and compliance across multi-host environments, all contributions must adhere to the quality standards and operational invariants defined below.

---

## English

### 1. General Principles & Quality Gates
1. **Local-First & Zero-Egress (`INV-LOCAL-01`)**: The core pointer registry, doctor diagnostics engine, one-way materialization pipeline, and allowlist operate strictly offline using the Python standard library. Zero outbound network sockets, zero telemetry, and zero phone-home tracking.
2. **Unprivileged User-Mode Execution (`INV-SEC-02` / `RunAsInvoker`)**: All CLI commands, deployment actions, and hook diagnostic routines execute strictly in unprivileged user space. Administrative elevation (UAC/root/sudo) is strictly forbidden.
3. **Pointer-Only Registry Architecture (`INV-PTR-03`)**: The registry maintains metadata and filesystem pointers to canonical script files; it never embeds executable script code inside `registry.json`.
4. **Executable Code Trust Class Separation (`INV-EXEC-04`)**: Executable hooks are recognized as a distinct trust class from static text policies. Cryptographic SHA-256 hashes are verified on every check, and drift is never silently resolved.
5. **One-Way Materialization Invariant (`INV-MAT-05`)**: Always copies canonical source to deploy target (`canonical -> deployed`), never the reverse. Direct changes to deployed targets are reported as drift, not automatically overwritten back to canonical.
6. **Fail-Closed Consent Allowlist (`INV-CONSENT-06`)**: Newly registered hook scripts require explicit user consent via `allowlist.json` before materialization; unconsented scripts are blocked fail-closed.
7. **Comprehensive Hook-Doctor Diagnostics (`INV-DOC-07`)**: Deep diagnostic checks verify canonical file existence, SHA-256 hash match, syntax compilation (`py_compile`), mtime drift, and agent config JSON/TOML syntax integrity without external dependencies.
8. **Optional Transport Independence (`INV-TRANS-08`)**: Standalone operation requires zero external packages; `system_gap_master` adapter operates purely as an optional, graceful transport layer.
9. **Zero-Copyleft & 100% Permissive Open-Source Licensing (`INV-LIC-09`)**: Clean MIT/PSFL stack audited in Level 1 SBOM, zero copyleft or AGPL contamination.
10. **Dual Security Response & Triage SLA (`INV-SLA-10`)**: We commit to a 48h acknowledgment and 5-business-day triage SLA for security disclosures pursuant to [SECURITY.md](SECURITY.md).
11. **Version Freeze Discipline (`T-20260920-167562623`)**: Package version `0.2.0` is strictly frozen across `__init__.py`, `pyproject.toml`, and all manifests. Do not bump the version string. Document all advancements under `## [Unreleased]` in `CHANGELOG.md`.
12. **Clean Code & Regression Testing**: Every feature or fix must include regression tests in `tests/`. Keep test coverage at a 100% pass rate.
13. **Bilingual Parity**: Maintain synchronized structural and navigational parity across `README.md` and `README_de.md` (18-point dual anchors `sec-01` through `sec-18`).

### 2. Local Development Workflow (Plan D)
```bash
# Clone the repository (canonical Plan D location)
git clone https://github.com/ellmos-ai/hook-master.git "C:\_Local_DEV\repos\hook-master"
cd "C:\_Local_DEV\repos\hook-master"

# Install package in editable mode with test dependencies
pip install -e ".[test]"

# Run comprehensive test suite
pytest -ra -v

# Run fast static code analysis
ruff check .

# Check bytecode compilation
python -m compileall -q .

# Check whitespace and git diff cleanliness
git diff --check

# Verify version freeze compliance (must return 0 matches)
git diff -G"version = "
```

### 3. Submission Protocol
- Open an issue for architectural discussions before large refactoring.
- Keep provider API keys, tokens, and private credentials strictly outside the repository.
- Ensure all 10 governance invariants (`INV-LOCAL-01` to `INV-SLA-10`) remain VERIFIED.
- Pull requests must target the `main` branch.

### 4. License
By contributing to `hook-master`, you agree that your contributions will be licensed under the [MIT License](LICENSE).

### 5. Statutory Notice & Liability Limitation (§ 521 BGB)
The provision of this software and its documentation is gratuitous (unentgeltliche Bereitstellung). Pursuant to § 521 BGB (German Civil Code), liability is strictly limited to intentional misconduct (Vorsatz) and gross negligence (grobe Fahrlässigkeit).

---

## Deutsch

### 1. Grundsätze & Qualitäts-Tore
1. **Local-First & Zero-Egress (`INV-LOCAL-01`)**: Die Zeiger-Registry, die Doctor-Diagnose-Engine, die Einweg-Materialisierungs-Pipeline und die Allowlist arbeiten standardmäßig zu 100% offline ausschließlich mit Modulen der Python-Standardbibliothek. Keine Telemetrie, keine externen Netzwerkverbindungen, kein Phone-Home.
2. **Unprivilegierte Benutzer-Ausführung (`INV-SEC-02` / `RunAsInvoker`)**: Sämtliche CLI-Befehle, Bereitstellungsaktionen und Hook-Diagnosen laufen strikt im unprivilegierten Standard-Benutzerkontext. Administrative Rechte oder UAC-Elevationen sind verboten.
3. **Reine Zeiger-Registry-Architektur (`INV-PTR-03`)**: Die Registry speichert Metadaten und Dateisystemzeiger auf kanonische Skriptdateien; ausführbarer Skriptcode wird niemals direkt in `registry.json` eingebettet.
4. **Ausführbarer Code als separate Vertrauensklasse (`INV-EXEC-04`)**: Ausführbare Hooks werden als eigenständige Vertrauensklasse gegenüber statischen Textrichtlinien behandelt. Kryptographische SHA-256-Hashes werden bei jedem Check validiert; Drift wird niemals stillschweigend aufgelöst.
5. **Einweg-Materialisierungs-Invariante (`INV-MAT-05`)**: Synchronisiert stets von der kanonischen Quelle zum Ziel (`canonical -> deployed`), niemals umgekehrt. Direkte Modifikationen an Zieldateien werden als Drift gemeldet und nicht still überschrieben.
6. **Fail-Closed Consent-Allowlist (`INV-CONSENT-06`)**: Neu registrierte Hook-Skripte verlangen zwingend eine explizite Nutzereinwilligung über `allowlist.json` vor der Materialisierung; nicht autorisierte Hooks werden fail-closed blockiert.
7. **Tiefgreifende Hook-Doctor-Diagnose (`INV-DOC-07`)**: Umfassende Prüfungen validieren Dateiexistenz, SHA-256-Hash-Übereinstimmung, Syntaxkompilierung (`py_compile`), mtime-Drift und Agenten-Konfigurationssyntax ohne externe Abhängigkeiten.
8. **Optionale Transport-Unabhängigkeit (`INV-TRANS-08`)**: Der Standalone-Betrieb erfordert keinerlei externe Pakete; der `system_gap_master`-Adapter dient rein als optionale, rückwärtskompatible Transportschicht.
9. **Zero-Copyleft & 100% permissive Open-Source-Lizenzierung (`INV-LIC-09`)**: Sauberer, im Level 1 SBOM auditierter MIT/PSFL-Stack ohne Copyleft- oder AGPL-Einschränkungen.
10. **Kryptographische Auditierbarkeit & Duale SLAs (`INV-SLA-10`)**: Verbindliche Zusage einer 48h Reaktionszeit und einer 5-Werktage-Triage-Bewertung gemäß [SECURITY.md](SECURITY.md).
11. **Version-Freeze-Disziplin (`T-20260920-167562623`)**: Paketversion `0.2.0` ist über alle Manifeste, Quelltexte und Badges hinweg strikt eingefroren. Kein Versions-Bump. Alle Weiterentwicklungen werden unter `## [Unreleased]` in `CHANGELOG.md` dokumentiert.
12. **Sauberer Code & Regressionstests**: Jede Änderung erfordert begleitende Tests in `tests/`. Die Testsuite muss zu 100% grün bleiben.
13. **Bilinguale Parität**: Strukturelle und navigatorische Parität zwischen `README.md` und `README_de.md` (18-Punkte Dual-Anker `sec-01` bis `sec-18`) ist zwingend einzuhalten.

### 2. Lokaler Entwicklungs-Workflow (Plan D)
```bash
# Klonen des Repositories (kanonischer Plan D Pfad)
git clone https://github.com/ellmos-ai/hook-master.git "C:\_Local_DEV\repos\hook-master"
cd "C:\_Local_DEV\repos\hook-master"

# Paket im Entwicklungsmodus mit Testabhängigkeiten installieren
pip install -e ".[test]"

# Testsuite ausführen
pytest -ra -v

# Schnelle statische Code-Prüfung ausführen
ruff check .

# Bytecode-Kompilierung validieren
python -m compileall -q .

# Whitespace- und Diff-Sauberkeit prüfen
git diff --check

# Versions-Freeze prüfen (darf keine Treffer liefern)
git diff -G"version = "
```

### 3. Einreichungs-Protokoll
- Vor umfangreichen Architektur-Refactorings bitte ein Issue zur Abstimmung eröffnen.
- Niemals API-Schlüssel, Passwörter oder persönliche Tokens im Repository committen.
- Sicherstellen, dass alle 10 Invarianten (`INV-LOCAL-01` bis `INV-SLA-10`) unverletzt bleiben.
- Pull Requests richten sich stets an den Branch `main`.

### 4. Lizenz
Mit dem Einreichen von Beiträgen erklärst du dich damit einverstanden, dass deine Beiträge unter der [MIT-Lizenz](LICENSE) veröffentlicht werden.

### 5. Gesetzlicher Hinweis & Haftungsbeschränkung (§ 521 BGB)
Die Bereitstellung dieser Software und ihrer Dokumentation erfolgt unentgeltlich. Gemäß § 521 BGB (Bürgerliches Gesetzbuch — Haftung des Schenkers) ist die Haftung für Sach- und Rechtsmängel auf Vorsatz und grobe Fahrlässigkeit beschränkt.
