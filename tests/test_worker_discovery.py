"""Worker registration contract, including rejected external addresses."""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from aiohttp import web

ROOT = Path(__file__).resolve().parent.parent


class View:
    def json(self, data, **kwargs):
        return data


http = types.ModuleType("homeassistant.components.http")
http.HomeAssistantView = View
http.KEY_HASS = "hass"
sys.modules["homeassistant.components.http"] = http

from custom_components.fish_live3.worker_api import WorkerRegisterView, validate_worker_url


@pytest.mark.parametrize(
    "url", ["http://local-fish-live3-worker:8789", "http://ab12cd34-fish-live3-worker:8789/"]
)
def test_repository_and_local_hostnames(url):
    assert validate_worker_url(url) == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com:8789",
        "http://127.0.0.1:8789",
        "https://local-fish-live3-worker:8789",
        "http://local-fish-live3-worker:80",
        "http://user:pass@local-fish-live3-worker:8789",
        "http://local-fish-live3-worker:8789/private",
        "http://local-fish-live3-worker:8789?url=other",
        None,
    ],
)
def test_rejects_public_or_unscoped_worker_addresses(url):
    with pytest.raises(ValueError):
        validate_worker_url(url)


def test_worker_registration_requires_the_private_key():
    async def run():
        view = WorkerRegisterView()
        assert view.requires_auth is True
        hass = types.SimpleNamespace(data={"fish_live3_worker_key": "fixture-key"})
        request = types.SimpleNamespace(
            app={"hass": hass},
            json=AsyncMock(
                return_value={
                    "bridge_key": "wrong",
                    "worker_url": "http://ab12cd34-fish-live3-worker:8789",
                }
            ),
        )
        with pytest.raises(web.HTTPForbidden):
            await view.post(request)
        request.json = AsyncMock(
            return_value={
                "bridge_key": "fixture-key",
                "worker_url": "http://ab12cd34-fish-live3-worker:8789",
            }
        )
        assert await view.post(request) == {"registered": True}
        assert hass.data["fish_live3_worker_url"] == "http://ab12cd34-fish-live3-worker:8789"

    asyncio.run(run())


def test_worker_uses_its_own_supervisor_hostname(monkeypatch, tmp_path):
    worker = ROOT / "fish_live3_worker/worker"
    monkeypatch.syspath_prepend(str(worker))
    spec = importlib.util.spec_from_file_location("worker_server_test", worker / "server.py")
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    key_path = tmp_path / "bridge-key"
    key_path.write_text("fixture-key", encoding="utf-8")
    monkeypatch.setattr(server, "KEY_PATH", key_path)
    monkeypatch.setenv("SUPERVISOR_TOKEN", "fixture-supervisor-token")
    posted = []

    class Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def json(self):
            return {"data": {"hostname": "ab12cd34-fish-live3-worker"}}

        async def read(self):
            return b"{}"

    class Session:
        def get(self, url, **kwargs):
            assert url == "http://supervisor/addons/self/info"
            return Response()

        def post(self, url, **kwargs):
            posted.append((url, kwargs["json"]))
            return Response()

    async def stop_after_iteration(seconds):
        raise asyncio.CancelledError()

    monkeypatch.setattr(server.asyncio, "sleep", stop_after_iteration)

    async def run():
        with pytest.raises(asyncio.CancelledError):
            await server.register_worker({"http": Session()})

    asyncio.run(run())
    assert posted == [
        (
            "http://supervisor/core/api/fish_live3/worker-register",
            {"bridge_key": "fixture-key", "worker_url": "http://ab12cd34-fish-live3-worker:8789"},
        )
    ]
