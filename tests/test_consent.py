from __future__ import annotations

from hook_master.consent import ConsentStore


def test_unknown_entry_is_not_consented_fail_closed(tmp_path):
    store = ConsentStore(tmp_path / "allowlist.json")
    assert store.is_consented("never-seen") is False


def test_missing_file_reads_as_empty_fail_open(tmp_path):
    store = ConsentStore(tmp_path / "does" / "not" / "exist.json")
    assert store.load() == {}
    assert store.is_consented("anything") is False


def test_corrupt_file_reads_as_empty_fail_open(tmp_path):
    path = tmp_path / "allowlist.json"
    path.write_text("{not valid json", encoding="utf-8")
    store = ConsentStore(path)
    assert store.load() == {}


def test_wrong_schema_reads_as_empty_fail_open(tmp_path):
    path = tmp_path / "allowlist.json"
    path.write_text('{"schema": "wrong", "entries": {}}', encoding="utf-8")
    store = ConsentStore(path)
    assert store.load() == {}


def test_grant_makes_entry_consented(tmp_path):
    store = ConsentStore(tmp_path / "allowlist.json")
    store.grant("my-hook", by="lukas", note="reviewed")
    assert store.is_consented("my-hook") is True
    record = store.load()["my-hook"]
    assert record.consented_by == "lukas"
    assert record.note == "reviewed"


def test_revoke_makes_entry_not_consented(tmp_path):
    store = ConsentStore(tmp_path / "allowlist.json")
    store.grant("my-hook")
    store.revoke("my-hook")
    assert store.is_consented("my-hook") is False


def test_seed_grandfathered_grants_all_listed_ids(tmp_path):
    store = ConsentStore(tmp_path / "allowlist.json")
    store.seed_grandfathered(["a", "b", "c"], note="bereits deployed vor Consent-Pflicht")
    assert store.is_consented("a") is True
    assert store.is_consented("b") is True
    assert store.is_consented("c") is True
    assert store.load()["a"].consented_by == "grandfathered"


def test_persists_across_new_store_instances(tmp_path):
    path = tmp_path / "allowlist.json"
    ConsentStore(path).grant("persisted-hook")
    assert ConsentStore(path).is_consented("persisted-hook") is True
