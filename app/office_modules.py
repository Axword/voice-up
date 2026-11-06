"""Hands-free office modules: dictation and pointer control, as pipeline routers/executors."""

from __future__ import annotations

import re
from collections.abc import Callable

from app.pipeline import Intent, MouseAction, RouteContext, StateAction, TypeTextAction
from app.profiles import normalize_phrase

START = {
    "dyktuj", "tryb dyktowania", "dictate", "start dictation", "diktieren", "dictar",
    "dicter", "диктувати",
}
STOP = {
    "koniec dyktowania", "stop dyktowania", "stop dictation", "end dictation", "diktat beenden",
    "terminar dictado", "fin de la dictee", "кінець диктування",
}


class DictationRouter:
    """After a start phrase every utterance is typed, until a stop phrase."""

    name = "dictation"

    def __init__(self) -> None:
        self.active = False

    def route(self, text: str, context: RouteContext) -> Intent | None:
        phrase = normalize_phrase(text)
        if not self.active:
            if phrase in START:
                self.active = True
                return Intent(StateAction("dictation_on"), self.name, label="dictation on")
            return None
        if phrase in STOP:
            self.active = False
            return Intent(StateAction("dictation_off"), self.name, label="dictation off")
        typed = text.strip()
        return Intent(TypeTextAction(typed[:1].upper() + typed[1:] + " "), self.name, label="dictation")


STEP = 100
_NUMBER = r"(?:\s+(\d{1,4}))?$"
_MOVES: list[tuple[str, tuple[int, int]]] = [
    (r"(?:mysz|kursor|mouse|cursor)\s+(?:w\s+)?(?:lewo|left)", (-1, 0)),
    (r"(?:mysz|kursor|mouse|cursor)\s+(?:w\s+)?(?:prawo|right)", (1, 0)),
    (r"(?:mysz|kursor|mouse|cursor)\s+(?:w\s+)?(?:gore|up)", (0, -1)),
    (r"(?:mysz|kursor|mouse|cursor)\s+(?:w\s+)?(?:dol|down)", (0, 1)),
]
_CLICKS = {
    "kliknij": "click", "klik": "click", "click": "click",
    "podwojny klik": "double_click", "double click": "double_click",
    "prawy klik": "right_click", "right click": "right_click",
}
_SCROLLS = {
    "przewin w dol": -5, "scroll down": -5, "przewin w gore": 5, "scroll up": 5,
}


class MouseRouter:
    """Spoken pointer control: direction + optional pixels, clicks and scrolling."""

    name = "mouse"

    def route(self, text: str, context: RouteContext) -> Intent | None:
        phrase = normalize_phrase(text)
        for pattern, (sx, sy) in _MOVES:
            match = re.fullmatch(pattern + _NUMBER, phrase)
            if match:
                pixels = max(1, min(2000, int(match.group(1) or STEP)))
                return Intent(MouseAction("move", sx * pixels, sy * pixels), self.name, label=phrase)
        if phrase in _CLICKS:
            return Intent(MouseAction(_CLICKS[phrase]), self.name, label=phrase)
        if phrase in _SCROLLS:
            return Intent(MouseAction("scroll", amount=_SCROLLS[phrase]), self.name, label=phrase)
        return None


class TypeExecutor:
    def __init__(self, controller: Callable[[], object]) -> None:
        self._controller = controller

    def execute(self, action) -> bool:
        return bool(self._controller().type_text(action.text))

    def release_all(self) -> None:
        pass


class MouseExecutor:
    def __init__(self, controller: Callable[[], object]) -> None:
        self._controller = controller

    def execute(self, action) -> bool:
        return bool(self._controller().pointer(action.kind, action.dx, action.dy, action.amount))

    def release_all(self) -> None:
        pass
