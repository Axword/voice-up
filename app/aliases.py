"""Local voice adaptation: phrases the recognizer mishears, taught by user corrections.

Stored per profile as {heard phrase: command id}; nothing leaves the computer.
"""

from __future__ import annotations

import json
import threading

from app import paths
from app.pipeline import Intent, KeyAction, RouteContext
from app.profiles import normalize_phrase

MAX_ALIASES_PER_PROFILE = 500
_lock = threading.RLock()


def _file():
    return paths.CONFIG_DIR / "aliases.json"


def load() -> dict[str, dict[str, str]]:
    with _lock:
        target = _file()
        if not target.is_file():
            return {}
        try:
            data = json.loads(target.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}


def teach(profile_id: str, heard: str, command_id: str, existing_phrases: frozenset[str] = frozenset()) -> None:
    phrase = normalize_phrase(heard)
    if not phrase:
        raise ValueError("Pusta fraza.")
    if phrase in existing_phrases:
        raise ValueError("Ta fraza jest już komendą w profilu.")
    with _lock:
        data = load()
        entries = data.setdefault(profile_id, {})
        if phrase not in entries and len(entries) >= MAX_ALIASES_PER_PROFILE:
            raise ValueError("Za dużo zapamiętanych poprawek w tym profilu.")
        entries[phrase] = command_id
        paths.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        temporary = _file().with_suffix(".json.tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(_file())


class AliasRouter:
    """Maps a previously corrected mishearing to its command, before any other matching."""

    name = "alias"

    def route(self, text: str, context: RouteContext) -> Intent | None:
        command_id = load().get(context.profile.id, {}).get(normalize_phrase(text))
        if command_id is None:
            return None
        command = next((c for c in context.profile.commands if c.id == command_id and c.enabled), None)
        if command is None:
            return None
        action = KeyAction(command.id, tuple(command.keys), command.mode, command.duration_ms)
        return Intent(action, self.name, 1.0, command, label=text)
