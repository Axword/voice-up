"""Input ownership, simultaneous presses and nonblocking hold lifetimes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar

import pytest

from controls.key_controller import KeyController, normalize_key


class FakeTimer:
    instances: ClassVar[list] = []

    def __init__(self, seconds, callback):
        self.seconds = seconds
        self.callback = callback
        self.cancelled = False
        self.started = False
        self.daemon = False
        self.instances.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True


@pytest.fixture
def inputs(monkeypatch):
    events = []
    controller = KeyController()
    controller._available = True
    monkeypatch.setattr(controller, "_down", lambda key: events.append(("down", key)))
    monkeypatch.setattr(controller, "_up", lambda key: events.append(("up", key)))
    FakeTimer.instances = []
    monkeypatch.setattr("controls.key_controller.threading.Timer", FakeTimer)
    return controller, events


def test_combination_is_simultaneous_and_released_in_reverse(inputs):
    controller, events = inputs
    assert controller.execute("cast", ["ctrl", "q"])
    assert events == [("down", "ctrl"), ("down", "q"), ("up", "q"), ("up", "ctrl")]
    assert controller.held_keys == []


def test_timed_hold_returns_before_timer_and_releases_on_expiry(inputs):
    controller, events = inputs
    assert controller.execute("sprint", ["shift", "w"], "timed", 3000)
    timer = FakeTimer.instances[0]
    assert timer.seconds == 3
    assert timer.started and timer.daemon
    assert events == [("down", "shift"), ("down", "w")]
    assert controller.held_command_ids == ["sprint"]
    timer.callback()
    assert events[-2:] == [("up", "w"), ("up", "shift")]
    assert controller.held_keys == []


def test_second_toggle_releases_the_same_combination(inputs):
    controller, events = inputs
    controller.execute("walk", ["w", "space"], "toggle")
    assert controller.held_keys == ["space", "w"]
    controller.execute("walk", ["w", "space"], "toggle")
    assert events == [("down", "w"), ("down", "space"), ("up", "space"), ("up", "w")]
    assert controller.held_command_ids == []


def test_overlapping_holds_do_not_release_shared_key(inputs):
    controller, events = inputs
    controller.execute("walk", ["w"], "toggle")
    controller.execute("sprint", ["ctrl", "w"], "timed")
    FakeTimer.instances[0].callback()
    assert events == [("down", "w"), ("down", "ctrl"), ("up", "ctrl")]
    assert controller.held_keys == ["w"]
    controller.execute("walk", ["w"], "toggle")
    assert events[-1] == ("up", "w")


def test_click_does_not_release_another_commands_modifier(inputs):
    controller, events = inputs
    controller.execute("modifier", ["ctrl"], "toggle")
    controller.execute("cast", ["ctrl", "q"], "click")
    assert events == [("down", "ctrl"), ("down", "q"), ("up", "q")]
    assert controller.held_keys == ["ctrl"]


def test_retriggered_timed_hold_ignores_previous_timer(inputs):
    controller, _events = inputs
    controller.execute("walk", ["w"], "timed")
    previous = FakeTimer.instances[0]
    controller.execute("walk", ["w"], "timed")
    previous.callback()
    assert previous.cancelled
    assert controller.held_keys == ["w"]
    FakeTimer.instances[1].callback()
    assert controller.held_keys == []


def test_release_all_cancels_timers_and_releases_every_key_once(inputs):
    controller, events = inputs
    controller.execute("walk", ["w"], "toggle")
    controller.execute("sprint", ["ctrl", "w"], "timed")
    controller.release_all()
    assert events.count(("up", "w")) == 1
    assert events.count(("up", "ctrl")) == 1
    assert FakeTimer.instances[0].cancelled
    assert controller.held_keys == []
    FakeTimer.instances[0].callback()
    assert events.count(("up", "w")) == 1


def test_partial_press_failure_releases_attempted_key_and_other_holds(inputs, monkeypatch):
    controller, events = inputs
    controller.execute("walk", ["w"], "toggle")

    def failing_down(key):
        events.append(("down", key))
        if key == "q":
            raise OSError("Input disconnected")

    monkeypatch.setattr(controller, "_down", failing_down)
    assert not controller.execute("cast", ["ctrl", "q"])
    assert ("up", "ctrl") in events
    assert ("up", "q") in events
    assert ("up", "w") in events
    assert controller.held_keys == []


def test_failed_release_is_retained_for_emergency_retry(inputs, monkeypatch):
    controller, events = inputs
    controller.execute("walk", ["w"], "toggle")
    monkeypatch.setattr(controller, "_up", lambda key: (_ for _ in ()).throw(OSError("Disconnected")))
    controller.release_all()
    assert controller.held_keys == ["w"]
    monkeypatch.setattr(controller, "_up", lambda key: events.append(("up", key)))
    controller.release_all()
    assert controller.held_keys == []


def test_unavailable_system_input_reports_failure_without_success():
    controller = KeyController()
    controller._available = False
    assert not controller.execute("cast", ["q"])
    assert not controller.held_keys


def test_keyboard_special_keys_and_mouse_buttons_resolve_correctly():
    events = []
    controller = KeyController()
    controller._available = True
    controller.keyboard = SimpleNamespace(
        press=lambda key: events.append(("keyboard-down", key)),
        release=lambda key: events.append(("keyboard-up", key)),
    )
    controller.mouse = SimpleNamespace(
        press=lambda key: events.append(("mouse-down", key)),
        release=lambda key: events.append(("mouse-up", key)),
    )
    controller._keyboard_module = SimpleNamespace(Key=SimpleNamespace(ctrl="CTRL"))
    controller._mouse_module = SimpleNamespace(Button=SimpleNamespace(left="LEFT"))
    assert controller.execute("click", ["Control", "left_click"])
    assert events == [("keyboard-down", "CTRL"), ("mouse-down", "LEFT"),
                      ("mouse-up", "LEFT"), ("keyboard-up", "CTRL")]


@pytest.mark.parametrize("value, expected", [("Control", "ctrl"), ("F12", "f12"), ("ArrowUp", "up"), (" ", "space")])
def test_key_aliases(value, expected):
    assert normalize_key(value) == expected


def test_left_modifier_alias_shares_hold_ownership(inputs):
    controller, events = inputs
    controller.execute("modifier", ["ctrl"], "toggle")
    controller.execute("cast", ["ctrl_l", "q"], "click")
    assert events == [("down", "ctrl"), ("down", "q"), ("up", "q")]
    assert controller.held_keys == ["ctrl"]


@pytest.mark.parametrize("value", ["", "a+b", "f25", "unknown", "click twice"])
def test_unsupported_keys_are_rejected(value):
    with pytest.raises(ValueError):
        normalize_key(value)
