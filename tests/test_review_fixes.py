"""Regression tests for the bugs found by the multi-agent review."""

from __future__ import annotations

import json
import threading
from types import SimpleNamespace

import pytest

from app import aliases, config, paths, profiles
from app.pipeline import ProfileRouter, RouteContext
from controller.service import VoiceService
from controller.transcriber import clean_text, is_hallucination
from controller.voice_controller import VoiceController
from tests.test_office_modules import Recorder, make_service


def profile(pid, *phrases, apps=(), language="pl_PL"):
    return profiles.Profile(id=pid, name=pid, apps=list(apps), language=language, commands=[
        profiles.VoiceCommand(id=f"c{i}", phrase=phrase, keys=["r"]) for i, phrase in enumerate(phrases)
    ])


# --- transcript cleaning --------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("E-mail.", "e mail"), ("3,5", "3 5"), ("10:30", "10 30"),
    ("a\nb\tc", "a b c"), ("  Błysk!  ", "błysk"), ("Don't stop", "don t stop"),
])
def test_punctuation_becomes_a_space_and_control_characters_vanish(raw, expected):
    assert clean_text(raw) == expected


def test_a_command_with_a_hyphen_now_matches_what_whisper_says():
    router = ProfileRouter()
    ctx = RouteContext(profile("p", "e-mail"))
    assert router.route(clean_text("E-mail."), ctx) is not None


@pytest.mark.parametrize("text", ["dziękuję za oglądanie", "thanks for watching", "napisy stworzone przez społeczność amara org"])
def test_known_whisper_artefacts_are_dropped(text):
    assert is_hallucination(text, 1.0)


def test_plain_thanks_is_still_a_normal_utterance():
    assert not is_hallucination("dziękuję", 1.0)


# --- matching -------------------------------------------------------------

def test_pruned_fuzzy_matching_still_finds_near_misses_and_ignores_long_text():
    ctx = RouteContext(profile("p", "przeładuj", "menu zakupów"), threshold=0.8)
    router = ProfileRouter()
    assert router.route("przeladoj", ctx).command.phrase == "przeładuj"
    assert router.route("menu zakupow " + "x" * 300, ctx) is None


# --- effective profile ----------------------------------------------------

def test_the_selected_profile_wins_while_its_own_program_is_focused(monkeypatch):
    wasd = profile("league-of-legends-wasd", "atak")
    classic = profile("league-of-legends", "atak klasyczny")
    service = make_service(classic)
    service._profiles = profiles.ProfilesDocument(active_profile_id=wasd.id, profiles=[wasd, classic])
    service._settings = config.Settings(auto_profile=True)
    monkeypatch.setattr("controller.service.foreground_process", lambda: "league of legends.exe")
    assert service.status()["effective_profile_id"] == "league-of-legends-wasd"


def test_keys_held_in_one_window_are_released_when_the_profile_changes(monkeypatch):
    word = profile("word", "pogrub", apps=["winword.exe"])
    service = make_service(word)
    service._settings = config.Settings(auto_profile=True)
    recorder = service._key_controller
    recorder.released = 0
    recorder.release_all = lambda: setattr(recorder, "released", recorder.released + 1)
    monkeypatch.setattr("controller.service.foreground_process", lambda: "")
    service.handle_transcript("zapisz")
    monkeypatch.setattr("controller.service.foreground_process", lambda: "winword.exe")
    service.handle_transcript("pogrub")
    assert recorder.released == 1


def test_disabling_dictation_clears_a_running_dictation():
    service = make_service()
    service.handle_transcript("dyktuj")
    assert service.status()["dictating"]
    service._settings = config.Settings(disabled_modules=["dictation"])
    service.handle_transcript("cokolwiek")
    assert service.status()["dictating"] is False


# --- locking --------------------------------------------------------------

def test_starting_to_listen_does_not_block_status_calls():
    entered, release = threading.Event(), threading.Event()

    class SlowController:
        is_listening = False
        settings = None

        def start_listening(self):
            entered.set()
            release.wait(10)
            self.is_listening = True
            return True

        def stop_listening(self):
            self.is_listening = False

    service = make_service()
    service._controller = SlowController()
    starter = threading.Thread(target=service.start, daemon=True)
    starter.start()
    assert entered.wait(5)
    answered = []
    reader = threading.Thread(target=lambda: answered.append(service.status()), daemon=True)
    reader.start()
    reader.join(3)
    release.set()
    starter.join(5)
    assert answered, "status() waited for the microphone to start"
    assert service.status()["listening"] is True


# --- settings -------------------------------------------------------------

def test_unsupported_setting_values_are_dropped_instead_of_breaking_startup():
    paths.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    paths.CONFIG_FILE.write_text(json.dumps({
        "language": "ru_RU", "theme": "auto", "audio_device": 2, "engine_id": "whisper-base", "check_updates": False,
    }), encoding="utf-8")
    config.reset_cache()
    loaded = config.load()
    assert loaded.language == "pl_PL" and loaded.theme == "light"
    assert loaded.engine_id == "whisper-base" and loaded.check_updates is False


def test_concurrent_settings_updates_do_not_lose_changes():
    config.reset_cache()
    keys = [("matching_threshold", 0.5), ("check_updates", False), ("start_with_windows", True), ("theme", "dark")]
    threads = [threading.Thread(target=config.update, args=({key: value},)) for key, value in keys]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    result = config.load(force=True)
    assert (result.matching_threshold, result.check_updates, result.start_with_windows, result.theme) == (0.5, False, True, "dark")


# --- profiles and aliases -------------------------------------------------

def test_old_profile_files_with_odd_program_names_still_load():
    loaded = profiles.Profile(id="p", name="P", apps=["notepad", "chrome.exe", "a;b.exe"], commands=[])
    assert loaded.apps == ["chrome.exe"]


def test_an_unreadable_alias_file_is_never_rewritten_empty(monkeypatch):
    aliases.teach("p", "zapis", "save")
    original = (paths.CONFIG_DIR / "aliases.json").read_text(encoding="utf-8")
    real_read = type(paths.CONFIG_DIR).read_text

    def locked(self, *args, **kwargs):
        if self.name == "aliases.json":
            raise PermissionError("locked by antivirus")
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(type(paths.CONFIG_DIR), "read_text", locked)
    with pytest.raises(OSError):
        aliases.teach("p", "inna fraza", "save")
    monkeypatch.undo()
    assert (paths.CONFIG_DIR / "aliases.json").read_text(encoding="utf-8") == original


def test_a_correction_never_shadows_a_phrase_added_later():
    service = make_service()
    service.teach_alias("zapis", "save")
    service.document.active_profile.commands.append(
        profiles.VoiceCommand(id="zapis-cmd", phrase="zapis", keys=["f5"])
    )
    assert service.test_command("zapis")["command"]["id"] == "zapis-cmd"


# --- audio ----------------------------------------------------------------

def test_one_utterance_is_cut_after_eight_seconds_of_continuous_sound():
    controller = VoiceController(settings=config.Settings(), transcriber=SimpleNamespace(), on_text=None)
    controller.is_listening = True
    controller.vad = SimpleNamespace(is_speech=lambda *_: True)
    chunk = SimpleNamespace(tobytes=lambda: b"\x01\x00" * controller.CHUNK_SIZE)
    for _ in range(controller.MAX_SPEECH_CHUNKS + 50):
        controller._audio_stream_callback(chunk, controller.CHUNK_SIZE, None, None)
    assert controller.audio_queue.qsize() == 1
    assert len(controller.audio_queue.get_nowait()) == controller.MAX_SPEECH_CHUNKS * controller.CHUNK_SIZE * 2
    assert len(controller.speech_buffer) < controller.MAX_SPEECH_CHUNKS
