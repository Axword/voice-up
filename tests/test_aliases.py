"""Corrections taught by the user are remembered locally and win over normal matching."""

from __future__ import annotations

import pytest

from app import aliases
from tests.test_office_modules import make_service


def test_taught_mishearing_runs_the_command_after_restart():
    service = make_service()
    assert not service.test_command("zapis")["matched"]
    service.teach_alias("Zapis!", "save")
    # a fresh service reads the same local file
    fresh = make_service()
    result = fresh.test_command("zapis")
    assert result["matched"] and result["command"]["id"] == "save"
    fresh.handle_transcript("zapis")
    assert fresh._key_controller.calls == [("keys", ("save", ["ctrl", "s"], "click", 3000))]


def test_unknown_command_is_rejected_and_nothing_is_saved():
    service = make_service()
    with pytest.raises(KeyError):
        service.teach_alias("zapis", "missing")
    assert aliases.load() == {}


def test_alias_to_disabled_command_does_not_fire():
    service = make_service()
    service.teach_alias("zapis", "save")
    service.document.active_profile.commands[0].enabled = False
    assert not service.test_command("zapis")["matched"]


def test_alias_is_scoped_to_its_profile():
    service = make_service()
    aliases.teach("other-profile", "zapis", "save")
    assert not service.test_command("zapis")["matched"]
