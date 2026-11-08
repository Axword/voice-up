"""Offline speech synthesis (Windows SAPI) and engine helpers for the accent tests.

Nothing here talks to the network: text is spoken by voices installed in Windows and fed to the
same local Whisper engines the application uses.
"""

from __future__ import annotations

import os
import sys
import tempfile
import wave
from difflib import SequenceMatcher
from pathlib import Path

import pytest

SAMPLE_RATE = 16000
LEAD_SILENCE_S = 0.3   # Whisper loses very short clips; the old fixtures padded the same way
TAIL_SILENCE_S = 0.4
SAFT_16KHZ_16BIT_MONO = 22
SSFM_CREATE_FOR_WRITE = 3

# Directory of the models downloaded by the real application (tests isolate every other path).
REAL_DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "LoLVoice"


def _voices():
    import pythoncom  # noqa: F401  (initialises COM for this thread)
    import win32com.client

    pythoncom.CoInitialize()
    speaker = win32com.client.Dispatch("SAPI.SpVoice")
    return speaker, list(speaker.GetVoices())


def installed_voices() -> list[str]:
    if sys.platform != "win32":
        return []
    try:
        return [voice.GetDescription() for voice in _voices()[1]]
    except Exception:
        return []


def find_voice(fragment: str) -> str | None:
    return next((name for name in installed_voices() if fragment.lower() in name.lower()), None)


def synthesize(text: str, voice_fragment: str, rate: int = 0) -> bytes:
    """16 kHz mono int16 PCM of `text` spoken by the first installed voice matching `voice_fragment`."""
    import win32com.client

    speaker, voices = _voices()
    voice = next((v for v in voices if voice_fragment.lower() in v.GetDescription().lower()), None)
    if voice is None:
        raise LookupError(f"Voice not installed: {voice_fragment}")
    speaker.Voice = voice
    speaker.Rate = rate
    target = Path(tempfile.mkdtemp(prefix="tts-")) / "speech.wav"
    stream = win32com.client.Dispatch("SAPI.SpFileStream")
    stream.Format.Type = SAFT_16KHZ_16BIT_MONO
    stream.Open(str(target), SSFM_CREATE_FOR_WRITE)
    speaker.AudioOutputStream = stream
    speaker.Speak(text)
    stream.Close()
    with wave.open(str(target), "rb") as wav:
        pcm = wav.readframes(wav.getnframes())
    target.unlink(missing_ok=True)
    lead = b"\x00\x00" * int(SAMPLE_RATE * LEAD_SILENCE_S)
    tail = b"\x00\x00" * int(SAMPLE_RATE * TAIL_SILENCE_S)
    return lead + pcm + tail


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def require_voice(fragment: str) -> str:
    name = find_voice(fragment)
    if name is None:
        pytest.skip(f"Windows voice not installed: {fragment}")
    return name


def engine_ready(engine_id: str) -> bool:
    """True when the engine's model files exist in the real application data directory."""
    from app import engines, paths

    saved = paths.MODELS_DIR
    paths.MODELS_DIR = REAL_DATA_DIR / "models"
    try:
        engine = engines.get(engine_id)
        return bool(engine and engine.is_installed())
    finally:
        paths.MODELS_DIR = saved
