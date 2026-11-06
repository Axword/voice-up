"""Similarity matching, exact letter commands and validated threshold settings."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app import config, profiles
from controller.service import VoiceService


def make_service(phrases: list[str], threshold: float = 1.0) -> VoiceService:
    service = VoiceService()
    service._settings = config.Settings(matching_threshold=threshold)
    service._profiles = profiles.ProfilesDocument(
        active_profile_id="matching-test",
        profiles=[profiles.Profile(
            id="matching-test", name="Matching test", language="pl_PL",
            commands=[profiles.VoiceCommand(id=f"command-{index}", phrase=phrase, keys=["r"])
                      for index, phrase in enumerate(phrases)],
        )],
    )
    return service


def test_default_threshold_preserves_exact_matching():
    service = make_service(["reload"])
    assert service.settings.matching_threshold == 1.0
    assert service.test_command("reload")["matched"]
    assert not service.test_command("relaod")["matched"]
    assert not service.test_command("please reload now")["matched"]
    assert service._key_controller is None


def test_exact_match_wins_before_fuzzy_candidates():
    service = make_service(["reload weapon", "reload"], threshold=0.0)
    assert service.test_command("reload")["command"]["phrase"] == "reload"


@pytest.mark.parametrize("text", [" BŁYSK! ", "blysk", "Błysk."])
def test_exact_normalization_ignores_accents_case_and_punctuation(text):
    assert make_service(["błysk"]).test_command(text)["matched"]


def test_fuzzy_matching_uses_the_same_accent_normalization():
    service = make_service(["przeładuj"], threshold=0.85)
    assert service.test_command("PRZEŁADÓJ!")["matched"]


@pytest.mark.parametrize("threshold,matched", [(0.8, True), (0.84, False), (1.0, False)])
def test_threshold_applies_to_the_similarity_score(threshold, matched):
    service = make_service(["reload"], threshold=threshold)
    assert service.test_command("relaod")["matched"] is matched


def test_a_score_equal_to_the_threshold_is_accepted():
    assert make_service(["mapa"], threshold=0.75).test_command("mapo")["matched"]


@pytest.mark.parametrize("order", [["reloading", "reload"], ["reload", "reloading"]])
def test_highest_score_wins_independently_of_command_order(order):
    result = make_service(order, threshold=0.6).test_command("relaod")
    assert result["command"]["phrase"] == "reload"


@pytest.mark.parametrize("order", [["mapa", "mapy"], ["mapy", "mapa"]])
def test_equal_best_scores_are_rejected_instead_of_guessing(order):
    assert not make_service(order, threshold=0.7).test_command("mapo")["matched"]


def test_a_better_candidate_resolves_a_previous_lower_score_tie():
    service = make_service(["mapa", "mapy", "mapka"], threshold=0.6)
    assert service.test_command("mapko")["command"]["phrase"] == "mapka"


@pytest.mark.parametrize("text", ["reload", "relaod"])
def test_disabled_commands_are_excluded_from_exact_and_fuzzy_matching(text):
    service = make_service(["reload"], threshold=0.0)
    service.document.active_profile.commands[0].enabled = False
    assert not service.test_command(text)["matched"]


def test_disabled_best_candidate_does_not_hide_an_enabled_candidate():
    service = make_service(["reload", "reloading"], threshold=0.6)
    service.document.active_profile.commands[0].enabled = False
    assert service.test_command("relaod")["command"]["phrase"] == "reloading"


@pytest.mark.parametrize("text,phrase", [
    ("war", "w"), ("wee", "we"), ("word", "wu"), ("e", "reload"),
    ("go", "go now"), ("a b", "abc"), ("w", "q"),
])
def test_short_inputs_and_letter_commands_never_use_fuzzy_matching(text, phrase):
    assert not make_service([phrase], threshold=0.0).test_command(text)["matched"]


@pytest.mark.parametrize("phrase", ["q", "w", "e", "wu", "go"])
def test_short_commands_still_match_exactly(phrase):
    assert make_service([phrase], threshold=0.0).test_command(phrase)["matched"]


@pytest.mark.parametrize("text", ["", "!!!", "   "])
def test_empty_normalized_text_never_matches(text):
    assert not make_service(["reload"], threshold=0.0).test_command(text)["matched"]


def test_zero_similarity_does_not_match_at_zero_threshold():
    assert not make_service(["abc"], threshold=0.0).test_command("xyz")["matched"]


def test_only_the_active_profile_participates_in_fuzzy_matching():
    service = make_service(["inventory"], threshold=0.8)
    service.document.profiles.append(profiles.Profile(
        id="inactive", name="Inactive", commands=[
            profiles.VoiceCommand(id="reload", phrase="reload", keys=["r"]),
        ],
    ))
    assert not service.test_command("relaod")["matched"]


def test_live_transcripts_and_dry_runs_use_the_same_matching_rule():
    service = make_service(["reload"], threshold=0.8)
    events = []
    execute = Mock(return_value=True)
    service._key_controller = SimpleNamespace(execute=execute, held_command_ids=[], release_all=Mock())
    service._emit_status = Mock()
    service.set_event_sink(events.append)
    assert service.test_command("relaod")["matched"]
    execute.assert_not_called()
    assert service.handle_transcript("relaod") == ["r"]
    execute.assert_called_once_with("command-0", ["r"], "click", 3000)
    assert events[0]["command_id"] == "command-0"
    assert events[0]["executed"] is True


def test_changing_threshold_updates_matching_without_restarting_audio():
    service = make_service(["reload"])
    service._listening = True
    service.start = Mock()
    service.stop = Mock()
    service._emit_status = Mock()
    service.apply_settings(service.settings.model_copy(update={"matching_threshold": 0.8}))
    service.start.assert_not_called()
    service.stop.assert_not_called()
    assert service.test_command("relaod")["matched"]


@pytest.mark.parametrize("value", [-0.01, 1.01, True, False, "0.8", None, float("nan"), float("inf")])
def test_settings_reject_invalid_threshold_values(value):
    with pytest.raises(ValidationError):
        config.Settings(matching_threshold=value)


@pytest.mark.parametrize("value", [0, 0.8, 1])
def test_api_accepts_and_persists_a_threshold_in_the_closed_range(api_client, value):
    response = api_client.put("/api/v1/settings", json={"matching_threshold": value})
    assert response.status_code == 200
    assert response.json()["matching_threshold"] == value
    assert api_client.get("/api/v1/settings").json()["matching_threshold"] == value
    config.reset_cache()
    assert config.load().matching_threshold == value


@pytest.mark.parametrize("value", [-0.01, 1.01, True, False, "0.8", "NaN", None])
def test_api_rejects_invalid_threshold_without_changing_settings(api_client, value):
    before = api_client.get("/api/v1/settings").json()
    response = api_client.put("/api/v1/settings", json={"matching_threshold": value})
    assert response.status_code == 422
    assert api_client.get("/api/v1/settings").json() == before


def test_an_unrelated_settings_patch_does_not_reset_the_threshold(api_client):
    assert api_client.put("/api/v1/settings", json={"matching_threshold": 0.8}).status_code == 200
    response = api_client.put("/api/v1/settings", json={"theme": "dark"})
    assert response.status_code == 200
    assert response.json()["matching_threshold"] == 0.8
    assert response.json()["theme"] == "dark"
