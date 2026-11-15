"""Authenticated, scoped callbacks from our private satellite App."""

import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


def load_key(config_path):
    path = Path(config_path) / "fish_live3_worker_secret"
    if not path.exists():
        with path.open("x", encoding="utf-8") as stream:
            stream.write(secrets.token_urlsafe(48))
        path.chmod(0o600)
    return path.read_text(encoding="utf-8").strip()


class WorkerToolView(HomeAssistantView):
    url = "/api/fish_live3/worker-tool"
    name = "api:fish_live3:worker-tool"
    requires_auth = True

    async def post(self, request):
        hass = request.app[KEY_HASS]
        expected = hass.data.get(DOMAIN + "_worker_key", "")
        data = await request.json()
        supplied = data.get("bridge_key", "")
        if (
            not expected
            or not isinstance(supplied, str)
            or not secrets.compare_digest(supplied, expected)
        ):
            raise web.HTTPForbidden()
        for bridge in hass.data.get(DOMAIN, {}).values():
            for turn in bridge.turns.values():
                if turn.bridge_id == data.get("bridge_id") and turn.pending:
                    try:
                        result = await bridge.tool(
                            data.get("name"), data.get("params", {}), turn.context, turn.device_id
                        )
                    except (HomeAssistantError, ValueError):
                        return self.json(
                            {"error": "Home Assistant could not complete that request"},
                            status_code=400,
                        )
                    return self.json(result)
        raise web.HTTPForbidden()


def validate_worker_url(value):
    """Accept only the private Supervisor DNS name of this specific app."""
    if not isinstance(value, str):
        raise ValueError("Invalid worker address")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.port != 8789
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or not re.fullmatch(r"(?:[a-z0-9]+-)?fish-live3-worker", parsed.hostname or "")
    ):
        raise ValueError("Invalid worker address")
    return f"http://{parsed.hostname}:8789"


class WorkerRegisterView(HomeAssistantView):
    """Discover the app hostname without assuming a repository hash."""

    url = "/api/fish_live3/worker-register"
    name = "api:fish_live3:worker-register"
    requires_auth = True

    async def post(self, request):
        hass = request.app[KEY_HASS]
        expected = hass.data.get(DOMAIN + "_worker_key", "")
        data = await request.json()
        supplied = data.get("bridge_key", "")
        if (
            not expected
            or not isinstance(supplied, str)
            or not secrets.compare_digest(supplied, expected)
        ):
            raise web.HTTPForbidden()
        try:
            worker_url = validate_worker_url(data.get("worker_url"))
        except ValueError as error:
            raise web.HTTPBadRequest() from error
        hass.data[DOMAIN + "_worker_url"] = worker_url
        hass.data[DOMAIN + "_worker_seen"] = time.monotonic()
        return self.json({"registered": True})
