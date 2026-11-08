"""Live test rig: the whole application, end to end, aimed at a window of its own.

What runs for real: voice activity detection, the Whisper engine, the pipeline, profile switching by
the focused program, and Windows input injection (pynput). What is simulated: the microphone, which
is replaced by a synthesized voice (Windows SAPI) fed to the audio callback in real time.

Safety: every key press, typed character and mouse action first checks that the rig's own window is the
foreground window; otherwise nothing is sent (see Guarded). Settings, profiles and logs live in a
temporary directory; only the downloaded speech models are read from the real data directory.

    python tools/live_rig.py [--engine faster-whisper-base] [--voice Paulina]

Takes about a minute, steals focus for that time, and moves the pointer by 50 px. Exit code 0 = all passed.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import queue
import sys
import tempfile
import threading
import time
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["VOICE_CONTROL_HOME"] = tempfile.mkdtemp(prefix="voice-rig-")

from app import config, paths, profiles  # noqa: E402
from app.foreground import foreground_process  # noqa: E402
from controller import voice_controller  # noqa: E402
from controller.service import VoiceService  # noqa: E402
from controls.key_controller import KeyController  # noqa: E402
from tests import audio_support as audio  # noqa: E402

paths.MODELS_DIR = audio.REAL_DATA_DIR / "models"
user32 = ctypes.windll.user32
CHUNK = 640  # 20 ms of 16 kHz mono int16
REPORT = ROOT / "tests" / "reports" / "live_rig.json"


class Guarded(KeyController):
    """Real input, but only while the rig window has the focus; anything else is refused and counted."""

    def __init__(self, allowed) -> None:
        super().__init__()
        self.allowed = allowed
        self.refused = 0

    def _ok(self) -> bool:
        if self.allowed():
            return True
        self.refused += 1
        return False

    def execute(self, *args, **kwargs):
        return self._ok() and super().execute(*args, **kwargs)

    def type_text(self, text):
        return self._ok() and super().type_text(text)

    def pointer(self, *args, **kwargs):
        return self._ok() and super().pointer(*args, **kwargs)


class VirtualMic:
    """Stands in for sounddevice: pushes 20 ms chunks into the controller's audio callback in real time."""

    def __init__(self) -> None:
        self.chunks: queue.Queue = queue.Queue()
        self.controller = None
        self.running = False
        self.speech_ended_at = 0.0
        self.step_started = 0.0

    def install(self) -> None:
        mic = self

        def fake_stream(controller) -> bool:
            mic.controller, mic.running = controller, True
            threading.Thread(target=mic._feed, daemon=True).start()
            return True

        voice_controller.VoiceController._init_audio_stream = fake_stream

    def _feed(self) -> None:
        silence = b"\x00\x00" * (CHUNK // 2)
        due = time.perf_counter()
        while self.running:
            try:
                chunk = self.chunks.get_nowait()
            except queue.Empty:
                chunk = silence
            if chunk is None:
                self.speech_ended_at = time.perf_counter()
                continue
            self.controller._audio_stream_callback(SimpleNamespace(tobytes=lambda c=chunk: c), CHUNK // 2, None, None)
            due += 0.02
            time.sleep(max(0.0, due - time.perf_counter()))

    def say(self, pcm: bytes) -> None:
        for offset in range(0, len(pcm), CHUNK):
            self.chunks.put(pcm[offset:offset + CHUNK].ljust(CHUNK, b"\x00"))
        self.chunks.put(None)


class Target(tk.Tk):
    """The window that receives the injected input and records what arrived."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Voice Rig Target")
        self.geometry("520x320+240+160")
        self.attributes("-topmost", True)
        self.events: list[dict] = []
        self.text = tk.Text(self, height=8, font=("Segoe UI", 12))
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        self.button = tk.Button(self, text="Click target", height=2,
                                command=lambda: self.events.append({"t": time.perf_counter(), "kind": "click"}))
        self.button.pack(pady=(0, 12))
        self.bind_all("<Key>", self._key)
        self.text.focus_set()
        self.update()
        self.hwnd = user32.GetAncestor(self.winfo_id(), 2)  # GA_ROOT; read by other threads, so cached

    def _key(self, event) -> None:
        mods = [name for bit, name in ((0x4, "ctrl"), (0x20000, "alt"), (0x1, "shift")) if event.state & bit]
        if mods and event.keysym.lower() not in {"control_l", "control_r", "shift_l", "shift_r", "alt_l", "alt_r"}:
            self.events.append({"t": time.perf_counter(), "kind": "key", "value": "+".join([*mods, event.keysym.lower()])})

    def focused(self) -> bool:
        """Safe from any thread: plain Win32, no Tk calls."""
        return user32.GetForegroundWindow() == self.hwnd

    def grab_focus(self) -> bool:
        """Bring the window to the front. Windows refuses a plain SetForegroundWindow from a background
        process, so attach to the foreground window's input thread first (the documented workaround)."""
        self.deiconify()
        self.lift()
        hwnd = self.hwnd
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        foreground = user32.GetForegroundWindow()
        theirs = user32.GetWindowThreadProcessId(foreground, None)
        ours = ctypes.windll.kernel32.GetCurrentThreadId()
        attached = bool(theirs) and theirs != ours and user32.AttachThreadInput(ours, theirs, True)
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(ours, theirs, False)
        self.focus_force()
        self.text.focus_set()
        self.update()
        return self.focused()


def build_profiles(program: str) -> profiles.ProfilesDocument:
    def cmd(cid, phrase, keys):
        return profiles.VoiceCommand(id=cid, phrase=phrase, keys=keys)

    base = profiles.Profile(id="rig-base", name="Rig base", commands=[cmd("save", "zapisz", ["ctrl", "s"])])
    special = profiles.Profile(id="rig-target", name="Rig target", apps=[program], commands=[
        cmd("save-as", "zapisz", ["ctrl", "shift", "s"]), cmd("bold", "pogrub", ["ctrl", "b"]),
    ])
    return profiles.ProfilesDocument(active_profile_id="rig-base", profiles=[base, special])


def run_scenario(window: Target, args, results: list[dict]) -> None:
    def ui(fn, default=None):
        box, done = {}, threading.Event()

        def call():
            try:
                box["v"] = fn()
            finally:
                done.set()

        window.after(0, call)
        done.wait(5)
        return box.get("v", default)

    mic = VirtualMic()
    mic.install()
    guard = Guarded(window.focused)
    if not ui(window.grab_focus):
        print(f"ABORT: the rig window could not take the focus (in front: {foreground_process()}); nothing was injected.")
        return
    program = foreground_process()  # the rig window's own process name, as the application will see it
    config.save(config.Settings(engine_id=args.engine, language="pl_PL", auto_profile=True, matching_threshold=0.8))
    service = VoiceService()
    service._settings = config.load()
    service._profiles = build_profiles(program)
    service._key_controller = guard
    heard: list[str] = []
    service.set_event_sink(lambda e: heard.append(e["text"]) if e.get("type") == "heard" else None)

    def check(name, expected, ok, started, detail=""):
        latency = None
        if ok and started and mic.speech_ended_at >= mic.step_started:
            latency = round((time.perf_counter() - mic.speech_ended_at) * 1000)
        status = service.status()
        diag = (f"front={foreground_process()} refused={guard.refused} "
                f"in_use={status['effective_profile_id']} err={status['error']}")
        results.append({"step": name, "expected": expected, "passed": bool(ok), "heard": list(heard[-2:]),
                        "ms_after_speech": latency, "detail": detail, "diagnostics": diag})
        print(f"{'PASS' if ok else 'FAIL'}  {name:<34} heard={heard[-1:]} "
              f"{f'{latency} ms ' if latency is not None else ''}{detail} [{diag}]")

    def say_and_wait(text, condition, timeout=20.0):
        if not ui(window.grab_focus):
            return False
        mic.step_started = time.perf_counter()
        mic.say(audio.synthesize(text, args.voice))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if ui(condition):
                return True
            time.sleep(0.05)
        return False

    print(f"engine={args.engine} voice={args.voice} rig process={program}")
    started = time.perf_counter()
    service.start()
    print(f"service started in {time.perf_counter() - started:.1f} s (listening={service.status()['listening']})")

    keys = lambda value: any(e["kind"] == "key" and e["value"] == value for e in window.events)  # noqa: E731

    # 1. dictation
    ok = say_and_wait("dyktuj", lambda: service.status()["dictating"])
    check("dictation switches on", "dictating=True", ok, True)
    ok = say_and_wait("dzień dobry świecie", lambda: "dzień dobry" in window.text.get("1.0", "end").lower())
    typed = ui(lambda: window.text.get("1.0", "end").strip())
    check("dictated text is typed", "'Dzień dobry świecie'", ok, True, f"typed={typed!r}")
    ok = say_and_wait("koniec dyktowania", lambda: not service.status()["dictating"])
    check("dictation switches off", "dictating=False", ok, True)

    # 2. profile chosen by the focused program, then its own commands
    effective = service.status()["effective_profile_id"]
    check("window selects its profile", "rig-target", effective == "rig-target", False, f"in use={effective}")
    ok = say_and_wait("zapisz", lambda: keys("ctrl+shift+s") or keys("ctrl+s"))
    check("same phrase, window's own keys", "ctrl+shift+s (not ctrl+s)", ok and keys("ctrl+shift+s") and not keys("ctrl+s"), True)
    ok = say_and_wait("pogrub", lambda: keys("ctrl+b"))
    check("command only the window profile has", "ctrl+b", ok, True)

    # 3. pointer
    center = ui(lambda: (window.button.winfo_rootx() + window.button.winfo_width() // 2,
                         window.button.winfo_rooty() + window.button.winfo_height() // 2))
    user32.SetCursorPos(*center)
    point = ctypes.wintypes.POINT()

    def cursor_x():
        user32.GetCursorPos(ctypes.byref(point))
        return point.x

    ok = say_and_wait("mysz w prawo 50", lambda: abs(cursor_x() - (center[0] + 50)) <= 2)
    check("pointer moves right 50 px", f"x={center[0] + 50}", ok, True, f"x={cursor_x()}")
    ok = say_and_wait("mysz w lewo 50", lambda: abs(cursor_x() - center[0]) <= 2)
    check("pointer moves back", f"x={center[0]}", ok, True, f"x={cursor_x()}")
    before = len([e for e in window.events if e["kind"] == "click"])
    ok = say_and_wait("kliknij", lambda: len([e for e in window.events if e["kind"] == "click"]) > before)
    check("click lands on the button", "1 click", ok, True)

    # 4. safety net: without the focus nothing may be sent anywhere
    ui(window.iconify)
    time.sleep(0.5)
    refused_before, events_before = guard.refused, len(window.events)
    mic.say(audio.synthesize("pogrub", args.voice))
    time.sleep(8)
    check("no focus: input is refused", "refused, nothing delivered",
          guard.refused > refused_before and len(window.events) == events_before, False,
          f"refused={guard.refused - refused_before}")
    ui(window.grab_focus)

    service.stop()
    mic.running = False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engine", default="faster-whisper-base")
    parser.add_argument("--voice", default="Paulina")
    args = parser.parse_args()
    if not audio.find_voice(args.voice):
        print(f"Voice not installed: {args.voice}")
        return 2
    if not audio.engine_ready(args.engine):
        print(f"Speech model not downloaded: {args.engine}")
        return 2
    import ctypes.wintypes  # noqa: F401  (POINTER types used above)

    window = Target()
    results: list[dict] = []
    failure: list[BaseException] = []

    def worker() -> None:
        try:
            run_scenario(window, args, results)
        except BaseException as exc:  # noqa: BLE001
            failure.append(exc)
            print(f"ERROR: {type(exc).__name__}: {exc}")
        finally:
            window.after(0, window.destroy)

    window.after(600, lambda: threading.Thread(target=worker, daemon=True).start())
    window.mainloop()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    passed = sum(item["passed"] for item in results)
    print(f"\n{passed}/{len(results)} passed; report: {REPORT}")
    return 0 if results and passed == len(results) and not failure else 1


if __name__ == "__main__":
    sys.exit(main())
