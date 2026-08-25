from __future__ import annotations

import pytest

from hook_master.registry import HookRegistry, RegistryError


def test_init_creates_empty_registry(tmp_path):
    registry = HookRegistry(tmp_path / "r.json")
    path = registry.init()
    assert path.exists()
    assert registry.load()["entries"] == []


def test_register_and_get(registry, hook_entry):
    registry.register(hook_entry)
    assert registry.get("example-hook")["title"] == "Example Hook"


def test_register_duplicate_without_replace_raises(registry, hook_entry):
    registry.register(hook_entry)
    with pytest.raises(RegistryError, match="existiert bereits"):
        registry.register(hook_entry)


def test_register_duplicate_with_replace_overwrites(registry, hook_entry):
    registry.register(hook_entry)
    updated = dict(hook_entry)
    updated["title"] = "Renamed"
    registry.register(updated, replace=True)
    assert registry.get("example-hook")["title"] == "Renamed"


def test_search_by_event(registry, hook_entry):
    registry.register(hook_entry)
    assert len(registry.search(event="PreToolUse")) == 1
    assert registry.search(event="Stop") == []


def test_search_by_agent(registry, hook_entry):
    registry.register(hook_entry)
    assert len(registry.search(agent="claude-code")) == 1
    assert registry.search(agent="codex") == []


def test_verify_ok_when_hash_matches(registry, hook_entry):
    registry.register(hook_entry)
    result = registry.verify()
    assert result["ok"] is True
    assert result["checks"][0]["state"] == "ok"


def test_verify_detects_hash_mismatch(registry, hook_entry, canonical_script):
    registry.register(hook_entry)
    canonical_script.write_text("# tampered\n", encoding="utf-8")
    result = registry.verify()
    assert result["ok"] is False
    assert result["checks"][0]["state"] == "hash-mismatch"


def test_verify_detects_missing_source(registry, hook_entry, canonical_script):
    registry.register(hook_entry)
    canonical_script.unlink()
    result = registry.verify()
    assert result["checks"][0]["state"] == "missing"


def test_load_rejects_wrong_schema(tmp_path):
    path = tmp_path / "r.json"
    path.write_text('{"schema": "wrong", "entries": []}', encoding="utf-8")
    registry = HookRegistry(path)
    with pytest.raises(RegistryError, match="Ungueltiges Registry-Format"):
        registry.load()
