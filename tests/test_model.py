from __future__ import annotations

import pytest

from hook_master.model import ValidationError, validate_entry


def test_valid_hook_entry_passes(hook_entry):
    assert validate_entry(dict(hook_entry))["id"] == "example-hook"


def test_missing_required_field_rejected(hook_entry):
    entry = dict(hook_entry)
    del entry["event"]
    with pytest.raises(ValidationError, match="Fehlende Felder"):
        validate_entry(entry)


def test_forbidden_content_key_rejected(hook_entry):
    entry = dict(hook_entry)
    entry["script_text"] = "print(1)"
    with pytest.raises(ValidationError, match="Skript-Volltext"):
        validate_entry(entry)


def test_unknown_event_rejected(hook_entry):
    entry = dict(hook_entry)
    entry["event"] = "NotARealEvent"
    with pytest.raises(ValidationError, match="event-Wert"):
        validate_entry(entry)


def test_canonical_source_requires_hash(hook_entry):
    entry = dict(hook_entry)
    entry["source"] = {"kind": "canonical", "uri": "/some/path.py"}
    with pytest.raises(ValidationError, match="source.hash"):
        validate_entry(entry)


def test_consumer_kind_requires_external_module_source(hook_entry):
    entry = dict(hook_entry)
    entry["kind"] = "consumer"
    with pytest.raises(ValidationError, match="source.kind=external-module"):
        validate_entry(entry)


def test_consumer_entry_with_external_module_source_valid():
    entry = {
        "id": "consumer:memoryhooker",
        "kind": "consumer",
        "title": "memoryhooker",
        "event": "SessionStart",
        "source": {"kind": "external-module", "module": "memoryhooker"},
        "targets": [{"agent": "claude-code", "config_path": "~/.claude/settings.json"}],
        "consumers": ["memoryhooker"],
        "status": "active",
        "adoption": {"laptop": "adopted"},
    }
    assert validate_entry(entry)["kind"] == "consumer"


def test_canonical_hook_target_requires_deploy_path(hook_entry):
    entry = dict(hook_entry)
    entry["targets"] = [{"agent": "claude-code", "config_path": "~/.claude/settings.json"}]
    with pytest.raises(ValidationError, match="deploy_path"):
        validate_entry(entry)


def test_unknown_agent_rejected(hook_entry):
    entry = dict(hook_entry)
    entry["targets"][0]["agent"] = "not-an-agent"
    with pytest.raises(ValidationError, match="target.agent"):
        validate_entry(entry)


def test_unknown_adoption_status_rejected(hook_entry):
    entry = dict(hook_entry)
    entry["adoption"] = {"laptop": "not-a-real-status"}
    with pytest.raises(ValidationError, match="adoption"):
        validate_entry(entry)


def test_doctor_fields_optional_but_validated_when_present(hook_entry):
    entry = dict(hook_entry)
    entry["doctor"] = {"exec_check": True, "mtime_policy": "warn-if-newer-than-deploy", "allowlist": ["Bash"]}
    assert validate_entry(entry)["doctor"]["exec_check"] is True


def test_doctor_bad_exec_check_type_rejected(hook_entry):
    entry = dict(hook_entry)
    entry["doctor"] = {"exec_check": "yes"}
    with pytest.raises(ValidationError, match="exec_check"):
        validate_entry(entry)
