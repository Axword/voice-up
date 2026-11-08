"""Local speech recognition and execution of the active voice profile.

Audio and system input libraries load only when used, so the panel and its
validation endpoints also work without an audio device or a speech model.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from app import aliases, app_icons, config, engines, modules, profiles, version
from app.known_apps import apps_for
from app.foreground import foreground_process
from app.office_modules import DictationRouter, MouseExecutor, MouseRouter, TypeExecutor
from app.pipeline import (
    Intent, KeyAction, KeyExecutor, MouseAction, Pipeline, ProfileRouter, RouteContext, StateAction,
    StateExecutor, TypeTextAction,
)
from app.config import Settings
from app.logging_setup import get_logger
from controller.transcriber import clean_text
from controls.key_controller import KeyController

log = get_logger("service")
EventSink = Callable[[dict], None]
INSTALLED_TTL = 60.0
MAX_ICON_LOOKUPS = 60
TranscriberFn = Callable[[bytes], str]


class VoiceService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._settings: Settings | None = None
        self._profiles: profiles.ProfilesDocument | None = None
        self._key_controller: KeyController | None = None
        self._controller: Any | None = None
        self._engine: Any | None = None
        self._transcriber: TranscriberFn | None = None
        self._event_sink: EventSink | None = None
        self._listening = False
        self._last_command: str | None = None
        self._last_heard: str | None = None
        self._last_error: str | None = None
        self.update_available = False
        self._installed_lock = threading.Lock()
        self._last_profile_id: str | None = None
        self._installed_cache: tuple[float, list[str]] | None = None
        self._dictation = DictationRouter()
        self._pipeline = Pipeline(
            routers=[self._dictation, aliases.AliasRouter(), ProfileRouter(), MouseRouter()],
            executors={
                KeyAction: KeyExecutor(lambda: self.key_controller),
                TypeTextAction: TypeExecutor(lambda: self.key_controller),
                MouseAction: MouseExecutor(lambda: self.key_controller),
                StateAction: StateExecutor(self._apply_state),
            },
        )

    @property
    def pipeline(self) -> Pipeline:
        return self._pipeline

    @property
    def settings(self) -> Settings:
        with self._lock:
            if self._settings is None:
                if self._profiles is None:
                    self._profiles = profiles.load()
                self._settings = config.load()
                self._synchronize_profile_language()
            return self._settings

    @property
    def document(self) -> profiles.ProfilesDocument:
        with self._lock:
            if self._profiles is None:
                self._profiles = profiles.load()
                self._synchronize_profile_language()
            return self._profiles

    def _synchronize_profile_language(self) -> None:
        """Keep the recognizer configured for the active profile's phrases."""
        if self._profiles is None:
            return
        language = self._profiles.active_profile.language
        settings = self.settings
        if settings.language != language:
            self._settings = config.save(settings.model_copy(update={"language": language}))
        if self._controller is not None:
            self._controller.settings = self._settings

    @property
    def key_controller(self) -> KeyController:
        if self._key_controller is None:
            self._key_controller = KeyController()
        return self._key_controller

    def profiles_document(self) -> dict:
        with self._lock:
            return self.document.model_dump()

    def replace_profiles(self, payload: dict) -> dict:
        with self._lifecycle_lock:
            validated = profiles.ProfilesDocument.model_validate(payload)
            with self._lock:
                profiles.save(validated)
            # Restarting audio invalidates results captured for the old profile.
            was_listening = self.listening
            self.stop()
            with self._lock:
                self._profiles = validated
                self._synchronize_profile_language()
                self._last_command = None
            if was_listening:
                self.start()
            else:
                self._emit_status()
            return validated.model_dump()

    def set_event_sink(self, fn: EventSink | None) -> None:
        self._event_sink = fn

    def _emit(self, event: dict) -> None:
        if self._event_sink is not None:
            try:
                self._event_sink(event)
            except Exception as exc:
                log.warning("Event sink failed: %s", exc)

    def _emit_status(self) -> None:
        if self._event_sink is not None:
            try:
                self._emit({"type": "status", **self.status()})
            except Exception as exc:
                log.warning("Could not publish status: %s", exc)

    def _emit_log(self, level: str, message: str) -> None:
        log.log({"error": 40, "warning": 30}.get(level, 20), "%s", message)
        self._emit({"type": "log", "level": level, "message": message})

    def set_transcriber(self, fn: TranscriberFn | None) -> None:
        self._transcriber = fn

    def _engine_transcriber(self):
        if self._engine is None:
            from controller.transcriber import Transcriber

            self._engine = Transcriber()
        if not self._engine.loaded:
            self._engine.load()
        return self._engine

    def _transcribe(self, pcm: bytes) -> str:
        _ = self.document
        self._synchronize_profile_language()
        if self._transcriber is not None:
            return clean_text(self._transcriber(pcm))
        if self._controller is not None:
            return self._controller.transcriber.transcribe_pcm(pcm, self.settings.language)
        return self._engine_transcriber().transcribe_pcm(pcm, self.settings.language)

    def feed_pcm(self, pcm: bytes) -> str:
        try:
            text = self._transcribe(pcm)
        except Exception as exc:
            self._emit_log("error", f"Transcription failed: {exc}")
            return ""
        if text:
            self.handle_transcript(text)
        return text

    def _apply_state(self, state: str) -> None:
        if state in {"dictation_on", "dictation_off"}:
            self._dictation.active = state == "dictation_on"

    def _route(self, text: str, profile: profiles.Profile, preview: bool = False) -> Intent | None:
        context = RouteContext(profile, self.settings.matching_threshold)
        # A preview must neither start dictation nor be swallowed by it.
        exclude = modules.inactive_ids(self.settings.disabled_modules)
        if "dictation" in exclude:
            self._dictation.active = False
        if preview:
            exclude |= {"dictation"}
        return self._pipeline.route(text, context, exclude)

    def _effective_profile(self) -> profiles.Profile:
        """The active profile, unless the focused program has its own profile in the same language."""
        active = self.document.active_profile
        if not self.settings.auto_profile or self._dictation.active:
            return active
        program = foreground_process()
        if not program:
            return active
        if program in apps_for(active):
            return active
        same_language = [p for p in self.document.profiles if p.language == active.language]
        # Profiles that name their program explicitly beat the built-in mapping.
        for profile in same_language:
            if program in (name.lower() for name in profile.apps):
                return profile
        for profile in same_language:
            if not profile.apps and program in apps_for(profile):
                return profile
        return active

    def installed_profile_ids(self) -> list[str]:
        """Profiles whose program is installed or running here (its icon could be read)."""
        from concurrent.futures import ThreadPoolExecutor

        with self._installed_lock:
            cached = self._installed_cache
            if cached is not None and time.monotonic() - cached[0] < INSTALLED_TTL:
                return list(cached[1])
            with self._lock:
                profile_apps = [(p.id, apps_for(p)) for p in self.document.profiles if apps_for(p)]
            # Profile files can name many programs; look each one up once and only so many.
            programs = list(dict.fromkeys(exe for _, exes in profile_apps for exe in exes))[:MAX_ICON_LOOKUPS]
            with ThreadPoolExecutor(max_workers=8) as pool:
                found = dict(zip(programs, pool.map(lambda exe: app_icons.icon_for((exe,)) is not None, programs)))
            ids = [pid for pid, exes in profile_apps if any(found.get(exe) for exe in exes)]
            self._installed_cache = (time.monotonic(), ids)
            return list(ids)

    def profile_icon(self, profile_id: str):
        """Path of the program icon for a profile, or None."""
        with self._lock:
            profile = next((p for p in self.document.profiles if p.id == profile_id), None)
        if profile is None:
            return None
        return app_icons.icon_for(apps_for(profile))

    def teach_alias(self, text: str, command_id: str, profile_id: str | None = None) -> dict:
        """Remember that `text` (a mishearing) means a command of a profile.

        Defaults to the profile selected in the panel, not the one a focused program may have
        switched to; the `heard` event names the profile that actually matched, so pass that id.
        """
        with self._lock:
            profile = next((p for p in self.document.profiles if p.id == profile_id), None) \
                if profile_id else self.document.active_profile
            if profile is None or not any(command.id == command_id for command in profile.commands):
                raise KeyError(command_id)
            aliases.teach(
                profile.id, text, command_id,
                frozenset(profiles.normalize_phrase(command.phrase) for command in profile.commands),
            )
            return {"profile_id": profile.id, "command_id": command_id, "text": text}

    def test_command(self, text: str) -> dict:
        """Match a phrase without recording audio or sending any system input."""
        with self._lock:
            # The panel previews the profile it shows, even while another program has the focus.
            profile = self.document.active_profile
            intent = self._route(text, profile, preview=True)
            command = intent.command if intent else None
            return {
                "text": text,
                "matched": intent is not None,
                "command": command.model_dump() if command else None,
                "profile_id": profile.id,
            }

    def handle_transcript(self, text: str) -> list[str] | None:
        cleaned = clean_text(text)
        if not cleaned:
            return None
        with self._lock:
            self._last_heard = cleaned
            profile = self._effective_profile()
            if self._last_profile_id is not None and profile.id != self._last_profile_id \
                    and self._key_controller is not None:
                self._key_controller.release_all()
            self._last_profile_id = profile.id
            intent = self._route(text, profile)
            action = intent.action if intent else None
            command = intent.command if intent else None
            keys = list(action.keys) if isinstance(action, KeyAction) else []
            executed = False
            if intent is not None:
                try:
                    executed = self._pipeline.execute(intent)
                except Exception as exc:
                    self._pipeline.release_all()
                    self._last_error = str(exc)
                    self._emit_log("error", f"Input action failed: {exc}")
                if executed:
                    self._last_command = cleaned
                    self._last_error = None
                    # Dictated text is private: log what ran, not what was said.
                    shown = "(dictation)" if intent.source == "dictation" else cleaned
                    log.info("Executed '%s' -> %s via %s", shown, intent.label if intent.source != "dictation" else "typed text", intent.source)
                else:
                    self._last_error = self._last_error or "Nie można wysłać przycisków do systemu."
            self._emit({
                "type": "heard", "text": cleaned, "matched": keys if intent else None,
                "command_id": command.id if command else None, "executed": executed,
                "profile_id": profile.id,
                "profile_name": profile.name,
                "mode": command.mode if command else None,
                "duration_ms": command.duration_ms if command else None,
                "held": bool(command and command.id in getattr(self._key_controller, "held_command_ids", [])),
                "error": self._last_error if intent and not executed else None,
                "source": intent.source if intent else None,
                "confidence": intent.confidence if intent else None,
                "time": time.time(),
            })
            self._emit_status()
            return keys if intent and executed else None

    def release_all(self) -> None:
        with self._lock:
            if self._key_controller is not None:
                self._key_controller.release_all()
        self._emit_status()

    def _ensure_controller(self):
        if self._controller is None:
            from controller.voice_controller import VoiceController

            self._controller = VoiceController(
                settings=self.settings, transcriber=self._engine_transcriber(), on_text=self._handle_live_transcript,
            )
        return self._controller

    def _handle_live_transcript(self, text: str, generation: int | None = None) -> list[str] | None:
        with self._lock:
            if not self._listening:
                return None
            if generation is not None and generation != getattr(self._controller, "_generation", None):
                return None
            return self.handle_transcript(text)

    def start(self) -> bool:
        with self._lifecycle_lock:
            with self._lock:
                if self.listening:
                    return True
            started, error = False, None
            try:
                with self._lock:
                    # Validate persisted profiles before starting the microphone.
                    _ = self.document
                    self._synchronize_profile_language()
                # Loading the speech model and opening the stream take seconds; the service lock
                # stays free meanwhile so status calls and the panel keep answering.
                controller = self._ensure_controller()
                started = bool(controller.start_listening() and controller.is_listening)
                error = None if started else "Mikrofon jest niedostępny."
            except Exception as exc:
                error = str(exc)
                self._emit_log("error", f"Could not start listening: {exc}")
            with self._lock:
                self._listening = started
                self._last_error = error
                if error and self._key_controller is not None:
                    self._key_controller.release_all()
            self._emit_status()
            return self._listening

    def stop(self) -> bool:
        with self._lifecycle_lock:
            with self._lock:
                controller = self._controller
                self._listening = False
                self._dictation.active = False
                if self._key_controller is not None:
                    self._key_controller.release_all()
            if controller is not None:
                try:
                    controller.stop_listening()
                except Exception as exc:
                    log.warning("Error stopping audio: %s", exc)
            self.release_all()
            return True

    @property
    def listening(self) -> bool:
        if self._controller is not None:
            return bool(self._controller.is_listening)
        return self._listening

    def apply_settings(self, settings: Settings, *, profile_language: bool = False) -> None:
        """Apply preferences; legacy recognition-language edits update the profile."""
        with self._lifecycle_lock:
            previous = self._settings
            was_listening = self.listening
            requested_language = settings.language
            document = self.document
            previous = previous or self._settings
            updated_document = None
            if profile_language and requested_language != document.active_profile.language:
                updated_document = document.model_copy(deep=True)
                updated_document.active_profile.language = requested_language
                profiles.save(updated_document)
            language = (
                updated_document.active_profile.language if updated_document else document.active_profile.language
            )
            settings = settings.model_copy(update={"language": language})
            audio_changed = previous is not None and (
                previous.audio_device != settings.audio_device or previous.language != settings.language
            )
            engine_changed = previous is not None and previous.engine_id != settings.engine_id
            if was_listening and (audio_changed or engine_changed):
                self.stop()
            if updated_document is not None:
                self._profiles = updated_document
            if config.load() != settings:
                config.save(settings)
            self._settings = settings
            if self._controller is not None:
                self._controller.settings = settings
            if engine_changed:
                self._engine = None
                self._controller = None
            if was_listening and (audio_changed or engine_changed):
                self.start()
            else:
                self._emit_status()

    def reload_engine(self) -> bool:
        with self._lifecycle_lock:
            was_listening = self.listening
            self.stop()
            self._engine = None
            self._controller = None
            try:
                engine = self._engine_transcriber()
            except Exception as exc:
                self._last_error = str(exc)
                self._emit_log("error", f"Engine reload failed: {exc}")
                self._emit_status()
                return False
            self._last_error = None
            self._emit_log("info", f"Engine loaded: {engine.engine_id}")
            if was_listening:
                return self.start()
            self._emit_status()
            return True

    def _active_engine(self) -> tuple[str, str]:
        try:
            engine = engines.resolve_active()
            return engine.id, engine.name
        except Exception:
            configured = engines.get(self.settings.engine_id)
            return self.settings.engine_id, configured.name if configured else ""

    def status(self) -> dict:
        engine_id, engine_name = self._active_engine()
        with self._lock:
            active = self.document.active_profile
            keys = self._key_controller
            return {
                "listening": self.listening,
                "active_profile_id": active.id,
                "profile_name": active.name,
                "engine_id": engine_id,
                "engine_name": engine_name,
                "version": version.get_version(),
                "mappings_count": sum(command.enabled for command in active.commands),
                "dictating": self._dictation.active,
                "effective_profile_id": self._effective_profile().id,
                "foreground": foreground_process() if self.settings.auto_profile else "",
                "held_keys": keys.held_keys if keys else [],
                "held_command_ids": keys.held_command_ids if keys else [],
                "last_command": self._last_command,
                "last_heard": self._last_heard,
                "update_available": self.update_available,
                "error": self._last_error,
            }

    def modules_status(self) -> list[dict]:
        return modules.status(self.settings.disabled_modules)

    def mappings(self) -> list[dict]:
        with self._lock:
            return [command.model_dump() for command in self.document.active_profile.commands]

    def set_update_available(self, available: bool) -> None:
        self.update_available = available
        self._emit_status()

    def list_audio_devices(self) -> list[dict]:
        """Wejsciowe urzadzenia audio jako [{id, name, default}]."""
        try:
            import sounddevice as sd

            all_devices = list(sd.query_devices())
            default_input = sd.default.device[0] if sd.default.device else None
            # Nazwy w starych API sa uciete do 31 znakow, wiec domyslne
            # urzadzenie dopasowujemy po prefiksie nazwy.
            default_name = ""
            if default_input is not None and 0 <= default_input < len(all_devices):
                default_name = all_devices[default_input].get("name", "")

            # PortAudio wystawia kazde urzadzenie po kilka razy (MME,
            # DirectSound, WASAPI, WDM-KS). Pokazujemy tylko WASAPI, a gdy go
            # nie ma, pierwsze wystapienie danej nazwy.
            hostapis = list(sd.query_hostapis())
            wasapi = next((i for i, api in enumerate(hostapis) if "WASAPI" in api.get("name", "")), None)

            devices = []
            seen_names: set[str] = set()
            for index, info in enumerate(all_devices):
                if info.get("max_input_channels", 0) <= 0:
                    continue
                if wasapi is not None and info.get("hostapi") != wasapi:
                    continue
                name = info.get("name", f"device {index}")
                if name in seen_names:
                    continue
                seen_names.add(name)
                is_default = bool(default_name) and (
                    name == default_name or name.startswith(default_name) or default_name.startswith(name)
                )
                devices.append({"id": name, "name": name, "default": is_default})
            if not devices:
                for index, info in enumerate(all_devices):
                    if info.get("max_input_channels", 0) <= 0:
                        continue
                    name = info.get("name", f"device {index}")
                    if name in seen_names:
                        continue
                    seen_names.add(name)
                    devices.append({"id": str(index), "name": name, "default": index == default_input})
            return devices
        except Exception as exc:  # brak PortAudio to normalny stan w CI
            log.warning("Audio devices unavailable: %s", exc)
            return []

    def test_microphone(self, seconds: int = 3) -> dict:
        """Nagrywa krotka probke i zwraca {level 0..1, transcript}."""
        result: dict = {"level": 0.0, "transcript": ""}
        try:
            import numpy as np
            import sounddevice as sd

            from controller.voice_controller import resolve_audio_device

            device = resolve_audio_device(self.settings.audio_device)

            frames = int(16000 * max(1, seconds))
            recording = sd.rec(frames, samplerate=16000, channels=1, dtype="int16", device=device)
            sd.wait()
            audio = np.asarray(recording, dtype=np.int16).reshape(-1)
            if audio.size:
                rms = float(np.sqrt(np.mean((audio.astype(np.float32) / 32768.0) ** 2)))
                result["level"] = round(min(1.0, rms * 4.0), 4)
            pcm = audio.tobytes()
        except Exception as exc:  # brak mikrofonu ma wrocic jako blad, nie wyjatek
            log.warning("Microphone test failed: %s", exc)
            result["error"] = str(exc)
            return result

        try:
            result["transcript"] = self._transcribe(pcm)
        except Exception as exc:  # brak modelu nie psuje pomiaru poziomu
            log.warning("Microphone test transcription failed: %s", exc)
            result["error"] = str(exc)
        return result


_service: VoiceService | None = None
_service_lock = threading.Lock()


def get_service() -> VoiceService:
    global _service
    with _service_lock:
        if _service is None:
            _service = VoiceService()
        return _service


def reset_service() -> None:
    global _service
    with _service_lock:
        previous = _service
        _service = None
    if previous is not None:
        previous.stop()
