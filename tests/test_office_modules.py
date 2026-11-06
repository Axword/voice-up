"""Dictation, pointer control and per-program profiles, without touching real input."""

from __future__ import annotations

from types import SimpleNamespace

from app import config, profiles
from controller.service import VoiceService


class Recorder:
    def __init__(self):
        self.calls = []
        self.held_keys, self.held_command_ids = [], []

    def execute(self, *args):
        self.calls.append(("keys", args))
        return True

    def type_text(self, text):
        self.calls.append(("type", text))
        return True

    def pointer(self, kind, dx=0, dy=0, amount=0):
        self.calls.append((kind, dx, dy, amount))
        return True

    def release_all(self):
        pass


def make_service(*extra_profiles):
    service = VoiceService()
    service._settings = config.Settings()
    base = profiles.Profile(id="base", name="Base", commands=[
        profiles.VoiceCommand(id="save", phrase="zapisz", keys=["ctrl", "s"]),
        profiles.VoiceCommand(id="klik", phrase="kliknij", keys=["enter"]),
    ])
    service._profiles = profiles.ProfilesDocument(active_profile_id="base", profiles=[base, *extra_profiles])
    service._key_controller = Recorder()
    return service


def test_dictation_types_capitalised_text_until_stop_phrase():
    service = make_service()
    recorder = service._key_controller
    service.handle_transcript("dyktuj")
    assert service.status()["dictating"] is True
    service.handle_transcript("dzień dobry")
    service.handle_transcript("zapisz")  # typed, not executed as a command
    service.handle_transcript("koniec dyktowania")
    assert service.status()["dictating"] is False
    assert recorder.calls == [("type", "Dzień dobry "), ("type", "Zapisz ")]


def test_stopping_listening_ends_dictation():
    service = make_service()
    service.handle_transcript("dictate")
    service.stop()
    assert service.status()["dictating"] is False


def test_mouse_moves_with_default_and_spoken_pixels():
    service = make_service()
    service.handle_transcript("mysz w prawo")
    service.handle_transcript("kursor w górę 250")
    service.handle_transcript("scroll down")
    assert service._key_controller.calls == [("move", 100, 0, 0), ("move", 0, -250, 0), ("scroll", 0, 0, -5)]


def test_profile_command_wins_over_builtin_mouse_phrase():
    service = make_service()
    service.handle_transcript("kliknij")
    assert service._key_controller.calls == [("keys", ("klik", ["enter"], "click", 3000))]


def test_focused_program_selects_its_profile_in_the_same_language(monkeypatch):
    outlook = profiles.Profile(id="outlook", name="Outlook", apps=["Outlook.exe"], commands=[
        profiles.VoiceCommand(id="send", phrase="wyślij", keys=["ctrl", "enter"]),
    ])
    english = profiles.Profile(id="outlook-en", name="Outlook EN", language="en_US", apps=["outlook.exe"], commands=[
        profiles.VoiceCommand(id="send-en", phrase="send", keys=["ctrl", "enter"]),
    ])
    service = make_service(outlook, english)
    service._settings = config.Settings(auto_profile=True)
    monkeypatch.setattr("controller.service.foreground_process", lambda: "outlook.exe")
    assert service.test_command("wyślij")["matched"]
    assert not service.test_command("send")["matched"]
    monkeypatch.setattr("controller.service.foreground_process", lambda: "notepad.exe")
    assert not service.test_command("wyślij")["matched"]


def test_auto_profile_can_be_disabled(monkeypatch):
    outlook = profiles.Profile(id="outlook", name="Outlook", apps=["outlook.exe"], commands=[
        profiles.VoiceCommand(id="send", phrase="wyślij", keys=["ctrl", "enter"]),
    ])
    service = make_service(outlook)
    monkeypatch.setattr("controller.service.foreground_process", lambda: "outlook.exe")
    service._settings = config.Settings(auto_profile=False)
    assert not service.test_command("wyślij")["matched"]


def test_office_library_ships_with_program_names():
    office = [p for p in profiles.catalog_profiles() if p.id.startswith("office-")]
    assert len(office) == 8 and all(p.apps for p in office)


def test_previewing_a_phrase_never_changes_dictation_state():
    service = make_service()
    assert service.test_command("dyktuj")["matched"] is False
    assert service.status()["dictating"] is False
    service.handle_transcript("dyktuj")
    assert service.test_command("zapisz")["command"]["id"] == "save"  # not swallowed by dictation
    service.test_command("koniec dyktowania")
    assert service.status()["dictating"] is True


def test_heard_event_and_teaching_use_the_profile_that_is_in_effect(monkeypatch):
    word = profiles.Profile(id="word", name="Word", apps=["winword.exe"], commands=[
        profiles.VoiceCommand(id="bold", phrase="pogrub", keys=["ctrl", "b"]),
    ])
    service = make_service(word)
    service._settings = config.Settings(auto_profile=True)
    events = []
    service.set_event_sink(events.append)
    monkeypatch.setattr("controller.service.foreground_process", lambda: "winword.exe")
    service.teach_alias("pogrup", "bold")
    service.handle_transcript("pogrup")
    heard = next(e for e in events if e["type"] == "heard")
    assert heard["profile_id"] == "word" and heard["command_id"] == "bold" and heard["executed"]
