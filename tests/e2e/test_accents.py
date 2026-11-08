"""Speech recognition with synthesized voices, including foreign-accent cases.

Windows only offers Polish and US-English voices here, so accents are produced by proxy: a Polish
voice reading English (Polish-accented English), a US voice reading Polish/German/Spanish/French
(American-accented). Native pairs must recognise reliably; accent pairs only need to stay above a
low floor, and every number lands in tests/reports/accent_report.json so regressions are visible.

Run: python -m pytest tests/e2e -m audio -q   (needs downloaded models; no network is used)
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass

import pytest

from app import profiles
from app.pipeline import ProfileRouter, RouteContext
from app.profiles import normalize_phrase
from tests import audio_support as audio
from tests.conftest import ROOT

pytestmark = [pytest.mark.audio, pytest.mark.skipif(sys.platform != "win32", reason="Windows SAPI voices")]

ENGINES = ["faster-whisper-tiny", "faster-whisper-base", "whisper-tiny"]
REPORT = ROOT / "tests" / "reports" / "accent_report.json"
THRESHOLD = 0.8  # the similarity setting a user would enable to tolerate small misrecognitions
_report: dict[str, dict] = {}


@dataclass(frozen=True)
class Case:
    name: str
    voice: str
    language: str
    profile_id: str | None      # library profile whose commands are the expected targets
    count: int
    min_hit_rate: float         # fraction of commands that must reach the right command
    phrases: tuple[str, ...] = ()  # free phrases (no profile) scored by text similarity
    min_similarity: float = 0.0


CASES = [
    Case("polish voice, Polish", "Paulina", "pl_PL", "counter-strike-2", 8, 0.5),
    Case("US voice, English", "Zira", "en_US", "counter-strike-2-en", 8, 0.75),
    Case("Polish accent, English", "Paulina", "en_US", "counter-strike-2-en", 8, 0.5),
    Case("US accent, Polish", "Zira", "pl_PL", "counter-strike-2", 8, 0.0),
    Case("office Polish", "Paulina", "pl_PL", "office-outlook", 8, 0.5),
    Case("office English", "Zira", "en_US", "office-outlook-en", 8, 0.75),
    Case("US accent, Spanish", "Zira", "es_ES", None, 0, 0.0,
         ("guardar", "copiar", "pegar", "deshacer", "seleccionar todo", "nuevo mensaje"), 0.6),
    Case("US accent, French", "Zira", "fr_FR", None, 0, 0.0,
         ("enregistrer", "copier", "coller", "annuler", "tout sélectionner", "nouveau message"), 0.5),
    Case("US accent, German", "Zira", "de_DE", None, 0, 0.0,
         ("speichern", "kopieren", "einfügen", "rückgängig", "alles auswählen", "neue nachricht"), 0.35),
    Case("Polish accent, German", "Paulina", "de_DE", None, 0, 0.0,
         ("speichern", "kopieren", "einfügen", "rückgängig", "alles auswählen", "neue nachricht"), 0.4),
]


def targets(case: Case) -> list[tuple[str, str]]:
    """(phrase, command id) pairs: the first commands of the library profile, distinct phrases only."""
    profile = next(p for p in profiles.catalog_profiles() if p.id == case.profile_id)
    return [(c.phrase, c.id) for c in profile.commands if len(c.phrase) > 3][: case.count]


@pytest.fixture(scope="module", autouse=True)
def write_report():
    yield
    if _report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(_report, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.mark.parametrize("engine_id", ENGINES)
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_accent_recognition(case, engine_id, load_engine):
    audio.require_voice(case.voice)
    engine = load_engine(engine_id)
    rows = []
    if case.profile_id:
        profile = next(p for p in profiles.catalog_profiles() if p.id == case.profile_id)
        router = ProfileRouter()
        hits = 0
        for phrase, command_id in targets(case):
            heard = engine.transcribe_pcm(audio.synthesize(phrase, case.voice), case.language)
            intent = router.route(heard, RouteContext(profile, THRESHOLD))
            hit = bool(intent and intent.command and intent.command.id == command_id)
            hits += hit
            rows.append({"said": phrase, "heard": heard, "hit": hit})
        score = hits / len(rows)
        needed = case.min_hit_rate
    else:
        sims = []
        for phrase in case.phrases:
            heard = engine.transcribe_pcm(audio.synthesize(phrase, case.voice), case.language)
            similarity = audio.similarity(normalize_phrase(heard), normalize_phrase(phrase))
            sims.append(similarity)
            rows.append({"said": phrase, "heard": heard, "similarity": round(similarity, 2)})
        score = sum(sims) / len(sims)
        needed = case.min_similarity
    _report.setdefault(case.name, {})[engine_id] = {"score": round(score, 2), "required": needed, "rows": rows}
    assert score >= needed, f"{case.name} on {engine_id}: {score:.2f} < {needed} ({rows})"


@pytest.mark.parametrize("engine_id", ENGINES)
def test_unreadable_audio_never_produces_a_looping_transcript(engine_id, load_engine):
    """A Polish voice cannot read Cyrillic, so the audio is near-silent: Whisper used to loop on it."""
    audio.require_voice("Paulina")
    engine = load_engine(engine_id)
    for language, pcm in (("uk_UA", audio.synthesize("зберегти копіювати вставити", "Paulina")),
                          ("pl_PL", b"\x00\x00" * 32000), ("en_US", b"\x00\x00" * 32000)):
        heard = engine.transcribe_pcm(pcm, language)
        assert len(heard) < 60, f"{engine_id} {language}: {heard[:80]!r}"
