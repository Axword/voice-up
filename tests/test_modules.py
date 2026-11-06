"""Module registry, editions and organization policy."""

from __future__ import annotations

import json

from app import config, modules, paths
from tests.test_office_modules import make_service

API = "/api/v1"


def by_id(items):
    return {item["id"]: item for item in items}


def block(monkeypatch, tmp_path, **rules):
    target = tmp_path / "policy.json"
    target.write_text(json.dumps(rules))
    monkeypatch.setenv("VOICE_CONTROL_POLICY", str(target))


def test_all_builtin_modules_run_by_default_in_the_free_edition():
    assert all(item["enabled"] for item in modules.status([]))


def test_user_can_disable_a_module_but_not_the_core():
    state = by_id(modules.status(["mouse", "profile"]))
    assert state["mouse"]["reason"] == "user" and state["profile"]["enabled"]


def test_disabled_module_stops_routing():
    service = make_service()
    service._settings = config.Settings(disabled_modules=["mouse"])
    assert not service.test_command("mysz w prawo")["matched"]
    service.handle_transcript("dyktuj")
    assert service.status()["dictating"]


def test_policy_blocks_a_module(tmp_path, monkeypatch):
    block(monkeypatch, tmp_path, cloud_enabled=False, disabled_modules=["dictation"])
    state = by_id(modules.status([]))
    assert state["dictation"]["reason"] == "policy" and state["mouse"]["enabled"]
    service = make_service()
    service.handle_transcript("dyktuj")
    assert service.status()["dictating"] is False


def test_cloud_module_is_blocked_by_cloud_policy(tmp_path, monkeypatch):
    block(monkeypatch, tmp_path, cloud_enabled=False)
    extra = modules.Manifest("x", "X", "router", requires_cloud=True)
    monkeypatch.setattr(modules, "BUILTIN", (*modules.BUILTIN, extra))
    assert by_id(modules.status([]))["x"]["reason"] == "policy-cloud"


def test_broken_policy_file_never_locks_the_core(tmp_path, monkeypatch):
    (tmp_path / "policy.json").write_text("{not json")
    monkeypatch.setenv("VOICE_CONTROL_POLICY", str(tmp_path / "policy.json"))
    assert all(item["enabled"] for item in modules.status([]))


def test_edition_gates_modules_and_reads_the_license_file(monkeypatch):
    extra = modules.Manifest("pro-thing", "P", "router", edition="pro")
    monkeypatch.setattr(modules, "BUILTIN", (*modules.BUILTIN, extra))
    assert by_id(modules.status([]))["pro-thing"]["reason"] == "edition"
    (paths.CONFIG_DIR / "license.json").write_text(json.dumps({"edition": "pro"}))
    assert by_id(modules.status([]))["pro-thing"]["enabled"]
    (paths.CONFIG_DIR / "license.json").write_text(json.dumps({"edition": "gold"}))
    assert modules.current_edition() == "free"
