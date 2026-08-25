from __future__ import annotations

from hook_master import materialize


def test_deploy_writes_missing_target(registry, hook_entry):
    registry.register(hook_entry)
    results = materialize.deploy(registry)
    assert len(results) == 1
    assert results[0].action == "written"
    deployed = list(materialize.diff(registry))[0]
    assert deployed["state"] == "in-sync"


def test_deploy_is_idempotent(registry, hook_entry):
    registry.register(hook_entry)
    materialize.deploy(registry)
    second = materialize.deploy(registry)
    assert second[0].action == "unchanged"


def test_deploy_dry_run_does_not_write(registry, hook_entry):
    registry.register(hook_entry)
    results = materialize.deploy(registry, dry_run=True)
    assert results[0].action == "written"
    from hook_master.model import expand_uri

    deploy_path = expand_uri(hook_entry["targets"][0]["deploy_path"])
    assert not deploy_path.exists()


def test_diff_detects_drift(registry, hook_entry):
    registry.register(hook_entry)
    materialize.deploy(registry)
    from hook_master.model import expand_uri

    deployed = expand_uri(hook_entry["targets"][0]["deploy_path"])
    deployed.write_text("# drifted locally\n", encoding="utf-8")
    rows = materialize.diff(registry)
    assert rows[0]["state"] == "drifted"


def test_diff_reports_not_deployed(registry, hook_entry):
    registry.register(hook_entry)
    rows = materialize.diff(registry)
    assert rows[0]["state"] == "not-deployed"


def test_status_combines_verify_and_diff(registry, hook_entry):
    registry.register(hook_entry)
    materialize.deploy(registry)
    result = materialize.status(registry)
    assert result["ok"] is True
    assert result["registry"]["ok"] is True
    assert result["materialization"][0]["state"] == "in-sync"


def test_deploy_by_entry_id_filters(registry, hook_entry):
    registry.register(hook_entry)
    other = dict(hook_entry)
    other["id"] = "other-hook"
    registry.register(other, replace=False)
    results = materialize.deploy(registry, entry_id="example-hook")
    assert len(results) == 1
    assert results[0].entry_id == "example-hook"
