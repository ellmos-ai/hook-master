from __future__ import annotations

from hook_master import materialize
from hook_master.consent import ConsentStore


def test_deploy_writes_missing_target(registry, hook_entry, consented_store):
    registry.register(hook_entry)
    results = materialize.deploy(registry, consent=consented_store)
    assert len(results) == 1
    assert results[0].action == "written"
    deployed = list(materialize.diff(registry))[0]
    assert deployed["state"] == "in-sync"


def test_deploy_is_idempotent(registry, hook_entry, consented_store):
    registry.register(hook_entry)
    materialize.deploy(registry, consent=consented_store)
    second = materialize.deploy(registry, consent=consented_store)
    assert second[0].action == "unchanged"


def test_deploy_dry_run_does_not_write(registry, hook_entry, consented_store):
    registry.register(hook_entry)
    results = materialize.deploy(registry, dry_run=True, consent=consented_store)
    assert results[0].action == "written"
    from hook_master.model import expand_uri

    deploy_path = expand_uri(hook_entry["targets"][0]["deploy_path"])
    assert not deploy_path.exists()


def test_diff_detects_drift(registry, hook_entry, consented_store):
    registry.register(hook_entry)
    materialize.deploy(registry, consent=consented_store)
    from hook_master.model import expand_uri

    deployed = expand_uri(hook_entry["targets"][0]["deploy_path"])
    deployed.write_text("# drifted locally\n", encoding="utf-8")
    rows = materialize.diff(registry)
    assert rows[0]["state"] == "drifted"


def test_diff_reports_not_deployed(registry, hook_entry):
    registry.register(hook_entry)
    rows = materialize.diff(registry)
    assert rows[0]["state"] == "not-deployed"


def test_status_combines_verify_and_diff(registry, hook_entry, consented_store):
    registry.register(hook_entry)
    materialize.deploy(registry, consent=consented_store)
    result = materialize.status(registry)
    assert result["ok"] is True
    assert result["registry"]["ok"] is True
    assert result["materialization"][0]["state"] == "in-sync"


def test_deploy_by_entry_id_filters(registry, hook_entry, consented_store, tmp_path):
    registry.register(hook_entry)
    other = dict(hook_entry)
    other["id"] = "other-hook"
    registry.register(other, replace=False)
    consented_store.grant("other-hook")
    results = materialize.deploy(registry, entry_id="example-hook", consent=consented_store)
    assert len(results) == 1
    assert results[0].entry_id == "example-hook"


# --- HE2: Consent-Gate (T-20260825-519184830) -------------------------------


def test_deploy_without_consent_is_pending_not_written(registry, hook_entry, tmp_path):
    """Fail-closed-Kernverhalten: ein nie freigegebener Eintrag wird NICHT
    materialisiert, sondern als pending-consent gemeldet."""
    registry.register(hook_entry)
    empty_consent = ConsentStore(tmp_path / "empty-allowlist.json")
    results = materialize.deploy(registry, consent=empty_consent)
    assert results[0].action == "pending-consent"
    from hook_master.model import expand_uri

    assert not expand_uri(hook_entry["targets"][0]["deploy_path"]).exists()


def test_deploy_after_consent_grant_writes(registry, hook_entry, tmp_path):
    registry.register(hook_entry)
    store = ConsentStore(tmp_path / "allowlist.json")
    # Erster Versuch: noch nicht freigegeben.
    first = materialize.deploy(registry, consent=store)
    assert first[0].action == "pending-consent"
    # Consent erteilen, dann klappt derselbe deploy()-Aufruf.
    store.grant(hook_entry["id"])
    second = materialize.deploy(registry, consent=store)
    assert second[0].action == "written"


def test_deploy_with_default_consent_store_is_pending_when_ids_unknown(registry, hook_entry, monkeypatch, tmp_path):
    """Ohne explizit uebergebenen ConsentStore greift der Default-Pfad -- auch
    dort gilt fail-closed fuer einen frischen, nie zuvor gesehenen Eintrag."""
    monkeypatch.setenv("HOOK_MASTER_ALLOWLIST_PATH", str(tmp_path / "default-allowlist.json"))
    registry.register(hook_entry)
    results = materialize.deploy(registry)
    assert results[0].action == "pending-consent"
