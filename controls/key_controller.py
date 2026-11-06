"""Simultaneous input actions, with cancellable holds and shared-key ownership."""

from __future__ import annotations

import re
import threading
import uuid
from collections import Counter
from typing import Any

from app.logging_setup import get_logger

log = get_logger("keys")

SPECIAL_KEYS = frozenset({
    "alt", "alt_l", "alt_r", "alt_gr", "backspace", "caps_lock", "cmd", "cmd_l", "cmd_r",
    "ctrl", "ctrl_l", "ctrl_r", "delete", "down", "end", "enter", "esc", "home", "insert",
    "left", "menu", "num_lock", "page_down", "page_up", "pause", "print_screen", "right",
    "scroll_lock", "shift", "shift_l", "shift_r", "space", "tab", "up",
})
MOUSE_KEYS = frozenset({"left_click", "right_click", "middle_click"})
ALIASES = {
    "control": "ctrl", "escape": "esc", "return": "enter", "win": "cmd", "windows": "cmd",
    "ctrl_l": "ctrl", "alt_l": "alt", "shift_l": "shift", "cmd_l": "cmd",
    "arrowup": "up", "arrowdown": "down", "arrowleft": "left", "arrowright": "right",
    "pageup": "page_up", "pagedown": "page_down", "capslock": "caps_lock", " ": "space",
    "mouse1": "left_click", "mouse2": "right_click", "mouse3": "middle_click",
}


def normalize_key(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Przycisk musi być tekstem.")
    raw = value.lower() if value == " " else value.strip().lower()
    key = ALIASES.get(raw, raw)
    if key in SPECIAL_KEYS or key in MOUSE_KEYS or re.fullmatch(r"f(?:[1-9]|1\d|2[0-4])", key):
        return key
    if len(key) == 1 and key.isascii() and key.isprintable() and not key.isspace():
        return key
    raise ValueError(f"Nieobsługiwany przycisk: {value}")


class KeyController:
    def __init__(self, lazy: bool = True) -> None:
        self.mouse: Any | None = None
        self.keyboard: Any | None = None
        self._mouse_module: Any | None = None
        self._keyboard_module: Any | None = None
        self._available: bool | None = None
        self._lock = threading.RLock()
        self._owners: dict[str, tuple[str, ...]] = {}
        self._counts: Counter[str] = Counter()
        self._timers: dict[str, threading.Timer] = {}
        self._pending_release: set[str] = set()
        if not lazy:
            self._ensure()

    def _ensure(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            from pynput import keyboard, mouse

            self.mouse = mouse.Controller()
            self.keyboard = keyboard.Controller()
            self._mouse_module = mouse
            self._keyboard_module = keyboard
            self._available = True
        except Exception as exc:
            log.warning("Input control unavailable: %s", exc)
            self._available = False
        return self._available

    @property
    def available(self) -> bool:
        return self._ensure()

    @property
    def held_keys(self) -> list[str]:
        with self._lock:
            return sorted(set(self._counts) | self._pending_release)

    @property
    def held_command_ids(self) -> list[str]:
        with self._lock:
            return list(self._owners)

    def _input(self, key: str) -> tuple[Any, Any]:
        if key in MOUSE_KEYS:
            return self.mouse, getattr(self._mouse_module.Button, key.removesuffix("_click"))
        if key in SPECIAL_KEYS or len(key) > 1:
            return self.keyboard, getattr(self._keyboard_module.Key, key)
        return self.keyboard, key

    def _down(self, key: str) -> None:
        controller, button = self._input(key)
        controller.press(button)

    def _up(self, key: str) -> None:
        controller, button = self._input(key)
        controller.release(button)

    def _release_owner(self, owner: str) -> None:
        timer = self._timers.pop(owner, None)
        if timer:
            timer.cancel()
        keys = self._owners.pop(owner, ())
        for key in reversed(keys):
            self._counts[key] -= 1
            if self._counts[key] <= 0:
                del self._counts[key]
                try:
                    self._up(key)
                    self._pending_release.discard(key)
                except Exception as exc:
                    self._pending_release.add(key)
                    log.error("Could not release %s: %s", key, exc)

    def _expire(self, owner: str, timer: threading.Timer) -> None:
        with self._lock:
            if self._timers.get(owner) is timer:
                self._release_owner(owner)

    def execute(self, command_id: str, keys: list[str], mode: str = "click", duration_ms: int = 3000) -> bool:
        if mode not in {"click", "timed", "toggle"}:
            raise ValueError("Unknown input mode")
        normalized = tuple(dict.fromkeys(normalize_key(key) for key in keys))
        if not normalized:
            raise ValueError("An action must contain a key")
        with self._lock:
            if mode == "toggle" and command_id in self._owners:
                self._release_owner(command_id)
                return not self._pending_release
            if not self._ensure():
                return False
            owner = command_id if mode != "click" else f"click-{uuid.uuid4()}"
            if owner in self._owners:
                self._release_owner(owner)
            acquired: list[str] = []
            try:
                for key in normalized:
                    if not self._counts[key]:
                        # Also clean up a key if an OS call fails after pressing it.
                        self._pending_release.add(key)
                        self._down(key)
                        self._pending_release.discard(key)
                    self._counts[key] += 1
                    acquired.append(key)
                self._owners[owner] = tuple(acquired)
                if mode == "click":
                    self._release_owner(owner)
                elif mode == "timed":
                    timer = threading.Timer(max(0.1, min(60, duration_ms / 1000)), lambda: self._expire(owner, timer))
                    timer.daemon = True
                    self._timers[owner] = timer
                    timer.start()
                return not self._pending_release
            except Exception as exc:
                self._owners[owner] = tuple(acquired)
                log.error("Input action failed: %s", exc)
                self.release_all()
                return False

    def release_all(self) -> None:
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
            keys = list(dict.fromkeys(key for owned in self._owners.values() for key in owned))
            keys.extend(key for key in self._pending_release if key not in keys)
            self._owners.clear()
            self._counts.clear()
            self._pending_release.clear()
            for key in reversed(keys):
                try:
                    self._up(key)
                except Exception as exc:
                    self._pending_release.add(key)
                    log.error("Could not release %s: %s", key, exc)

    def press_key(self, key: str) -> bool:
        return self.execute("single", [key])

    def type_text(self, text: str) -> bool:
        """Type literal text into the focused window (dictation)."""
        with self._lock:
            if not text or not self._ensure():
                return False
            try:
                self.keyboard.type(text)
                return True
            except Exception as exc:
                log.error("Typing failed: %s", exc)
                return False

    def pointer(self, kind: str, dx: int = 0, dy: int = 0, amount: int = 0) -> bool:
        """Relative pointer move, click or scroll."""
        with self._lock:
            if not self._ensure():
                return False
            try:
                button = self._mouse_module.Button
                if kind == "move":
                    self.mouse.move(dx, dy)
                elif kind == "click":
                    self.mouse.click(button.left)
                elif kind == "double_click":
                    self.mouse.click(button.left, 2)
                elif kind == "right_click":
                    self.mouse.click(button.right)
                elif kind == "scroll":
                    self.mouse.scroll(0, amount)
                else:
                    raise ValueError(f"Unknown pointer action: {kind}")
                return True
            except Exception as exc:
                log.error("Pointer action failed: %s", exc)
                return False
