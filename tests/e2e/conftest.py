"""Accent tests use the speech models already downloaded by the real application.

Every other test isolates the data directory; here the model directories are pointed back at the
real ones only while an engine is loading, so the application's own data is never written.
"""

from __future__ import annotations

import pytest

from tests import audio_support as audio


@pytest.fixture(scope="module")
def load_engine():
    from app import paths
    from controller.transcriber import Transcriber

    cache: dict[str, Transcriber] = {}

    def load(engine_id: str) -> Transcriber:
        if engine_id in cache:
            return cache[engine_id]
        if not audio.engine_ready(engine_id):
            pytest.skip(f"Speech model not downloaded: {engine_id}")
        patch = pytest.MonkeyPatch()
        try:
            patch.setattr(paths, "DATA_DIR", audio.REAL_DATA_DIR)
            patch.setattr(paths, "MODELS_DIR", audio.REAL_DATA_DIR / "models")
            patch.setattr(paths, "CACHE_DIR", audio.REAL_DATA_DIR / "cache")
            engine = Transcriber(engine_id=engine_id)
            engine.load()
        finally:
            patch.undo()
        cache[engine_id] = engine
        return engine

    return load
