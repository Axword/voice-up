"""Shipped library validation and non-destructive, one-time profile migration."""

from __future__ import annotations

import copy
import json
import string

import pytest
from pydantic import ValidationError

from app import paths, profiles


def _profile(profile_id: str, **changes) -> dict:
    return {
        "id": profile_id,
        "name": profile_id,
        "game": "Test",
        "commands": [{"id": "action", "phrase": "akcja", "keys": ["q"], "mode": "click"}],
        **changes,
    }


@pytest.fixture
def catalog(monkeypatch):
    entries = [_profile("built-one"), _profile("built-two")]
    monkeypatch.setattr(profiles, "catalog_profiles", lambda: [profiles.Profile.model_validate(p) for p in entries])
    return entries


@pytest.fixture
def user_document():
    return {
        "version": 1,
        "active_profile_id": "my-profile",
        "profiles": [_profile("my-profile", name="Mój profil")],
    }


def _state_path():
    return paths.CONFIG_DIR / "profile-library-state.json"


def _state():
    return json.loads(_state_path().read_text(encoding="utf-8"))


def _write_shards(root, entries):
    data = root / "data"
    data.mkdir()
    shards = [*entries, *([] for _ in range(len(profiles.LIBRARY_FILES) - len(entries)))]
    for filename, value in zip(profiles.LIBRARY_FILES, shards, strict=True):
        (data / filename).write_text(json.dumps(value), encoding="utf-8")


def test_new_installation_receives_the_entire_catalog(catalog):
    document = profiles.load()
    assert [item.id for item in document.profiles] == ["built-one", "built-two"]
    assert document.active_profile_id == "built-one"
    assert _state() == {"schema": 1, "seen_catalog_ids": ["built-one", "built-two"]}


def test_existing_profiles_commands_order_and_active_profile_are_preserved(catalog, user_document):
    altered = _profile("built-two", name="Moja własna nazwa", game="Inna gra")
    altered["commands"][0].update(keys=["shift", "x"], mode="toggle", enabled=False, duration_ms=7000)
    user_document["profiles"].insert(0, altered)
    expected = copy.deepcopy(user_document)
    profiles.save(user_document)
    merged = profiles.load().model_dump()
    assert merged["active_profile_id"] == expected["active_profile_id"]
    assert [item["id"] for item in merged["profiles"]] == ["built-two", "my-profile", "built-one"]
    original = profiles.ProfilesDocument.model_validate(expected).model_dump()
    assert merged["profiles"][:2] == original["profiles"]


def test_migration_appends_only_once_and_does_not_modify_the_callers_document(catalog, user_document):
    expected = copy.deepcopy(user_document)
    first = profiles.synchronize_library(user_document)
    second = profiles.synchronize_library(first)
    assert first == second
    assert user_document == expected
    assert len(first.profiles) == 3


def test_user_deleted_builtin_stays_deleted_on_later_load(catalog):
    document = profiles.load().model_dump()
    document["profiles"] = document["profiles"][:1]
    profiles.save(document)
    assert [profile.id for profile in profiles.load().profiles] == ["built-one"]
    assert "built-two" in _state()["seen_catalog_ids"]


def test_later_catalog_additions_arrive_without_restoring_deleted_profiles(catalog):
    document = profiles.load().model_dump()
    document["profiles"] = document["profiles"][:1]
    profiles.save(document)
    catalog.append(_profile("built-three"))
    merged = profiles.load()
    assert [profile.id for profile in merged.profiles] == ["built-one", "built-three"]
    assert _state()["seen_catalog_ids"] == ["built-one", "built-two", "built-three"]


def test_retired_catalog_ids_remain_in_the_ledger(catalog):
    profiles.load()
    catalog.pop()
    profiles.load()
    assert _state()["seen_catalog_ids"] == ["built-one", "built-two"]


def test_corrupted_user_document_is_never_overwritten_or_migrated(catalog):
    target = paths.CONFIG_DIR / "profiles.json"
    target.write_bytes(b"{corrupt-user-data")
    with pytest.raises(ValidationError):
        profiles.load()
    assert target.read_bytes() == b"{corrupt-user-data"
    assert not _state_path().exists()
    assert not (paths.CONFIG_DIR / "profiles.before-library.json").exists()


@pytest.mark.parametrize("contents", ["{bad-ledger", '{"schema":2,"seen_catalog_ids":[]}',
    '{"schema":1,"seen_catalog_ids":["built-one","built-one"]}'])
def test_corrupted_ledger_does_not_overwrite_itself_or_valid_profiles(catalog, user_document, contents):
    profiles.save(user_document)
    before = (paths.CONFIG_DIR / "profiles.json").read_bytes()
    _state_path().write_text(contents, encoding="utf-8")
    with pytest.raises(ValidationError):
        profiles.load()
    assert _state_path().read_text(encoding="utf-8") == contents
    assert (paths.CONFIG_DIR / "profiles.json").read_bytes() == before
    assert not (paths.CONFIG_DIR / "profiles.before-library.json").exists()


def test_corrupted_ledger_does_not_create_a_new_profiles_document(catalog):
    _state_path().write_text("{broken", encoding="utf-8")
    with pytest.raises(ValidationError):
        profiles.load()
    assert not (paths.CONFIG_DIR / "profiles.json").exists()


def test_first_migration_backs_up_original_file_once(catalog, user_document):
    target = paths.CONFIG_DIR / "profiles.json"
    original = json.dumps(user_document, ensure_ascii=False).encode("utf-8")
    target.write_bytes(original)
    profiles.load()
    backup = paths.CONFIG_DIR / "profiles.before-library.json"
    assert backup.read_bytes() == original
    catalog.append(_profile("built-three"))
    profiles.load()
    assert backup.read_bytes() == original
    assert not backup.with_suffix(".json.tmp").exists()


def test_ledger_is_committed_only_after_a_successful_profile_save(catalog, user_document, monkeypatch):
    profiles.save(user_document)
    original = (paths.CONFIG_DIR / "profiles.json").read_bytes()

    def fail_save(_document):
        raise OSError("disk unavailable")

    monkeypatch.setattr(profiles, "save", fail_save)
    with pytest.raises(OSError, match="disk unavailable"):
        profiles.synchronize_library(user_document)
    assert not _state_path().exists()
    assert (paths.CONFIG_DIR / "profiles.json").read_bytes() == original


def test_failed_later_upgrade_preserves_existing_ledger(catalog, monkeypatch):
    document = profiles.load()
    original = _state_path().read_bytes()
    catalog.append(_profile("built-three"))

    def fail_save(_document):
        raise OSError("disk unavailable")

    monkeypatch.setattr(profiles, "save", fail_save)
    with pytest.raises(OSError, match="disk unavailable"):
        profiles.synchronize_library(document)
    assert _state_path().read_bytes() == original


def test_ledger_write_failure_can_be_retried_without_duplicate_profiles(catalog, user_document, monkeypatch):
    original_writer = profiles._write_state

    def fail_state(_state):
        raise OSError("state unavailable")

    monkeypatch.setattr(profiles, "_write_state", fail_state)
    with pytest.raises(OSError, match="state unavailable"):
        profiles.synchronize_library(user_document)
    assert not _state_path().exists()
    monkeypatch.setattr(profiles, "_write_state", original_writer)
    restored = profiles.load()
    assert [profile.id for profile in restored.profiles] == ["my-profile", "built-one", "built-two"]
    assert _state()["seen_catalog_ids"] == ["built-one", "built-two"]


def test_capacity_limit_preserves_all_user_profiles_and_records_skipped_ids(catalog):
    document = {
        "version": 1,
        "active_profile_id": "custom-50",
        "profiles": [_profile(f"custom-{index}") for index in range(100)],
    }
    profiles.save(document)
    merged = profiles.load().model_dump()
    assert merged == profiles.ProfilesDocument.model_validate(document).model_dump()
    assert _state()["seen_catalog_ids"] == ["built-one", "built-two"]
    merged["profiles"].pop()
    profiles.save(merged)
    assert len(profiles.load().profiles) == 99


def test_one_remaining_slot_uses_catalog_order_and_no_duplicate_id(catalog, user_document):
    user_document["profiles"] = [_profile(f"custom-{index}") for index in range(98)] + [_profile("built-two")]
    user_document["active_profile_id"] = "built-two"
    merged = profiles.synchronize_library(user_document)
    assert len(merged.profiles) == 100
    assert merged.profiles[-1].id == "built-one"
    assert len({profile.id for profile in merged.profiles}) == 100


def test_known_catalog_does_not_rewrite_a_stable_user_file(catalog):
    document = profiles.load().model_dump()
    target = paths.CONFIG_DIR / "profiles.json"
    original = json.dumps(document).encode("utf-8")
    target.write_bytes(original)
    profiles.load()
    assert target.read_bytes() == original


@pytest.mark.parametrize("missing", profiles.LIBRARY_FILES)
def test_all_catalog_shards_are_required(tmp_path, monkeypatch, missing):
    _write_shards(tmp_path, [])
    (tmp_path / "data" / missing).unlink()
    monkeypatch.setattr(paths, "bundled_dir", lambda: tmp_path)
    with pytest.raises(FileNotFoundError, match=missing):
        profiles.catalog_profiles()


def test_duplicate_catalog_ids_across_shards_are_rejected(tmp_path, monkeypatch):
    _write_shards(tmp_path, [[_profile("duplicate")], [_profile("duplicate")], []])
    monkeypatch.setattr(paths, "bundled_dir", lambda: tmp_path)
    with pytest.raises(ValueError, match="Powtórzony identyfikator"):
        profiles.catalog_profiles()


def test_non_array_catalog_shard_is_rejected(tmp_path, monkeypatch):
    _write_shards(tmp_path, [{"profiles": []}, [], []])
    monkeypatch.setattr(paths, "bundled_dir", lambda: tmp_path)
    with pytest.raises(ValueError, match="musi zawierać listę"):
        profiles.catalog_profiles()


def test_invalid_catalog_command_does_not_overwrite_profiles(tmp_path, monkeypatch, user_document):
    invalid = _profile("invalid")
    invalid["commands"][0]["keys"] = ["unsupported-key"]
    _write_shards(tmp_path, [[invalid], [], []])
    profiles.save(user_document)
    original = (paths.CONFIG_DIR / "profiles.json").read_bytes()
    monkeypatch.setattr(paths, "bundled_dir", lambda: tmp_path)
    with pytest.raises(ValidationError):
        profiles.load()
    assert (paths.CONFIG_DIR / "profiles.json").read_bytes() == original
    assert not _state_path().exists()


def test_shipped_catalog_is_large_valid_and_preserves_core_order():
    catalog = profiles.catalog_profiles()
    assert len(catalog) >= 20
    assert [profile.id for profile in catalog[:2]] == ["league-of-legends", "minecraft"]
    assert len({profile.id for profile in catalog}) == len(catalog)
    assert all(len(profile.commands) >= 8 for profile in catalog)
    for profile in catalog:
        for command in profile.commands:
            assert all(profiles.normalize_key(key) == key for key in command.keys)
    assert profiles.default_document().active_profile_id == "league-of-legends"


def test_bundle_contains_full_data_docs_and_profile_licenses():
    import build_config

    bundled = set(build_config.bundle_data())
    assert ("data", "data") in bundled
    assert ("docs", "docs") in bundled
    for filename in profiles.LIBRARY_FILES:
        assert (build_config.ROOT_DIR / "data" / filename).is_file()


@pytest.mark.parametrize("missing", profiles.LIBRARY_FILES)
def test_bundle_requires_every_profile_shard(tmp_path, monkeypatch, missing):
    import build_config

    _write_shards(tmp_path, [])
    (tmp_path / "data" / missing).unlink()
    monkeypatch.setattr(build_config, "ROOT_DIR", tmp_path)
    with pytest.raises(FileNotFoundError, match=missing):
        build_config.bundle_data()


@pytest.mark.parametrize("profile_id,language", [("basic-keyboard", "pl_PL"), ("basic-keyboard-en", "en_US")])
def test_baseline_maps_every_letter_digit_and_standard_key_to_a_single_click(profile_id, language):
    profile = next(profile for profile in profiles.catalog_profiles() if profile.id == profile_id)
    assert profile.language == language
    assert profile.game == "Keyboard"
    commands = {command.phrase: command for command in profile.commands}
    assert all(commands[letter].keys == [letter] for letter in string.ascii_lowercase)
    assert all(commands[digit].keys == [digit] for digit in string.digits)
    expected_keys = set(string.ascii_lowercase + string.digits) | {
        "enter", "space", "esc", "tab", "backspace", "delete", "insert", "home", "end", "page_up", "page_down",
        "up", "down", "left", "right", "ctrl", "shift", "alt", "cmd",
        *(f"f{number}" for number in range(1, 13)),
    }
    assert {command.keys[0] for command in profile.commands} == expected_keys
    canonical = [command for command in profile.commands if command.id.startswith("key-")]
    assert len(canonical) == len(expected_keys) == 67
    assert all(command.mode == "click" and len(command.keys) == 1 and command.enabled for command in profile.commands)
    assert len({profiles.normalize_phrase(command.phrase) for command in profile.commands}) == len(profile.commands)


def test_baseline_special_key_phrases_are_localized():
    catalog = {profile.id: profile for profile in profiles.catalog_profiles()}
    polish = {command.phrase: command.keys for command in catalog["basic-keyboard"].commands}
    english = {command.phrase: command.keys for command in catalog["basic-keyboard-en"].commands}
    assert polish["spacja"] == english["space"] == ["space"]
    assert polish["usuń"] == english["delete"] == ["delete"]
    assert polish["strzałka w górę"] == english["arrow up"] == ["up"]
    assert polish["strona w dół"] == english["page down"] == ["page_down"]


@pytest.mark.parametrize("profile_id,letter_names,number_names", [
    ("basic-keyboard",
     ("a", "be", "ce", "de", "e", "ef", "gie", "ha", "i", "jot", "ka", "el", "em", "en", "o", "pe", "ku",
      "er", "es", "te", "u", "fał", "wu", "iks", "igrek", "zet"),
     ("zero", "jeden", "dwa", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem", "dziewięć")),
    ("basic-keyboard-en",
     ("ay", "bee", "cee", "dee", "ee", "ef", "gee", "aitch", "eye", "jay", "kay", "el", "em", "en", "oh", "pee",
      "cue", "ar", "ess", "tee", "you", "vee", "double u", "ex", "why", "zed"),
     ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")),
])
def test_baseline_accepts_spoken_names_of_letters_and_numbers(profile_id, letter_names, number_names):
    profile = next(profile for profile in profiles.catalog_profiles() if profile.id == profile_id)
    phrases = {profiles.normalize_phrase(command.phrase): command for command in profile.commands}
    for key, phrase in zip(string.ascii_lowercase, letter_names, strict=True):
        assert phrases[profiles.normalize_phrase(phrase)].keys == [key]
    for key, phrase in zip(string.digits, number_names, strict=True):
        assert phrases[profiles.normalize_phrase(phrase)].keys == [key]
    assert len(phrases) == len(profile.commands)


def test_baseline_spoken_aliases_use_the_exact_matcher_without_sending_keys():
    from controller.service import VoiceService

    catalog = {profile.id: profile for profile in profiles.catalog_profiles()}
    service = VoiceService()
    service._profiles = profiles.ProfilesDocument(active_profile_id="basic-keyboard", profiles=[
        catalog["basic-keyboard"], catalog["basic-keyboard-en"],
    ])
    assert service.test_command(" WU! ")["command"]["keys"] == ["w"]
    assert service.test_command("pięć")["command"]["keys"] == ["5"]
    assert not service.test_command("naciśnij wu")["matched"]
    service._profiles.active_profile_id = "basic-keyboard-en"
    assert service.test_command("double u")["command"]["keys"] == ["w"]
    assert service.test_command("double you")["command"]["keys"] == ["w"]
    assert service.test_command("nine")["command"]["keys"] == ["9"]
    assert not service.test_command("press double u")["matched"]
    assert service._key_controller is None
