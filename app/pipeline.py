"""Typed contract of the voice pipeline: transcript -> intent -> action -> result.

Modules (routers and executors) depend only on these types, never on each other,
so any of them can be replaced without touching the rest of the application.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from app.profiles import Profile, VoiceCommand


@dataclass(frozen=True)
class KeyAction:
    """Press keys/buttons together (click, timed hold or toggle)."""

    command_id: str
    keys: tuple[str, ...]
    mode: Literal["click", "timed", "toggle"] = "click"
    duration_ms: int = 3000


@dataclass(frozen=True)
class TypeTextAction:
    """Type literal text into the focused window."""

    text: str


@dataclass(frozen=True)
class MouseAction:
    """Move or click the pointer. dx/dy are pixels, `amount` is scroll notches."""

    kind: Literal["move", "click", "double_click", "right_click", "scroll"]
    dx: int = 0
    dy: int = 0
    amount: int = 0


@dataclass(frozen=True)
class StateAction:
    """A mode switch handled inside the pipeline (nothing is sent to the system)."""

    state: str


Action = KeyAction | TypeTextAction | MouseAction | StateAction


@dataclass(frozen=True)
class Intent:
    """What a router understood, with the router's own confidence in 0..1."""

    action: Action
    source: str
    confidence: float = 1.0
    command: VoiceCommand | None = None
    label: str = ""


@dataclass(frozen=True)
class RouteContext:
    profile: Profile
    threshold: float = 1.0


class Router(Protocol):
    name: str

    def route(self, text: str, context: RouteContext) -> Intent | None: ...


class Executor(Protocol):
    def execute(self, action: Action) -> bool: ...

    def release_all(self) -> None: ...


@dataclass
class Pipeline:
    """Routers are tried in order; the first intent wins. Executors are chosen by action type."""

    routers: list[Router] = field(default_factory=list)
    executors: dict[type, Executor] = field(default_factory=dict)

    def route(self, text: str, context: RouteContext) -> Intent | None:
        for router in self.routers:
            intent = router.route(text, context)
            if intent is not None:
                return intent
        return None

    def execute(self, intent: Intent) -> bool:
        executor = self.executors.get(type(intent.action))
        return bool(executor and executor.execute(intent.action))

    def release_all(self) -> None:
        for executor in dict.fromkeys(self.executors.values()):
            executor.release_all()


def _alnum(value: str) -> int:
    return sum(char.isalnum() for char in value)


class ProfileRouter:
    """Exact phrase match, then optional similarity match, over the active profile."""

    name = "profile"

    def route(self, text: str, context: RouteContext) -> Intent | None:
        from app.profiles import normalize_phrase

        normalized = normalize_phrase(text)
        candidates = [
            (command, normalize_phrase(command.phrase))
            for command in context.profile.commands if command.enabled
        ]
        for command, phrase in candidates:
            if phrase == normalized:
                return self._intent(command, 1.0)

        if context.threshold >= 1.0 or _alnum(normalized) <= 2:
            return None

        best: VoiceCommand | None = None
        best_score = 0.0
        tied = False
        for command, phrase in candidates:
            # Letter commands remain exact, even at a permissive threshold.
            if _alnum(phrase) <= 2:
                continue
            score = SequenceMatcher(None, phrase, normalized, autojunk=False).ratio()
            if score < context.threshold or score == 0:
                continue
            if score > best_score:
                best, best_score, tied = command, score, False
            elif score == best_score:
                tied = True
        # Equally good guesses must not depend on the order of commands.
        return None if tied or best is None else self._intent(best, best_score)

    def _intent(self, command: VoiceCommand, confidence: float) -> Intent:
        action = KeyAction(command.id, tuple(command.keys), command.mode, command.duration_ms)
        return Intent(action, self.name, confidence, command, label=command.phrase)


class StateExecutor:
    def execute(self, action: Action) -> bool:
        return True

    def release_all(self) -> None:
        pass


class KeyExecutor:
    """Adapts KeyController; the controller is resolved lazily so no input library loads early."""

    def __init__(self, controller: Callable[[], object]) -> None:
        self._controller = controller

    def execute(self, action: Action) -> bool:
        assert isinstance(action, KeyAction)
        return bool(self._controller().execute(
            action.command_id, list(action.keys), action.mode, action.duration_ms,
        ))

    def release_all(self) -> None:
        self._controller().release_all()
