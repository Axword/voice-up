"""Execution metadata stays attached to the event after profile edits."""

from types import SimpleNamespace

from app import profiles
from controller.service import VoiceService


def event_service(execute):
    service = VoiceService()
    events = []
    service.set_event_sink(events.append)
    service._key_controller = SimpleNamespace(execute=execute, held_keys=[], held_command_ids=[])
    return service, events


def heard_event(events):
    return next(event for event in reversed(events) if event["type"] == "heard")


def test_click_event_carries_profile_and_simultaneous_keys():
    service, events = event_service(lambda *args: True)
    service.handle_transcript("ulepsz umiejętność")
    event = heard_event(events)
    assert event["profile_id"] == "league-of-legends"
    assert event["profile_name"] == "League of Legends"
    assert event["mode"] == "click"
    assert event["matched"] == ["ctrl", "q"]
    assert event["executed"] is True
    assert event["held"] is False
    assert event["error"] is None
    assert isinstance(event["time"], float)


def test_timed_event_keeps_its_duration_after_profile_edit():
    service, events = event_service(lambda *args: True)
    document = profiles.default_document().model_dump()
    document["profiles"][0]["commands"][3]["duration_ms"] = 4700
    service._profiles = profiles.ProfilesDocument.model_validate(document)
    service.handle_transcript("wyniki")
    event = heard_event(events)
    document["profiles"][0]["commands"][3]["duration_ms"] = 3000
    service._profiles = profiles.ProfilesDocument.model_validate(document)
    assert event["mode"] == "timed"
    assert event["duration_ms"] == 4700


def test_toggle_event_distinguishes_press_and_release():
    service, events = event_service(None)
    keys = service._key_controller

    def toggle(command_id, *_args):
        keys.held_command_ids = [] if command_id in keys.held_command_ids else [command_id]
        return True

    keys.execute = toggle
    service.handle_transcript("atakuj")
    assert heard_event(events)["held"] is True
    service.handle_transcript("atakuj")
    assert heard_event(events)["held"] is False
    assert heard_event(events)["mode"] == "toggle"


def test_execution_error_is_present_only_for_matched_failed_action():
    service, events = event_service(lambda *args: False)
    service.handle_transcript("błysk")
    failed = heard_event(events)
    assert failed["executed"] is False
    assert failed["error"]
    service.handle_transcript("nieznana fraza")
    unmatched = heard_event(events)
    assert unmatched["matched"] is None
    assert unmatched["mode"] is None
    assert unmatched["error"] is None
