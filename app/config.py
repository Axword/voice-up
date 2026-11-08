"""Application settings: schema, defaults, persistence, legacy migration."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

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
    auto_profile: bool = True
    disabled_modules: Annotated[list[Annotated[str, Field(max_length=64)]], Field(max_length=50)] = []

    model_config = {"extra": "ignore"}


_lock = threading.RLock()
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


def _lenient(raw: dict[str, Any]) -> Settings:
    """Settings from a file that may hold values this version does not accept (an old language
    code, a hand-edited theme): drop just those keys and keep the rest, rather than failing startup."""
    for _ in range(len(raw) + 1):
        try:
            return Settings(**raw)
        except ValidationError as exc:
            bad = {str(error["loc"][0]) for error in exc.errors() if error["loc"]}
            if not bad & raw.keys():
                break
            logging.getLogger("lolvoice.config").warning("Ignoring invalid settings: %s", ", ".join(sorted(bad)))
            raw = {key: value for key, value in raw.items() if key not in bad}
    return Settings()


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
        _cached = _lenient(raw)
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
    with _lock:  # read-modify-write: concurrent PUTs must not lose each other's changes
        current = load()
        nullable = ("audio_device", "skipped_version")
        changes = {k: v for k, v in patch.items() if v is not None or k in nullable}
        return save(Settings(**{**current.model_dump(), **changes}))


def reset_cache() -> None:
    global _cached
    with _lock:
        _cached = None
