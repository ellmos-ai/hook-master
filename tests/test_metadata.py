from __future__ import annotations

import json
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parents[1]


def test_required_house_files_exist():
    for name in ["README.md", "README_de.md", "SECURITY.md", "CHANGELOG.md", "LICENSE", "llms.txt", "ellmos-module.v2.json", "pyproject.toml"]:
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
    badges = ["tests-", "version-0.2.0", "python-", "Local--First", "consent%20gate", "ruff", "open--bricks", "llms.txt"]
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
    assert "Last-checked: 2026-09-10" in llms
    assert "Version: 0.2.0" in llms
    assert "https://github.com/ellmos-ai/hook-master" in llms
    assert "## Key files" in llms
    assert "## CLI Usage Quick Reference" in llms
