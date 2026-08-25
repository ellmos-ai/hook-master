from __future__ import annotations

import json

from hook_master import doctor
from hook_master.consent import ConsentStore


def test_healthy_consented_entry_is_ok(registry, hook_entry, consented_store):
    registry.register(hook_entry)
    from hook_master import materialize

    materialize.deploy(registry, consent=consented_store)
    report = doctor.run(registry, consent=consented_store)
    assert report["exit_code"] == 0
    assert report["entries"][0]["severity"] == "ok"


def test_pending_consent_is_warning_not_error(registry, hook_entry, tmp_path):
    registry.register(hook_entry)
    empty_consent = ConsentStore(tmp_path / "allowlist.json")
    report = doctor.run(registry, consent=empty_consent)
    assert report["exit_code"] == 1
    assert report["entries"][0]["severity"] == "warning"
    consent_finding = next(f for f in report["entries"][0]["findings"] if f["check"] == "consent")
    assert consent_finding["state"] == "pending-consent"


def test_missing_canonical_source_is_hard_error(registry, hook_entry, canonical_script, consented_store):
    registry.register(hook_entry)
    canonical_script.unlink()
    report = doctor.run(registry, consent=consented_store)
    assert report["exit_code"] == 2
    assert report["entries"][0]["severity"] == "error"


def test_hash_mismatch_is_hard_error(registry, hook_entry, canonical_script, consented_store):
    registry.register(hook_entry)
    canonical_script.write_text("# tampered after registration\n", encoding="utf-8")
    report = doctor.run(registry, consent=consented_store)
    assert report["exit_code"] == 2


def test_syntax_error_in_canonical_script_is_hard_error(registry, hook_entry, canonical_script, consented_store):
    registry.register(hook_entry)
    canonical_script.write_text("def broken(:\n", encoding="utf-8")
    # Hash weicht dadurch ohnehin ab -- fuer einen isolierten Syntax-Fund
    # direkt den Registry-Eintrag mit dem neuen Hash aktualisieren.
    from hook_master.model import sha256_file

    entry = registry.get(hook_entry["id"])
    entry["source"]["hash"]["value"] = sha256_file(canonical_script)
    registry.register(entry, replace=True)
    report = doctor.run(registry, consent=consented_store)
    exec_finding = next(f for f in report["entries"][0]["findings"] if f["check"] == "executable")
    assert exec_finding["state"] == "syntax-error"
    assert report["exit_code"] == 2


def test_not_deployed_is_warning(registry, hook_entry, consented_store):
    registry.register(hook_entry)
    report = doctor.run(registry, consent=consented_store)
    materialization = next(f for f in report["entries"][0]["findings"] if f["check"] == "materialization")
    assert materialization["state"] == "not-deployed"
    assert report["entries"][0]["severity"] == "warning"


def test_mtime_drift_flagged_when_deployed_edited_directly(registry, hook_entry, consented_store):
    """Realistisches Szenario: jemand bearbeitet die materialisierte Kopie
    direkt (statt den kanonischen Weg zu nehmen) -- das macht sie zugleich
    hash-verschieden (drifted) UND juenger als die kanonische Quelle. Ein
    blosses "deployed ist juenger" OHNE Hash-Unterschied ist dagegen der
    Normalzustand direkt nach jedem erfolgreichen deploy() (frische mtime durch
    shutil.copyfile) und darf KEIN Fund sein -- siehe
    test_healthy_consented_entry_is_ok, das genau das absichert."""
    from hook_master import materialize
    from hook_master.model import expand_uri

    registry.register(hook_entry)
    materialize.deploy(registry, consent=consented_store)
    deployed = expand_uri(hook_entry["targets"][0]["deploy_path"])
    deployed.write_text("# direkt an der Kopie bearbeitet, nicht kanonisch\n", encoding="utf-8")
    report = doctor.run(registry, consent=consented_store)
    materialization = next(f for f in report["entries"][0]["findings"] if f["check"] == "materialization")
    assert materialization["state"] == "drifted"
    assert "mtime_drift" in materialization
    assert report["entries"][0]["severity"] == "warning"


def test_timing_flag_adds_compile_seconds(registry, hook_entry, consented_store):
    registry.register(hook_entry)
    report = doctor.run(registry, consent=consented_store, timing=True)
    timing_finding = next(f for f in report["entries"][0]["findings"] if f["check"] == "timing")
    assert isinstance(timing_finding["compile_seconds"], float)


def test_consumer_entry_only_checks_config_integrity(tmp_path):
    from hook_master.registry import HookRegistry

    registry = HookRegistry(tmp_path / "registry.json")
    config = tmp_path / "settings.json"
    config.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
    entry = {
        "id": "consumer:memoryhooker",
        "kind": "consumer",
        "title": "memoryhooker",
        "event": "SessionStart",
        "source": {"kind": "external-module", "module": "memoryhooker"},
        "targets": [{"agent": "claude-code", "config_path": str(config)}],
        "consumers": ["memoryhooker"],
        "status": "active",
        "adoption": {"laptop": "adopted"},
    }
    registry.register(entry)
    report = doctor.run(registry, consent=ConsentStore(tmp_path / "allowlist.json"))
    findings = report["entries"][0]["findings"]
    assert len(findings) == 1
    assert findings[0]["check"] == "config"
    assert findings[0]["state"] == "valid"
    assert report["entries"][0]["severity"] == "ok"


def test_consumer_entry_flags_invalid_config_json(tmp_path):
    from hook_master.registry import HookRegistry

    registry = HookRegistry(tmp_path / "registry.json")
    config = tmp_path / "broken.json"
    config.write_text("{not valid json", encoding="utf-8")
    entry = {
        "id": "consumer:workflowhooker",
        "kind": "consumer",
        "title": "workflowhooker",
        "event": "Stop",
        "source": {"kind": "external-module", "module": "workflowhooker"},
        "targets": [{"agent": "codex", "config_path": str(config)}],
        "consumers": ["workflowhooker"],
        "status": "active",
        "adoption": {"laptop": "adopted"},
    }
    registry.register(entry)
    report = doctor.run(registry, consent=ConsentStore(tmp_path / "allowlist.json"))
    assert report["exit_code"] == 2
    assert report["entries"][0]["severity"] == "error"


def test_doctor_filters_by_entry_id(registry, hook_entry, consented_store):
    registry.register(hook_entry)
    other = dict(hook_entry)
    other["id"] = "other-hook"
    registry.register(other)
    report = doctor.run(registry, entry_id="example-hook", consent=consented_store)
    assert len(report["entries"]) == 1
    assert report["entries"][0]["id"] == "example-hook"
