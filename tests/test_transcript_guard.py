"""Looping Whisper output (seen on silence and on audio the voice could not read) is dropped."""

from __future__ import annotations

import pytest

from controller.transcriber import is_hallucination

LOOP_PL = "wydaje się że to jest to " * 30
LOOP_UK = "він " + "відео " * 60


@pytest.mark.parametrize("text,seconds", [(LOOP_PL, 2.0), (LOOP_UK, 2.0), ("tak tak tak tak tak tak tak", 1.0)])
def test_loops_are_dropped(text, seconds):
    assert is_hallucination(text.strip(), seconds)


@pytest.mark.parametrize("text,seconds", [
    ("", 1.0),
    ("błysk", 0.8),
    ("odpowiedz wszystkim", 1.5),
    ("nowa wiadomość", 1.2),
    ("dzień dobry chciałbym zapisać ten dokument i wysłać go do klienta", 5.0),
    ("one two three four", 1.0),
])
def test_normal_commands_and_dictation_are_kept(text, seconds):
    assert not is_hallucination(text, seconds)


def test_long_dictation_with_repeated_words_is_kept():
    text = "to jest bardzo bardzo długi tekst który powiedziałem powoli i dokładnie dla sprawdzenia dyktowania"
    assert not is_hallucination(text, 8.0)
