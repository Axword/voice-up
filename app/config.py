"""Application settings: schema, defaults, persistence, legacy migration."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field

from app import paths

Language = Literal["pl_PL", "en_US", "de_DE", "es_ES", "fr_FR", "uk_UA"]
MatchingThreshold = Annotated[float, Field(ge=0, le=1, strict=True, allow_inf_nan=False)]


class Settings(BaseModel):
    language: Language = "pl_PL"
    ui_language: Language = "pl_PL"
    engine_id: str = "whisper-tiny"
    matching_threshold: MatchingThreshold = 1.0
    audio_device: Optional[str] = None
    start_with_windows: bool = False
    start_listening_on_launch: bool = False
    theme: Literal["dark", "light", "system"] = "light"
    skipped_version: Optional[str] = None
    check_updates: bool = True
    auto_profile: bool = False

    model_config = {"extra": "ignore"}


_lock = threading.Lock()
_cached: Optional[Settings] = None

LEGACY_FILES = (Path("config/config.json"), Path("config.json"))


def _migrate_legacy(target: Path) -> dict[str, Any]:
    for legacy in LEGACY_FILES:
        try:
            if legacy.is_file():
                data = json.loads(legacy.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data:
                    return data
        except (OSError, json.JSONDecodeError):
            continue
    return {}


def load(force: bool = False) -> Settings:
    global _cached
    with _lock:
        if _cached is not None and not force:
            return _cached
        raw: dict[str, Any] = {}
        if paths.CONFIG_FILE.is_file():
            try:
                raw = json.loads(paths.CONFIG_FILE.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raw = {}
        else:
            raw = _migrate_legacy(paths.CONFIG_FILE)
        if not isinstance(raw, dict):
            raw = {}
        _cached = Settings(**raw) if raw else Settings()
        if not paths.CONFIG_FILE.is_file():
            _write(_cached)
        return _cached


def _write(settings: Settings) -> None:
    paths.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = paths.CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(settings.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(paths.CONFIG_FILE)


def save(settings: Settings) -> Settings:
    global _cached
    with _lock:
        _write(settings)
        _cached = settings
        return settings


def update(patch: dict[str, Any]) -> Settings:
    current = load()
    nullable = ("audio_device", "skipped_version")
    changes = {k: v for k, v in patch.items() if v is not None or k in nullable}
    return save(Settings(**{**current.model_dump(), **changes}))


def reset_cache() -> None:
    global _cached
    with _lock:
        _cached = None
