"""Profile validation, persistence and the audio-to-command execution boundary."""

from __future__ import annotations

import json
import threading
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app import paths, profiles
from controller.service import VoiceService


@pytest.fixture
def document():
    return profiles.default_document().model_dump()


def test_profile_json_round_trip_and_active_profile(lolvoice_home):
    first = profiles.load()
    target = paths.CONFIG_DIR / "profiles.json"
    assert target.exists()
    data = first.model_dump()
    data["active_profile_id"] = "minecraft"
    profiles.save(data)
    assert profiles.load().active_profile.name == "Minecraft"
    assert json.loads(target.read_text(encoding="utf-8")) == data
    assert not target.with_suffix(".json.tmp").exists()


def test_corrupted_profile_is_reported_without_overwriting(lolvoice_home):
    target = paths.CONFIG_DIR / "profiles.json"
    target.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValidationError):
        profiles.load()
    assert target.read_text(encoding="utf-8") == "{broken"


@pytest.mark.parametrize("phrase", [" BŁYSK! ", "blysk", "błysk."])
def test_polish_phrase_normalization(phrase):
    assert profiles.normalize_phrase(phrase) == "blysk"


@pytest.mark.parametrize("field,value", [("phrase", "!!!"), ("phrase", "  "), ("keys", []),
    ("keys", ["ctrl", "Control"]), ("keys", ["unsupported"]), ("mode", "sequence"),
    ("duration_ms", 0), ("duration_ms", 60001), ("duration_ms", 3.5)])
def test_invalid_command_is_rejected(document, field, value):
    document["profiles"][0]["commands"][0][field] = value
    with pytest.raises(ValidationError):
        profiles.ProfilesDocument.model_validate(document)


def test_duplicate_normalized_phrases_are_rejected(document):
    command = dict(document["profiles"][0]["commands"][0])
    command.update(id="different-id", phrase=" BLYSK!")
    document["profiles"][0]["commands"].append(command)
    with pytest.raises(ValidationError):
        profiles.ProfilesDocument.model_validate(document)


def test_unknown_active_profile_and_duplicate_ids_are_rejected(document):
    document["active_profile_id"] = "missing"
    with pytest.raises(ValidationError):
        profiles.ProfilesDocument.model_validate(document)
    document["active_profile_id"] = document["profiles"][0]["id"]
    document["profiles"].append(document["profiles"][0])
    with pytest.raises(ValidationError):
        profiles.ProfilesDocument.model_validate(document)


def test_test_command_is_dry_run_and_only_matches_whole_phrase():
    service = VoiceService()
    assert service.test_command("BŁYSK!")["matched"]
    assert service.test_command("BŁYSK!")["command"]["keys"] == ["d"]
    assert not service.test_command("zrób błysk teraz")["matched"]
    assert service._key_controller is None


def test_only_active_profile_and_enabled_commands_match(document):
    service = VoiceService()
    document["profiles"][0]["commands"][0]["enabled"] = False
    service.replace_profiles(document)
    assert not service.test_command("błysk")["matched"]
    assert not service.test_command("ekwipunek")["matched"]
    document["active_profile_id"] = "minecraft"
    service.replace_profiles(document)
    assert service.test_command("ekwipunek")["matched"]


def test_transcribed_audio_uses_same_profile_pipeline_and_emits_result():
    service = VoiceService()
    sent, events = [], []
    service._key_controller = SimpleNamespace(
        execute=lambda *args: sent.append(args) or True,
        held_keys=[], held_command_ids=[], release_all=lambda: None,
    )
    service.set_event_sink(events.append)
    service.set_transcriber(lambda pcm: "ulepsz umiejętność")
    assert service.feed_pcm(b"sample") == "ulepsz umiejętność"
    assert sent == [("level-up", ["ctrl", "q"], "click", 3000)]
    heard = next(event for event in events if event["type"] == "heard")
    assert heard["executed"] is True
    assert heard["matched"] == ["ctrl", "q"]


def test_profile_change_and_stop_release_all_held_inputs(document):
    service = VoiceService()
    calls = []
    service._key_controller = SimpleNamespace(release_all=lambda: calls.append("released"))
    document["active_profile_id"] = "minecraft"
    service.replace_profiles(document)
    service.stop()
    assert len(calls) >= 2


def test_failed_execution_is_not_reported_as_success():
    service = VoiceService()
    service._key_controller = SimpleNamespace(execute=lambda *args: False)
    assert service.handle_transcript("błysk") is None
    assert service._last_command is None
    assert service._last_error


def test_live_transcript_after_stop_cannot_press_or_hold_a_key():
    service = VoiceService()
    assert service._handle_live_transcript("atakuj") is None
    assert service._key_controller is None


def test_stale_audio_from_previous_listening_session_is_ignored():
    from controller.voice_controller import VoiceController

    heard = []
    transcriber = SimpleNamespace(transcribe_pcm=lambda pcm, language: "atakuj")
    controller = VoiceController(transcriber=transcriber, on_text=lambda text, generation: heard.append(text))
    controller.is_listening = True
    controller._generation = 2
    assert controller.process_audio(b"\x00" * 2000, generation=1) == "atakuj"
    assert heard == []
    controller.process_audio(b"\x00" * 2000, generation=2)
    assert heard == ["atakuj"]


def test_switch_profile_releases_real_hold_and_invalidates_captured_audio(document, monkeypatch):
    from controller.voice_controller import VoiceController
    from controls.key_controller import KeyController

    service = VoiceService()
    events = []
    keys = KeyController()
    keys._available = True
    monkeypatch.setattr(keys, "_down", lambda key: events.append(("down", key)))
    monkeypatch.setattr(keys, "_up", lambda key: events.append(("up", key)))
    service._key_controller = keys
    transcriber = SimpleNamespace(loaded=True, transcribe_pcm=lambda pcm, language: "atakuj")
    audio = VoiceController(transcriber=transcriber, on_text=service._handle_live_transcript)
    audio.vad = object()
    monkeypatch.setattr(audio, "_init_audio_stream", lambda: True)
    service._controller = audio
    assert service.start()
    try:
        generation = audio._generation
        service.handle_transcript("atakuj")
        assert keys.held_keys == ["a"]
        document["active_profile_id"] = "minecraft"
        document["profiles"][1]["commands"].append({
            "id": "other-attack", "phrase": "atakuj", "keys": ["w"], "mode": "toggle",
        })
        service.replace_profiles(document)
        assert service.listening
        assert keys.held_keys == []
        assert events == [("down", "a"), ("up", "a")]
        audio.process_audio(b"\x00" * 2000, generation=generation)
        assert events == [("down", "a"), ("up", "a")]
        # Even a callback already queued before the profile switch is rejected.
        assert service._handle_live_transcript("atakuj", generation=generation) is None
        assert events == [("down", "a"), ("up", "a")]
    finally:
        service.stop()


def test_server_preview_flags_do_not_enable_headless_voice_mode():
    import main

    args = main.parse_args(["--no-tray", "--no-browser", "--port", "21337"])
    assert args.no_tray and args.no_browser
    assert not args.cli
    assert args.port == 21337


def test_stop_during_model_loading_stops_the_eventually_created_controller(monkeypatch):
    service = VoiceService()
    loading, allow_load, stop_requested = threading.Event(), threading.Event(), threading.Event()
    controller = SimpleNamespace(is_listening=False)
    controller.start_listening = lambda: setattr(controller, "is_listening", True) or True
    controller.stop_listening = lambda: setattr(controller, "is_listening", False)

    class ObservableLock:
        def __init__(self):
            self.lock = threading.RLock()

        def __enter__(self):
            if threading.current_thread().name == "stop-service":
                stop_requested.set()
            self.lock.acquire()

        def __exit__(self, *args):
            self.lock.release()

    service._lifecycle_lock = ObservableLock()

    def load_controller():
        loading.set()
        assert allow_load.wait(3)
        service._controller = controller
        return controller

    monkeypatch.setattr(service, "_ensure_controller", load_controller)
    start_thread = threading.Thread(target=service.start, name="start-service", daemon=True)
    stop_thread = threading.Thread(target=service.stop, name="stop-service", daemon=True)
    start_thread.start()
    try:
        assert loading.wait(3)
        stop_thread.start()
        assert stop_requested.wait(3)
    finally:
        allow_load.set()
        start_thread.join(3)
        if stop_thread.ident is not None:
            stop_thread.join(3)
    assert not start_thread.is_alive() and not stop_thread.is_alive()
    assert not service.listening
    assert not controller.is_listening


def test_stream_is_closed_even_when_stopping_it_fails():
    from controller.voice_controller import VoiceController

    closed = []
    controller = VoiceController(transcriber=object())
    controller.stream = SimpleNamespace(
        stop=lambda: (_ for _ in ()).throw(OSError("Device disconnected")),
        close=lambda: closed.append(True),
    )
    controller.stop_listening()
    assert closed == [True]
    assert controller.stream is None
