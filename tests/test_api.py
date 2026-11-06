"""REST API against the contract in docs/CONTRACTS.md.

Everything runs on the Starlette TestClient. The voice service gets a dummy
controller instead of a microphone; command previews never generate system
input, and the former application update channel stays disconnected.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest
import requests
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import config, paths
from server import api as server_api

TOKEN = "test-token"
API = "/api/v1"

SETTINGS_KEYS = {
    "language",
    "ui_language",
    "engine_id",
    "matching_threshold",
    "audio_device",
    "start_with_windows",
    "start_listening_on_launch",
    "theme",
    "skipped_version",
    "check_updates",
    "auto_profile",
    "disabled_modules",
}

STATUS_KEYS = {
    "dictating",
    "listening",
    "active_profile_id",
    "profile_name",
    "held_keys",
    "held_command_ids",
    "engine_id",
    "engine_name",
    "version",
    "mappings_count",
    "last_command",
    "last_heard",
    "update_available",
}


class DummyController:
    """Stands in for the audio controller without opening a microphone."""

    def __init__(self) -> None:
        self.is_listening = False
        self.transcriber = object()
        self.settings = None

    def start_listening(self) -> bool:
        self.is_listening = True
        return True

    def stop_listening(self) -> None:
        self.is_listening = False


@pytest.fixture
def dummy_service(lolvoice_home):
    from controller.service import get_service

    service = get_service()
    service._controller = DummyController()
    return service


# --- auth ---------------------------------------------------------------


def test_missing_token_is_rejected(api_app):
    with TestClient(api_app) as client:
        assert client.get(f"{API}/status").status_code == 401


def test_wrong_token_is_rejected(api_app):
    with TestClient(api_app) as client:
        response = client.get(f"{API}/status", headers={"X-Auth-Token": "nope"})
        assert response.status_code == 401
        assert response.json()["detail"] == "Unauthorized"


def test_valid_token_in_header_and_query(api_app):
    with TestClient(api_app) as client:
        assert client.get(f"{API}/status", headers={"X-Auth-Token": TOKEN}).status_code == 200
        assert client.get(f"{API}/status", params={"token": TOKEN}).status_code == 200


def test_non_loopback_origin_is_forbidden(api_app):
    with TestClient(api_app, client=("203.0.113.7", 4444)) as client:
        response = client.get(f"{API}/status", headers={"X-Auth-Token": TOKEN})
        assert response.status_code == 403
        assert response.json()["detail"] == "Forbidden"


def test_panel_index_is_served_without_a_token(api_app):
    with TestClient(api_app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert TOKEN in response.text
        assert "window.__LOLVOICE__" in response.text


@pytest.mark.parametrize("path", ["/profiles", "/commands/test", "/keys/release"])
def test_profile_endpoints_require_authentication(api_app, path):
    with TestClient(api_app) as client:
        response = client.get(f"{API}{path}") if path == "/profiles" else client.post(f"{API}{path}", json={})
        assert response.status_code == 401


def test_socket_rejects_an_invalid_token(api_app):
    with TestClient(api_app) as client:
        with pytest.raises(WebSocketDisconnect) as error, client.websocket_connect("/ws/status?token=wrong"):
            pass
        assert error.value.code == 4401


def test_socket_rejects_a_non_loopback_client(api_app):
    with TestClient(api_app, client=("203.0.113.7", 4444)) as client:
        with pytest.raises(WebSocketDisconnect) as error, client.websocket_connect(f"/ws/status?token={TOKEN}"):
            pass
        assert error.value.code == 4403


def test_authenticated_socket_receives_the_status(api_app):
    with TestClient(api_app) as client, client.websocket_connect(f"/ws/status?token={TOKEN}") as socket:
        frame = socket.receive_json()
        assert frame["type"] == "status"
        assert set(frame) >= STATUS_KEYS


# --- status and listening -------------------------------------------------


def test_status_shape(api_client, dummy_service):
    payload = api_client.get(f"{API}/status").json()
    assert set(payload) >= STATUS_KEYS
    assert payload["active_profile_id"] == dummy_service.profiles_document()["active_profile_id"]
    assert payload["profile_name"]
    assert payload["held_keys"] == []
    assert "champion" not in payload
    assert isinstance(payload["mappings_count"], int)
    assert isinstance(payload["listening"], bool)
    assert payload["version"]


def test_listening_start_and_stop(api_client, dummy_service):
    started = api_client.post(f"{API}/listening/start").json()
    assert set(started) >= {"listening"}
    assert started["listening"] is True
    assert api_client.get(f"{API}/status").json()["listening"] is True

    stopped = api_client.post(f"{API}/listening/stop").json()
    assert stopped["listening"] is False
    assert api_client.get(f"{API}/status").json()["listening"] is False


def test_listening_start_reports_a_failure_instead_of_raising(api_client, dummy_service):
    def boom() -> bool:
        raise RuntimeError("no audio device")

    dummy_service._controller.start_listening = boom
    payload = api_client.post(f"{API}/listening/start").json()
    assert payload["listening"] is False


# --- settings -------------------------------------------------------------


def test_settings_get_returns_the_full_model(api_client):
    payload = api_client.get(f"{API}/settings").json()
    assert set(payload) == SETTINGS_KEYS


def test_settings_put_applies_a_partial_patch_and_persists(api_client, dummy_service):
    before = api_client.get(f"{API}/settings").json()

    response = api_client.put(f"{API}/settings", json={"theme": "dark", "audio_device": "Mikrofon"})
    assert response.status_code == 200
    updated = response.json()
    assert set(updated) == SETTINGS_KEYS
    assert updated["theme"] == "dark"
    assert updated["audio_device"] == "Mikrofon"
    assert updated["language"] == before["language"]
    assert updated["engine_id"] == before["engine_id"]

    on_disk = json.loads(paths.CONFIG_FILE.read_text(encoding="utf-8"))
    assert on_disk["theme"] == "dark"
    assert on_disk["audio_device"] == "Mikrofon"

    config.reset_cache()
    assert config.load().audio_device == "Mikrofon"


def test_settings_put_reaches_the_service(api_client, dummy_service):
    api_client.put(f"{API}/settings", json={"language": "en_US"})
    assert dummy_service.settings.language == "en_US"
    assert dummy_service._controller.settings.language == "en_US"


@pytest.mark.parametrize(
    "patch",
    [
        {"ui_language": "telepathy"},
        {"audio_device": []},
        {"theme": "neon"},
        {"check_updates": "maybe"},
    ],
)
def test_settings_put_rejects_an_invalid_value(api_client, patch):
    """An unknown value is a client error, and nothing is written."""
    before = api_client.get(f"{API}/settings").json()
    on_disk_before = paths.CONFIG_FILE.read_text(encoding="utf-8")

    response = api_client.put(f"{API}/settings", json=patch)
    assert response.status_code == 422

    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert detail
    field = next(iter(patch))
    assert any(field in map(str, entry.get("loc", ())) for entry in detail)
    assert all("url" not in entry for entry in detail)

    assert api_client.get(f"{API}/settings").json() == before
    assert paths.CONFIG_FILE.read_text(encoding="utf-8") == on_disk_before

    config.reset_cache()
    assert config.load().model_dump() == before


def test_settings_put_rejects_an_invalid_value_without_touching_the_service(api_client, dummy_service):
    before = dummy_service.settings.model_dump()
    assert api_client.put(f"{API}/settings", json={"theme": "neon"}).status_code == 422
    assert dummy_service.settings.model_dump() == before


def test_settings_put_with_an_empty_body_changes_nothing(api_client):
    before = api_client.get(f"{API}/settings").json()
    assert api_client.put(f"{API}/settings", json={}).json() == before


# --- engines ---------------------------------------------------------------


def test_engines_report_install_state(api_client):
    payload = api_client.get(f"{API}/engines").json()
    assert set(payload) == {"engines"}
    assert payload["engines"]
    for engine in payload["engines"]:
        assert {"id", "name", "installed", "active", "size_bytes", "requires_cuda"} <= set(engine)
        assert isinstance(engine["installed"], bool)
        assert isinstance(engine["active"], bool)
    assert sum(1 for engine in payload["engines"] if engine["active"]) <= 1


def test_engine_activate_updates_the_settings(api_client, dummy_service):
    engines = api_client.get(f"{API}/engines").json()["engines"]
    target = engines[-1]["id"]
    payload = api_client.post(f"{API}/engines/{target}/activate").json()
    assert payload == {"engine_id": target}
    assert config.load().engine_id == target


def test_engine_cancel(api_client):
    assert api_client.post(f"{API}/engines/whisper-tiny/cancel").json() == {"cancelled": True}


def test_engine_download_starts_a_worker(api_client, monkeypatch):
    from app import engines

    calls: list[str] = []
    monkeypatch.setattr(engines, "download", lambda engine_id, progress=None: calls.append(engine_id))
    payload = api_client.post(f"{API}/engines/whisper-tiny/download").json()
    assert payload == {"started": True}


# --- audio ------------------------------------------------------------------


def test_audio_devices_shape(api_client, dummy_service, monkeypatch):
    monkeypatch.setattr(
        type(dummy_service), "list_audio_devices", lambda _self: [{"id": "1", "name": "Mic", "default": True}]
    )
    payload = api_client.get(f"{API}/audio/devices").json()
    assert set(payload) >= {"devices"}
    for device in payload["devices"]:
        assert set(device) == {"id", "name", "default"}


def test_audio_devices_without_hardware(api_client, dummy_service):
    payload = api_client.get(f"{API}/audio/devices").json()
    assert isinstance(payload["devices"], list)


def test_audio_test_shape(api_client, dummy_service, monkeypatch):
    monkeypatch.setattr(
        type(dummy_service), "test_microphone", lambda _self, seconds=3: {"level": 0.25, "transcript": "flash"}
    )
    payload = api_client.post(f"{API}/audio/test", json={"seconds": 1}).json()
    assert payload == {"level": 0.25, "transcript": "flash"}


def test_audio_test_survives_a_missing_microphone(api_client, dummy_service, monkeypatch):
    sounddevice = pytest.importorskip("sounddevice")

    def no_input_device(*_args, **_kwargs):
        raise RuntimeError("Error querying device: no input device available")

    monkeypatch.setattr(sounddevice, "rec", no_input_device)
    payload = api_client.post(f"{API}/audio/test", json={"seconds": 1}).json()
    assert set(payload) >= {"level", "transcript"}
    assert payload["level"] == 0.0
    assert payload["transcript"] == ""


@pytest.mark.parametrize("seconds", [-1, 0, 11, "many"])
def test_audio_test_rejects_an_invalid_duration(api_client, seconds):
    assert api_client.post(f"{API}/audio/test", json={"seconds": seconds}).status_code == 422


# --- profile documents and command previews -----------------------------------


def test_profiles_document_shape(api_client, dummy_service):
    response = api_client.get(f"{API}/profiles")
    assert response.status_code == 200
    document = response.json()
    assert set(document) == {"version", "active_profile_id", "profiles"}
    assert document["version"] == 1
    assert document["profiles"]
    assert document == dummy_service.profiles_document()


def test_profile_edits_are_persisted(api_client, dummy_service):
    document = api_client.get(f"{API}/profiles").json()
    document["profiles"][0]["name"] = "Mój profil"
    response = api_client.put(f"{API}/profiles", json=document)
    assert response.status_code == 200
    assert response.json() == document
    assert api_client.get(f"{API}/profiles").json() == document


def test_invalid_profile_document_is_rejected_without_changes(api_client):
    before = api_client.get(f"{API}/profiles").json()
    document = json.loads(json.dumps(before))
    document["active_profile_id"] = "missing-profile"
    response = api_client.put(f"{API}/profiles", json=document)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert api_client.get(f"{API}/profiles").json() == before


def test_profile_save_failure_returns_an_error(api_client, dummy_service, monkeypatch):
    document = dummy_service.profiles_document()

    def fail(_document):
        raise OSError("read-only directory")

    monkeypatch.setattr(dummy_service, "replace_profiles", fail)
    assert api_client.put(f"{API}/profiles", json=document).status_code == 500


def test_command_preview_matches_without_pressing_keys(api_client, dummy_service, monkeypatch):
    document = dummy_service.profiles_document()
    profile = next(row for row in document["profiles"] if row["id"] == document["active_profile_id"])
    command = next(row for row in profile["commands"] if row["enabled"])

    def no_input(*_args, **_kwargs):
        raise AssertionError("Command previews must not generate system input")

    monkeypatch.setattr(dummy_service, "handle_transcript", no_input)
    response = api_client.post(f"{API}/commands/test", json={"text": command["phrase"]})
    assert response.status_code == 200
    preview = response.json()
    assert preview["matched"] is True
    assert preview["command"]["id"] == command["id"]
    assert preview["profile_id"] == profile["id"]
    assert dummy_service.status()["held_keys"] == []


def test_command_preview_requires_a_nonempty_text(api_client):
    assert api_client.post(f"{API}/commands/test", json={"text": ""}).status_code == 422
    assert api_client.post(f"{API}/commands/test", json={"text": ["flash"]}).status_code == 422


def test_release_all_calls_the_service(api_client, dummy_service, monkeypatch):
    calls = []
    monkeypatch.setattr(dummy_service, "release_all", lambda: calls.append(True))
    assert api_client.post(f"{API}/keys/release").json() == {"released": True}
    assert calls == [True]


# --- logs ---------------------------------------------------------------------


def test_logs_listing_shape(api_client):
    from app import logging_setup

    logging_setup.get_logger("test").warning("something happened")
    payload = api_client.get(f"{API}/logs", params={"limit": 10}).json()
    assert set(payload) == {"files", "tail"}
    assert isinstance(payload["files"], list)
    for entry in payload["files"]:
        assert set(entry) == {"name", "size", "modified"}
    for line in payload["tail"]:
        assert set(line) == {"time", "level", "name", "message"}


def test_logs_download_returns_a_zip_with_system_info(api_client):
    (paths.LOG_DIR / "lolvoice.log").write_text("hello\n", encoding="utf-8")

    response = api_client.get(f"{API}/logs/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert "system-info.txt" in names
        assert "logs/lolvoice.log" in names
        info = archive.read("system-info.txt").decode("utf-8")
        assert "app_version:" in info
        assert str(paths.DATA_DIR) in info


# --- updates --------------------------------------------------------------------


def test_unconfigured_updates_never_contact_the_old_lol_release_channel(api_client, monkeypatch):
    def no_network(*_args, **_kwargs):
        raise AssertionError("The former release channel must not be contacted")

    monkeypatch.setattr(requests, "get", no_network)
    payload = api_client.get(f"{API}/update/check", params={"force": "true"}).json()
    assert set(payload) == {"current", "latest", "available", "url", "notes"}
    assert payload["latest"] is None
    assert payload["available"] is False
    assert payload["url"] is None
    assert api_client.get(f"{API}/status").json()["update_available"] is False


def test_update_install_does_not_start_without_a_release_channel(api_client):
    payload = api_client.post(f"{API}/update/install").json()
    assert payload == {"started": False, "reason": "release_channel_not_configured"}


# --- quit -------------------------------------------------------------------------


def test_quit_calls_the_callback(lolvoice_home):
    called: list[bool] = []
    app = server_api.create_app(port=21999, token=TOKEN, on_quit=lambda: called.append(True))
    with TestClient(app) as client:
        client.headers.update({"X-Auth-Token": TOKEN})
        assert client.post(f"{API}/app/quit").json() == {"ok": True}


def test_teach_endpoint(api_client, dummy_service):
    command = dummy_service.profiles_document()["profiles"][0]["commands"][0]
    ok = api_client.post(f"{API}/commands/teach", json={"text": "mis hearing", "command_id": command["id"]})
    assert ok.status_code == 200
    assert dummy_service.test_command("mis hearing")["matched"]
    missing = api_client.post(f"{API}/commands/teach", json={"text": "x", "command_id": "nope"})
    assert missing.status_code == 404


def test_modules_endpoint(api_client, dummy_service):
    response = api_client.get(f"{API}/modules")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()["modules"]} >= {"profile", "dictation", "mouse", "alias"}
