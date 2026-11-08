"""Program icons, the built-in program mapping and the profile-icon endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import app_icons, config, profiles
from app.known_apps import apps_for
from tests.test_office_modules import make_service


def profile(pid, *phrases, apps=()):
    return profiles.Profile(id=pid, name=pid, apps=list(apps), commands=[
        profiles.VoiceCommand(id=f"c{i}", phrase=phrase, keys=["r"]) for i, phrase in enumerate(phrases)
    ])


def test_known_mapping_applies_only_without_explicit_apps():
    assert apps_for(profile("google-chrome")) == ("chrome.exe",)
    assert apps_for(profile("google-chrome-en")) == ("chrome.exe",)
    assert apps_for(profile("google-chrome", apps=["Brave.exe"])) == ("brave.exe",)
    assert apps_for(profile("my-own-profile")) == ()


def test_old_profile_without_apps_still_switches_by_program(monkeypatch):
    chrome = profile("google-chrome", "nowa karta")
    service = make_service(chrome)
    service._settings = config.Settings(auto_profile=True)
    monkeypatch.setattr("controller.service.foreground_process", lambda: "chrome.exe")
    service.handle_transcript("nowa karta")
    assert service._key_controller.calls == [("keys", ("c0", ["r"], "click", 3000))]
    assert service.status()["effective_profile_id"] == "google-chrome"


def test_explicit_apps_beat_the_builtin_mapping(monkeypatch):
    builtin = profile("google-chrome", "stara komenda")
    explicit = profile("office-browser", "nowa komenda", apps=["chrome.exe"])
    service = make_service(builtin, explicit)
    service._settings = config.Settings(auto_profile=True)
    monkeypatch.setattr("controller.service.foreground_process", lambda: "chrome.exe")
    assert service.status()["effective_profile_id"] == "office-browser"


@pytest.mark.parametrize("name", ["calc.exe", "My App.exe", "a-b_c.1.exe"])
def test_plain_program_names_are_accepted(name):
    assert app_icons.valid_exe(name)


@pytest.mark.parametrize("name", ["x; calc.exe", "..\\evil.exe", "a/b.exe", "notepad", "$(x).exe", ""])
def test_names_that_could_reach_the_shell_are_rejected(name):
    assert not app_icons.valid_exe(name)
    assert app_icons.icon_for((name,)) is None


def test_failed_lookup_is_remembered_instead_of_spawning_powershell_again(monkeypatch):
    calls = []
    monkeypatch.setattr(app_icons, "_extract", lambda exe, target: calls.append(exe) or False)
    monkeypatch.setattr(app_icons.sys, "platform", "win32")
    app_icons._misses.clear()
    assert app_icons.icon_for(("ghost.exe",)) is None
    assert app_icons.icon_for(("ghost.exe",)) is None
    assert calls == ["ghost.exe"]


def test_icon_cache_lives_under_the_app_cache_directory():
    from app import paths

    assert Path(app_icons._cache_file("Chrome.exe")).parent.parent == paths.CACHE_DIR


def test_concurrent_lookups_of_one_program_extract_it_once(monkeypatch):
    import threading
    import time

    calls = []

    def slow_extract(exe, target):
        calls.append(exe)
        time.sleep(0.2)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"png")
        return True

    monkeypatch.setattr(app_icons, "_extract", slow_extract)
    monkeypatch.setattr(app_icons.sys, "platform", "win32")
    app_icons._misses.clear()
    results = []
    threads = [threading.Thread(target=lambda: results.append(app_icons.icon_for(("Chrome.exe",)))) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(calls) == 1 and all(results)
