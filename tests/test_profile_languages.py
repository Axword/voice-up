"""Profile locales drive recognition independently of the panel locale."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app import config, paths, profiles
from controller.service import VoiceService

LANGUAGES = ("pl_PL", "en_US", "de_DE", "es_ES", "fr_FR", "uk_UA")


@pytest.fixture
def bilingual_document(monkeypatch):
    document = profiles.ProfilesDocument(active_profile_id="polish", profiles=[
        profiles.Profile(id="polish", name="Polski", language="pl_PL", commands=[
            profiles.VoiceCommand(id="move", phrase="naprzód", keys=["w"], mode="toggle"),
        ]),
        profiles.Profile(id="english", name="English", language="en_US", commands=[
            profiles.VoiceCommand(id="move", phrase="forward", keys=["w"], mode="toggle"),
        ]),
    ])
    monkeypatch.setattr(profiles, "catalog_profiles", lambda: [p.model_copy(deep=True) for p in document.profiles])
    return document


class AudioController:
    def __init__(self, settings):
        self.settings = settings
        self.is_listening = False
        self.events = []

    def start_listening(self):
        self.events.append(("start", self.settings.language))
        self.is_listening = True
        return True

    def stop_listening(self):
        self.events.append(("stop", self.settings.language))
        self.is_listening = False


def test_legacy_profiles_without_language_default_to_polish(bilingual_document):
    raw = bilingual_document.model_dump()
    for profile in raw["profiles"]:
        profile.pop("language")
    target = paths.CONFIG_DIR / "profiles.json"
    target.write_text(json.dumps(raw), encoding="utf-8")
    loaded = profiles.load()
    assert [profile.language for profile in loaded.profiles] == ["pl_PL", "pl_PL"]
    assert loaded.active_profile_id == raw["active_profile_id"]
    assert loaded.profiles[1].commands[0].phrase == "forward"


@pytest.mark.parametrize("language", LANGUAGES)
def test_supported_languages_validate_and_round_trip(language):
    value = profiles.Profile(id="custom", name="Custom", language=language)
    assert profiles.Profile.model_validate_json(value.model_dump_json()).language == language
    settings = config.Settings(language=language, ui_language=language)
    assert config.save(settings).ui_language == language
    config.reset_cache()
    assert config.load().model_dump() == settings.model_dump()


@pytest.mark.parametrize("language", ["en", "it_IT", "telepathy", None])
def test_unsupported_profile_or_panel_language_is_rejected(language):
    with pytest.raises(ValidationError):
        profiles.Profile(id="custom", name="Custom", language=language)
    with pytest.raises(ValidationError):
        config.Settings(ui_language=language)


@pytest.mark.parametrize("entrypoint", ["settings", "document", "profiles_document"])
def test_initialization_uses_saved_active_profile_language(bilingual_document, entrypoint):
    bilingual_document.active_profile_id = "english"
    profiles.save(bilingual_document)
    config.save(config.Settings(language="pl_PL", ui_language="de_DE"))
    service = VoiceService()
    result = getattr(service, entrypoint)
    if callable(result):
        result()
    assert service.settings.language == "en_US"
    assert service.settings.ui_language == "de_DE"
    assert config.load(force=True).language == "en_US"
    assert service._controller is None
    assert not service.listening


def test_switching_profiles_changes_recognizer_language_and_preserves_listening(bilingual_document):
    profiles.save(bilingual_document)
    config.save(config.Settings(ui_language="uk_UA"))
    service = VoiceService()
    audio = AudioController(service.settings)
    service._controller = audio
    released = []
    service._key_controller = SimpleNamespace(release_all=lambda: released.append(True))
    assert service.start()
    payload = service.profiles_document()
    payload["active_profile_id"] = "english"
    saved = service.replace_profiles(payload)
    assert saved["profiles"][1]["language"] == "en_US"
    assert audio.events == [("start", "pl_PL"), ("stop", "pl_PL"), ("start", "en_US")]
    assert released
    assert service.listening
    assert service.settings.language == audio.settings.language == "en_US"
    assert service.settings.ui_language == "uk_UA"
    assert config.load(force=True).language == "en_US"
    payload["active_profile_id"] = "polish"
    service.replace_profiles(payload)
    assert audio.events[-2:] == [("stop", "en_US"), ("start", "pl_PL")]
    assert service.settings.ui_language == "uk_UA"


def test_changing_language_of_active_profile_restarts_audio(bilingual_document):
    profiles.save(bilingual_document)
    service = VoiceService()
    audio = AudioController(service.settings)
    service._controller = audio
    assert service.start()
    payload = service.profiles_document()
    payload["profiles"][0]["language"] = "fr_FR"
    service.replace_profiles(payload)
    assert service.listening
    assert audio.events == [("start", "pl_PL"), ("stop", "pl_PL"), ("start", "fr_FR")]
    assert profiles.load().active_profile.language == "fr_FR"


def test_switching_when_stopped_does_not_start_audio(bilingual_document):
    profiles.save(bilingual_document)
    service = VoiceService()
    audio = AudioController(service.settings)
    service._controller = audio
    payload = service.profiles_document()
    payload["active_profile_id"] = "english"
    service.replace_profiles(payload)
    assert not service.listening
    assert all(event[0] != "start" for event in audio.events)
    assert audio.settings.language == "en_US"


def test_start_synchronizes_language_before_controller_starts(bilingual_document):
    bilingual_document.active_profile_id = "english"
    profiles.save(bilingual_document)
    config.save(config.Settings(language="pl_PL", ui_language="es_ES"))
    service = VoiceService()
    service._controller = AudioController(config.load())
    assert service.start()
    assert service._controller.events == [("start", "en_US")]
    assert service._controller.settings.ui_language == "es_ES"


def test_sample_transcription_uses_active_profile_language(bilingual_document):
    bilingual_document.active_profile_id = "english"
    profiles.save(bilingual_document)
    service = VoiceService()
    languages = []
    service._controller = AudioController(config.load())
    service._controller.transcriber = SimpleNamespace(
        transcribe_pcm=lambda pcm, language: languages.append(language) or "forward"
    )
    assert service._transcribe(b"sample") == "forward"
    assert languages == ["en_US"]
    assert not service.listening


def test_panel_preferences_do_not_override_profile_language_from_stale_settings(bilingual_document):
    bilingual_document.active_profile_id = "english"
    profiles.save(bilingual_document)
    stale = config.update({"language": "pl_PL", "ui_language": "de_DE", "theme": "dark"})
    service = VoiceService()
    service.apply_settings(stale)
    assert service.settings.language == "en_US"
    assert service.settings.ui_language == "de_DE"
    assert service.settings.theme == "dark"
    assert profiles.load().active_profile.language == "en_US"
    assert config.load(force=True).language == "en_US"


def test_legacy_recognition_setting_updates_only_active_profile_and_restarts(bilingual_document):
    profiles.save(bilingual_document)
    service = VoiceService()
    service._controller = AudioController(service.settings)
    assert service.start()
    updated = config.update({"language": "de_DE", "ui_language": "fr_FR"})
    service.apply_settings(updated, profile_language=True)
    assert service.document.active_profile.language == "de_DE"
    assert service.document.profiles[1].language == "en_US"
    assert service.settings.language == service._controller.settings.language == "de_DE"
    assert service.settings.ui_language == "fr_FR"
    assert service.listening
    assert service._controller.events[-2:] == [("stop", "pl_PL"), ("start", "de_DE")]
    assert profiles.load().active_profile.language == "de_DE"
    assert config.load(force=True).language == "de_DE"


def test_panel_language_change_keeps_audio_running_without_restart(bilingual_document):
    profiles.save(bilingual_document)
    service = VoiceService()
    service._controller = AudioController(service.settings)
    assert service.start()
    service.apply_settings(config.update({"ui_language": "es_ES"}))
    assert service._controller.events == [("start", "pl_PL")]
    assert service.listening
    assert service.settings.ui_language == "es_ES"
    assert profiles.load().active_profile.language == "pl_PL"


def test_settings_endpoint_reports_profile_locale_and_legacy_patch_updates_profile(api_client, bilingual_document):
    bilingual_document.active_profile_id = "english"
    profiles.save(bilingual_document)
    response = api_client.get("/api/v1/settings")
    assert response.status_code == 200
    assert response.json()["language"] == "en_US"
    response = api_client.put("/api/v1/settings", json={"language": "fr_FR", "ui_language": "de_DE"})
    assert response.status_code == 200
    assert response.json()["language"] == "fr_FR"
    assert response.json()["ui_language"] == "de_DE"
    assert profiles.load().active_profile.language == "fr_FR"


def test_profile_endpoint_persists_locale_and_refreshes_settings(api_client, bilingual_document):
    profiles.save(bilingual_document)
    payload = api_client.get("/api/v1/profiles").json()
    payload["active_profile_id"] = "english"
    response = api_client.put("/api/v1/profiles", json=payload)
    assert response.status_code == 200
    assert response.json()["profiles"][1]["language"] == "en_US"
    assert api_client.get("/api/v1/settings").json()["language"] == "en_US"
    assert profiles.load().active_profile.language == "en_US"


def test_invalid_profile_language_never_replaces_saved_profiles(bilingual_document):
    profiles.save(bilingual_document)
    target = paths.CONFIG_DIR / "profiles.json"
    before = target.read_bytes()
    payload = bilingual_document.model_dump()
    payload["profiles"][0]["language"] = "unsupported"
    with pytest.raises(ValidationError):
        VoiceService().replace_profiles(payload)
    assert target.read_bytes() == before
