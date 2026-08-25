from __future__ import annotations

import pytest

from hook_master.consent import ConsentStore
from hook_master.model import sha256_file
from hook_master.registry import HookRegistry


@pytest.fixture
def canonical_script(tmp_path):
    script = tmp_path / "library" / "example_hook.py"
    script.parent.mkdir(parents=True)
    script.write_text("#!/usr/bin/env python3\nprint('hook')\n", encoding="utf-8")
    return script


@pytest.fixture
def hook_entry(canonical_script, tmp_path):
    deploy_target = tmp_path / "deployed" / "example_hook.py"
    return {
        "id": "example-hook",
        "kind": "hook",
        "title": "Example Hook",
        "event": "PreToolUse",
        "source": {
            "kind": "canonical",
            "uri": str(canonical_script),
            "hash": {"algorithm": "sha256", "value": sha256_file(canonical_script)},
        },
        "targets": [{"agent": "claude-code", "config_path": "~/.claude/settings.json", "deploy_path": str(deploy_target)}],
        "consumers": [],
        "status": "active",
        "adoption": {"laptop": "adopted"},
    }


@pytest.fixture
def registry(tmp_path):
    return HookRegistry(tmp_path / "registry.json")


@pytest.fixture
def consent_store(tmp_path):
    return ConsentStore(tmp_path / "allowlist.json")


@pytest.fixture
def consented_store(tmp_path, hook_entry):
    """Ein ConsentStore, in dem `hook_entry`'s id bereits freigegeben ist --
    fuer Tests, die die Materialisierung selbst pruefen (nicht die
    Consent-Gate) und deshalb nicht bei jedem `deploy()` extra granten wollen."""
    store = ConsentStore(tmp_path / "allowlist.json")
    store.grant(hook_entry["id"], by="test-fixture")
    return store
