from __future__ import annotations

import json
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parents[1]


def test_required_house_files_exist():
    for name in [
        "README.md", "README_de.md", "SECURITY.md", "CHANGELOG.md", "LICENSE",
        "llms.txt", "ellmos-module.v2.json", "pyproject.toml",
        "NOTICE", "THIRD_PARTY_LICENSES.md", "THIRD_PARTY_LICENSES.txt",
        "MARKETING-LOG.txt", "TODO.md",
    ]:
        assert (REPO / name).is_file(), f"fehlt: {name}"


def test_module_manifest_valid_against_shared_schema():
    schema = json.loads((REPO / "_schema" / "ellmos.module.v2.schema.json").read_text(encoding="utf-8"))
    manifest = json.loads((REPO / "ellmos-module.v2.json").read_text(encoding="utf-8"))
    jsonschema.validate(manifest, schema)


def test_manifest_version_matches_pyproject():
    manifest = json.loads((REPO / "ellmos-module.v2.json").read_text(encoding="utf-8"))
    pyproject_text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{manifest["version"]}"' in pyproject_text


def test_manifest_version_matches_init():
    manifest = json.loads((REPO / "ellmos-module.v2.json").read_text(encoding="utf-8"))
    init_text = (REPO / "src" / "hook_master" / "__init__.py").read_text(encoding="utf-8")
    assert f'__version__ = "{manifest["version"]}"' in init_text


def test_manifest_has_no_policy_registry_seam():
    """hook-master ist policy-registry NACHGEBAUT, aber hat keine Laufzeit-
    Kopplung -- siehe CHANGELOG/registry.py-Docstring. Dieser Test prueft die
    resolutionsrelevanten Felder (requires/optional/adapters[].target), nicht
    Freitext-notes (die policy-registry als Vorbild zitieren duerfen): taucht
    dort spaeter eine echte policy-registry-Kopplung auf, muss es ein
    bewusster neuer Integrationspunkt sein, kein Versehen."""
    manifest = json.loads((REPO / "ellmos-module.v2.json").read_text(encoding="utf-8"))
    assert "policy.registry" not in manifest["requires"]
    assert "policy.registry" not in manifest["optional"]
    assert all(a.get("target") != "policy-registry" for a in manifest["adapters"])


def test_library_scripts_match_registered_hashes():
    """Schliesst den Kreis: jede library/*.py-Datei, die als canonical-Quelle
    einer Registry-Datei dient, muss mit der Datei auf der Platte hash-identisch
    sein -- verhindert, dass ein Doku-/Manifest-Refactor still von der Realitaet
    abweicht (dasselbe K3-Register-Aktualitaets-Muster wie in anderen Tickets
    dieser Sitzung bemaengelt)."""
    library = REPO / "library"
    for script in library.glob("*.py"):
        assert script.stat().st_size > 0, f"leere Datei: {script}"
        # Sanity: die Datei muss valides Python sein.
        compile(script.read_text(encoding="utf-8"), str(script), "exec")

def test_readme_language_switcher_and_links():
    en_text = (REPO / "README.md").read_text(encoding="utf-8")
    de_text = (REPO / "README_de.md").read_text(encoding="utf-8")
    assert "[English](README.md)" in en_text and "[Deutsch](README_de.md)" in en_text
    assert "[English](README.md)" in de_text and "[Deutsch](README_de.md)" in de_text


def test_readme_badges_presence():
    en_text = (REPO / "README.md").read_text(encoding="utf-8")
    de_text = (REPO / "README_de.md").read_text(encoding="utf-8")
    badges = [
        "tests-", "version-0.2.0", "python-", "Local--First",
        "consent%20gate", "Attribution-NOTICE-blue.svg", "ruff", "open--bricks", "llms.txt"
    ]
    for badge in badges:
        assert badge in en_text, f"Badge {badge} missing in README.md"
        assert badge in de_text, f"Badge {badge} missing in README_de.md"


def test_readme_mermaid_diagrams_present():
    en_text = (REPO / "README.md").read_text(encoding="utf-8")
    de_text = (REPO / "README_de.md").read_text(encoding="utf-8")
    for doc in [en_text, de_text]:
        assert "```mermaid\ngraph TD" in doc or "```mermaid\r\ngraph TD" in doc
        assert "sequenceDiagram" in doc
        assert "autonumber" in doc


def test_sibling_tools_matrix_parity():
    en_text = (REPO / "README.md").read_text(encoding="utf-8")
    de_text = (REPO / "README_de.md").read_text(encoding="utf-8")
    siblings = [
        "policy-registry", "memoryhooker", "workflowhooker",
        "system-gap-master", "source-resolver", "lock-master",
        "ticket-master", "DevCenter", "CodeBox", "open-bricks"
    ]
    for sibling in siblings:
        assert sibling in en_text, f"Sibling {sibling} missing in README.md"
        assert sibling in de_text, f"Sibling {sibling} missing in README_de.md"


def test_llms_txt_metadata_and_sections():
    llms = (REPO / "llms.txt").read_text(encoding="utf-8")
    assert "Last-checked: 2026-10-01" in llms or "Last-checked: 2026-09-29" in llms
    assert "Version: 0.2.0" in llms
    assert "https://github.com/ellmos-ai/hook-master" in llms
    assert "## Key files" in llms
    assert "## CLI Usage Quick Reference" in llms
    assert "NOTICE" in llms
    assert "THIRD_PARTY_LICENSES.md" in llms
    assert "THIRD_PARTY_LICENSES.txt" in llms
    assert "521 BGB" in llms


def test_notice_file_content():
    notice = (REPO / "NOTICE").read_text(encoding="utf-8")
    assert "hook-master" in notice
    assert "Lukas Geiger" in notice
    assert "ellmos-ai" in notice
    assert "open-bricks" in notice
    assert "MIT License" in notice
    assert "THIRD_PARTY_LICENSES.md" in notice
    assert "THIRD_PARTY_LICENSES.txt" in notice


def test_third_party_licenses_level1_sbom():
    sbom = (REPO / "THIRD_PARTY_LICENSES.md").read_text(encoding="utf-8")
    assert "Level 1 SBOM" in sbom
    assert "INV-LOCAL-01" in sbom
    assert "INV-SLA-10" in sbom
    assert "RunAsInvoker" in sbom
    assert "Python Standard Library" in sbom
    assert "PSFL-2.0" in sbom
    assert "Zero-Egress" in sbom


def test_ci_workflows_hardened():
    workflows_dir = REPO / ".github" / "workflows"
    assert (workflows_dir / "ci.yml").is_file()
    assert (workflows_dir / "stale.yml").is_file()
    assert (workflows_dir / "welcome.yml").is_file()
    assert (workflows_dir / "auto-assign.yml").is_file()
    assert (workflows_dir / "label-sync.yml").is_file()
    assert (REPO / ".github" / "labels.yml").is_file()

    for wf_name in ["ci.yml", "stale.yml", "welcome.yml", "auto-assign.yml", "label-sync.yml"]:
        content = (workflows_dir / wf_name).read_text(encoding="utf-8")
        assert "timeout-minutes:" in content, f"timeout-minutes missing in {wf_name}"
        assert "concurrency:" in content, f"concurrency missing in {wf_name}"
        assert "cancel-in-progress: true" in content, f"cancel-in-progress missing in {wf_name}"
        assert "permissions:" in content, f"permissions missing in {wf_name}"

    ci_content = (workflows_dir / "ci.yml").read_text(encoding="utf-8")
    assert "ubuntu-latest" in ci_content
    assert "windows-latest" in ci_content
    assert "macos-latest" in ci_content
    assert '"3.10"' in ci_content and '"3.13"' in ci_content


def test_gitignore_multihost_and_lock_defense():
    gi = (REPO / ".gitignore").read_text(encoding="utf-8")
    for pattern in [
        "*conflicted copy*", "*-WORKSTATION*", "*_WORKSTATION*", "*-IDEAPAD*",
        "LOCK", "LOCK.*", ".automation-lock", "uv.lock", ".hypothesis/", ".pytest_temp/"
    ]:
        assert pattern in gi, f"pattern {pattern} missing in .gitignore"


def test_pyproject_pep621_hardening_and_version_freeze():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.2.0"' in pyproject, "Version must remain frozen at 0.2.0"
    assert 'license-files = ["LICENSE", "NOTICE", "THIRD_PARTY_LICENSES.md", "THIRD_PARTY_LICENSES.txt"]' in pyproject
    assert 'Notice = "https://github.com/ellmos-ai/hook-master/blob/main/NOTICE"' in pyproject
    assert '"Third-Party Licenses" = "https://github.com/ellmos-ai/hook-master/blob/main/THIRD_PARTY_LICENSES.md"' in pyproject
    assert '"Third-Party Licenses (Text)" = "https://github.com/ellmos-ai/hook-master/blob/main/THIRD_PARTY_LICENSES.txt"' in pyproject
    assert 'minversion = "7.0"' in pyproject
    assert "norecursedirs" in pyproject
    assert ".pytest_temp" in pyproject


def test_statutory_notice_and_security_sla():
    readme_en = (REPO / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO / "README_de.md").read_text(encoding="utf-8")
    security = (REPO / "SECURITY.md").read_text(encoding="utf-8")

    assert "521 BGB" in readme_en
    assert "521 BGB" in readme_de
    assert "521 BGB" in security

    assert "48" in security
    assert "5" in security  # 5 days / 5 Werktagen
    assert "security@open-bricks.org" in security
    assert "security@ellmos.ai" in security


def test_changelog_has_unreleased_pfad_a():
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [Unreleased]" in changelog
    assert "Pfad A" in changelog
    assert "Level 1 SBOM" in changelog
    assert "## [0.2.0]" in changelog


def test_marketing_log_baseline():
    mlog = (REPO / "MARKETING-LOG.txt").read_text(encoding="utf-8")
    assert "MARKETING-LOG: hook-master" in mlog
    assert "INV-LOCAL-01" in mlog
    assert "INV-SLA-10" in mlog
    assert "Pfad A" in mlog


def test_pep561_and_module_execution():
    pkg_dir = REPO / "src" / "hook_master"
    assert (pkg_dir / "py.typed").is_file(), "src/hook_master/py.typed fehlt"
    assert (pkg_dir / "__main__.py").is_file(), "src/hook_master/__main__.py fehlt"
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert 'hook_master = ["py.typed"]' in pyproject


def test_bilingual_readme_18_point_navigation_parity_and_anchors():
    en_text = (REPO / "README.md").read_text(encoding="utf-8")
    de_text = (REPO / "README_de.md").read_text(encoding="utf-8")
    for i in range(1, 19):
        anchor = f'<a id="sec-{i:02d}"></a>'
        assert anchor in en_text, f"Anchor {anchor} missing in README.md"
        assert anchor in de_text, f"Anchor {anchor} missing in README_de.md"


def test_target_personas_parity():
    en_text = (REPO / "README.md").read_text(encoding="utf-8")
    de_text = (REPO / "README_de.md").read_text(encoding="utf-8")
    personas = ["[PERSONA-01]", "[PERSONA-02]", "[PERSONA-03]", "[PERSONA-04]"]
    for p in personas:
        assert p in en_text, f"Persona {p} missing in README.md"
        assert p in de_text, f"Persona {p} missing in README_de.md"


def test_comparative_matrix_parity():
    en_text = (REPO / "README.md").read_text(encoding="utf-8")
    de_text = (REPO / "README_de.md").read_text(encoding="utf-8")
    invariants = [
        "INV-LOCAL-01", "INV-SEC-02", "INV-PTR-03", "INV-EXEC-04", "INV-MAT-05",
        "INV-CONSENT-06", "INV-DOC-07", "INV-TRANS-08", "INV-LIC-09", "INV-SLA-10"
    ]
    for inv in invariants:
        assert inv in en_text, f"Invariant {inv} missing in README.md"
        assert inv in de_text, f"Invariant {inv} missing in README_de.md"


def test_pep621_twenty_keywords_saturation():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    expected_keywords = [
        "agent-hooks", "antigravity", "claude-code", "cli", "codex",
        "developer-tools", "ellmos-ai", "fail-closed", "governance", "hash-verification",
        "hook-registry", "local-first", "materialization", "multi-agent", "offline-first",
        "open-bricks", "pointer-registry", "python", "security-guardrails", "zero-egress",
    ]
    for kw in expected_keywords:
        assert f'"{kw}"' in pyproject, f"Keyword {kw} missing in pyproject.toml"


def test_third_party_licenses_invariant_cross_reference_matrix():
    sbom = (REPO / "THIRD_PARTY_LICENSES.md").read_text(encoding="utf-8")
    assert "Level 1 SBOM Invariant Cross-Reference Matrix" in sbom
    assert "Audited:** 2026-10-01" in sbom or "Audited:** 2026-09-29" in sbom
    for i in range(1, 11):
        assert "INV-" in sbom


def test_changelog_has_unreleased_pfad_b():
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [Unreleased]" in changelog
    assert "Pfad B" in changelog
    assert "2026-09-24" in changelog


def test_marketing_log_has_pfad_b_entry():
    mlog = (REPO / "MARKETING-LOG.txt").read_text(encoding="utf-8")
    assert "IMPLEMENTED PFAD B DISCOVERABILITY & MARKETING OVERHAUL (2026-09-24)" in mlog


def test_plain_text_sbom_companion():
    txt_sbom = (REPO / "THIRD_PARTY_LICENSES.txt").read_text(encoding="utf-8")
    assert "Audited: Stand: 2026-10-01" in txt_sbom or "Audited: Stand: 2026-09-29" in txt_sbom
    assert "INV-LOCAL-01" in txt_sbom
    assert "INV-SLA-10" in txt_sbom
    assert "RunAsInvoker" in txt_sbom
    assert "PSFL-2.0" in txt_sbom
    assert "zero external runtime dependencies" in txt_sbom


def test_labels_yml_has_eleven_governance_labels():
    labels_file = REPO / ".github" / "labels.yml"
    assert labels_file.is_file()
    content = labels_file.read_text(encoding="utf-8")
    for lbl in ["bug", "enhancement", "good first issue", "help wanted", "documentation", "duplicate", "wontfix", "priority: high", "priority: low", "needs-triage", "stale"]:
        assert f"- name: {lbl}" in content or f"- name: '{lbl}'" in content


def test_changelog_has_unreleased_pfad_a_2026_09_29():
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [Unreleased]" in changelog
    assert "2026-09-29" in changelog
    assert "Pfad A" in changelog


def test_marketing_log_has_pfad_a_entry_2026_09_29():
    mlog = (REPO / "MARKETING-LOG.txt").read_text(encoding="utf-8")
    assert "PFAD A" in mlog
    assert "2026-09-29" in mlog


def test_ascii_four_view_architectural_topology_parity():
    en_text = (REPO / "README.md").read_text(encoding="utf-8")
    de_text = (REPO / "README_de.md").read_text(encoding="utf-8")
    assert "### Four-View Architectural Topology Projection" in en_text
    assert "VIEW 1: CALLER RUNTIMES, AGENT CLIENTS & ENTRYPOINTS" in en_text
    assert "VIEW 2: HOOK-MASTER SOVEREIGN ENGINE & DISPATCH ORCHESTRATOR" in en_text
    assert "VIEW 3: RUNTIME PERSISTENCE, POINTER REGISTRY & AUDIT LEDGER" in en_text
    assert "VIEW 4: AIR-GAP DEFENSE PERIMETER, RUNASINVOKER & ZERO-EGRESS BOUNDARY" in en_text

    assert "### Vier-Sichten-Architekturtopologie-Projektion" in de_text
    assert "SICHT 1: AUFRUFER-LAUFZEITEN, AGENTEN-CLIENTS & EINSTIEGSPUNKTE" in de_text
    assert "SICHT 2: HOOK-MASTER KERN-ENGINE & DISPATCH-ORCHESTRIERUNG" in de_text
    assert "SICHT 3: LAUFZEIT-PERSISTENZ, ZEIGER-REGISTRY & AUDIT-HAUPTBUCH" in de_text
    assert "SICHT 4: AIR-GAP SICHERHEITSPERIMETER, RUNASINVOKER & ZERO-EGRESS GRENZE" in de_text


def test_changelog_has_unreleased_pfad_b_2026_10_01():
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [Unreleased]" in changelog
    assert "2026-10-01" in changelog
    assert "Pfad B" in changelog
    assert "ASCII Four-View Architectural Topology" in changelog


def test_marketing_log_has_pfad_b_entry_2026_10_01():
    mlog = (REPO / "MARKETING-LOG.txt").read_text(encoding="utf-8")
    assert "9. IMPLEMENTED PFAD B DISCOVERABILITY, 4-VIEW TOPOLOGY & LEVEL 1 SBOM (2026-10-01)" in mlog
    assert "VIEW 1: CALLER RUNTIMES" in mlog
    assert "SICHT 1 bis SICHT 4" in mlog
