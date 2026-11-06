"""Shared fixtures; every test uses an isolated application data directory."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_TOKEN = "test-token"


def _reset_app_state() -> None:
    from app import config, paths
    from controller import service
    from server import api, runtime

    service.reset_service()
    paths.refresh()
    config.reset_cache()
    api._service = None
    api._service_error = None
    runtime._current = None


@pytest.fixture(autouse=True)
def lolvoice_home(tmp_path, monkeypatch):
    home = tmp_path / "voice-control-home"
    home.mkdir()
    workdir = tmp_path / "cwd"
    workdir.mkdir()

    monkeypatch.setenv("LOLVOICE_HOME", str(home))
    monkeypatch.delenv("LOLVOICE_TOKEN", raising=False)
    monkeypatch.delenv("LOLVOICE_PORT", raising=False)
    monkeypatch.delenv("LOLVOICE_TRUSTED_HOSTS", raising=False)
    monkeypatch.chdir(workdir)

    _reset_app_state()
    from app import paths

    paths.ensure_dirs()
    yield home
    _reset_app_state()


@pytest.fixture
def workdir(lolvoice_home) -> Path:
    return Path.cwd()


@pytest.fixture
def settings(lolvoice_home):
    from app import config

    def make(persist: bool = False, **overrides):
        value = config.Settings(**overrides)
        if persist:
            config.save(value)
        return value

    return make


@pytest.fixture
def api_app(lolvoice_home):
    from server import api

    return api.create_app(port=21999, token=TEST_TOKEN)


@pytest.fixture
def api_client(api_app):
    from fastapi.testclient import TestClient

    with TestClient(api_app) as client:
        client.headers.update({"X-Auth-Token": TEST_TOKEN})
        yield client
