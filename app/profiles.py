"""Validated, portable voice profiles stored as an atomic JSON document."""

from __future__ import annotations

import json
import re
import threading
import unicodedata
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app import paths
from app.app_icons import valid_exe
from app.config import Language
from controls.key_controller import normalize_key

_lock = threading.RLock()
LIBRARY_FILES = (
    "profile-library-core.json",
    "profile-library-games.json",
    "profile-library-sim.json",
    "profile-library-baseline.json",
    "profile-library-office.json",
)
MAX_PROFILES = 100


def normalize_phrase(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower().replace("ł", "l"))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w\s]", " ", value).split())


class VoiceCommand(BaseModel):
    id: Annotated[str, Field(min_length=1, max_length=100)]
    phrase: Annotated[str, Field(min_length=1, max_length=160)]
    keys: Annotated[list[str], Field(min_length=1, max_length=4)]
    mode: Literal["click", "timed", "toggle"] = "click"
    duration_ms: Annotated[int, Field(ge=100, le=60000, strict=True)] = 3000
    enabled: bool = True

    model_config = {"extra": "forbid", "str_strip_whitespace": True}

    @field_validator("phrase")
    @classmethod
    def meaningful_phrase(cls, value: str) -> str:
        if not normalize_phrase(value):
            raise ValueError("Fraza musi zawierać słowo lub liczbę.")
        return value

    @field_validator("keys")
    @classmethod
    def valid_keys(cls, values: list[str]) -> list[str]:
        keys = [normalize_key(value) for value in values]
        if len(set(keys)) != len(keys):
            raise ValueError("Przyciski w jednej komendzie nie mogą się powtarzać.")
        return keys


class Profile(BaseModel):
    id: Annotated[str, Field(min_length=1, max_length=100)]
    name: Annotated[str, Field(min_length=1, max_length=80)]
    game: Annotated[str, Field(max_length=100)] = ""
    language: Language = "pl_PL"
    apps: Annotated[list[Annotated[str, Field(min_length=1, max_length=100)]], Field(max_length=20)] = Field(
        default_factory=list
    )
    commands: Annotated[list[VoiceCommand], Field(max_length=500)] = Field(default_factory=list)

    model_config = {"extra": "forbid", "str_strip_whitespace": True}

    @field_validator("apps")
    @classmethod
    def program_names(cls, values: list[str]) -> list[str]:
        # Older files may hold names like "notepad"; ignore what cannot be an executable name
        # instead of making the whole profile document unreadable.
        return [value for value in values if valid_exe(value)]

    @model_validator(mode="after")
    def unique_commands(self) -> Profile:
        ids = [command.id for command in self.commands]
        phrases = [normalize_phrase(command.phrase) for command in self.commands]
        if len(set(ids)) != len(ids):
            raise ValueError("Identyfikatory komend muszą być unikalne w profilu.")
        if len(set(phrases)) != len(phrases):
            raise ValueError("Frazy w jednym profilu nie mogą się powtarzać.")
        return self


class ProfilesDocument(BaseModel):
    version: Literal[1] = 1
    active_profile_id: Annotated[str, Field(min_length=1, max_length=100)]
    profiles: Annotated[list[Profile], Field(min_length=1, max_length=100)]

    model_config = {"extra": "forbid", "str_strip_whitespace": True}

    @model_validator(mode="after")
    def valid_active_profile(self) -> ProfilesDocument:
        ids = [profile.id for profile in self.profiles]
        if len(set(ids)) != len(ids):
            raise ValueError("Identyfikatory profili muszą być unikalne.")
        if self.active_profile_id not in ids:
            raise ValueError("Aktywny profil nie istnieje.")
        return self

    @property
    def active_profile(self) -> Profile:
        return next(profile for profile in self.profiles if profile.id == self.active_profile_id)


class LibraryState(BaseModel):
    schema_version: Literal[1] = Field(default=1, alias="schema")
    seen_catalog_ids: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(default_factory=list)

    model_config = {"extra": "forbid", "populate_by_name": True}

    @field_validator("seen_catalog_ids")
    @classmethod
    def unique_ids(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("Identyfikatory zapisanej biblioteki nie mogą się powtarzać.")
        return values


def catalog_profiles() -> list[Profile]:
    """Read every shipped shard, preserving its declared profile order."""
    catalog: list[Profile] = []
    seen: set[str] = set()
    for filename in LIBRARY_FILES:
        target = paths.bundled_dir() / "data" / filename
        if not target.is_file():
            raise FileNotFoundError(f"Brak pliku biblioteki profili: {filename}")
        raw = json.loads(target.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, list):
            raise ValueError(f"Biblioteka {filename} musi zawierać listę profili.")
        for entry in raw:
            profile = Profile.model_validate(entry)
            if profile.id in seen:
                raise ValueError(f"Powtórzony identyfikator w bibliotece: {profile.id}")
            seen.add(profile.id)
            catalog.append(profile)
    if not catalog:
        raise ValueError("Biblioteka profili jest pusta.")
    return catalog


def default_document() -> ProfilesDocument:
    catalog = catalog_profiles()
    return ProfilesDocument(active_profile_id=catalog[0].id, profiles=catalog)


def _state_file() -> Path:
    return paths.CONFIG_DIR / "profile-library-state.json"


def _read_state() -> LibraryState:
    target = _state_file()
    if target.is_file():
        # An invalid ledger must not silently restore profiles the user removed.
        return LibraryState.model_validate_json(target.read_text(encoding="utf-8-sig"))
    return LibraryState()


def _write_state(state: LibraryState) -> None:
    target = _state_file()
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(state.model_dump(by_alias=True), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(target)


def _backup_before_library_update() -> None:
    target = paths.CONFIG_DIR / "profiles.json"
    backup = paths.CONFIG_DIR / "profiles.before-library.json"
    if target.is_file() and not backup.exists():
        temporary = backup.with_suffix(".json.tmp")
        temporary.write_bytes(target.read_bytes())
        temporary.replace(backup)


def synchronize_library(document: ProfilesDocument | dict) -> ProfilesDocument:
    """Append unseen built-ins without replacing any existing user profile.

    The returned document is persisted when migration is needed. A separate
    ledger remembers offered IDs, including profiles removed by the user and
    entries skipped because the document already has the maximum 100 profiles.
    """
    validated = ProfilesDocument.model_validate(document).model_copy(deep=True)
    with _lock:
        catalog = catalog_profiles()
        state = _read_state()
        seen = set(state.seen_catalog_ids)
        existing = {profile.id for profile in validated.profiles}
        updated = list(validated.profiles)
        for profile in catalog:
            if profile.id not in seen and profile.id not in existing and len(updated) < MAX_PROFILES:
                updated.append(profile.model_copy(deep=True))
                existing.add(profile.id)
        merged = ProfilesDocument(
            version=validated.version, active_profile_id=validated.active_profile_id, profiles=updated
        )
        next_ids = [*state.seen_catalog_ids, *(profile.id for profile in catalog if profile.id not in seen)]
        state_changed = not _state_file().is_file() or next_ids != state.seen_catalog_ids
        profiles_added = len(merged.profiles) != len(validated.profiles)
        if profiles_added:
            _backup_before_library_update()
        if profiles_added or state_changed or not (paths.CONFIG_DIR / "profiles.json").is_file():
            # Commit the ledger only after the profiles document is safely saved.
            save(merged)
        if state_changed:
            _write_state(LibraryState(seen_catalog_ids=next_ids))
        return merged


def load() -> ProfilesDocument:
    with _lock:
        target = paths.CONFIG_DIR / "profiles.json"
        if target.is_file():
            # Invalid user data is reported; it must never be silently replaced.
            document = ProfilesDocument.model_validate_json(target.read_text(encoding="utf-8-sig"))
        else:
            document = default_document()
        return synchronize_library(document)


def save(document: ProfilesDocument | dict) -> ProfilesDocument:
    validated = ProfilesDocument.model_validate(document)
    with _lock:
        paths.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        target = paths.CONFIG_DIR / "profiles.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(validated.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)
    return validated
