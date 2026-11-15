"""Private voice worker. No Fish API key, public port, or stored audio."""

import asyncio
import base64
import contextlib
import logging
import os
import secrets
import time
from pathlib import Path
from types import SimpleNamespace

from aiohttp import ClientError, ClientSession, ClientTimeout, web
from transport import WorkerTurn

KEY_PATH = Path("/homeassistant/fish_live3_worker_secret")
ROOMS = {}


def key():
    return KEY_PATH.read_text(encoding="utf-8").strip()


@web.middleware
async def authenticate(request, handler):
    if request.path != "/health" and not KEY_PATH.exists():
        raise web.HTTPServiceUnavailable(reason="Configure the Fish integration first")
    if request.path != "/health" and not secrets.compare_digest(
        request.headers.get("X-Bridge-Key", ""), key()
    ):
        raise web.HTTPForbidden()
    return await handler(request)


class CoreBridge:
    def __init__(self, app, bridge_id):
        self.app, self.bridge_id = app, bridge_id
        self.hass = SimpleNamespace(async_create_task=asyncio.create_task)

    async def tool(self, name, params, context, device_id):
        async with self.app["http"].post(
            "http://supervisor/core/api/fish_live3/worker-tool",
            headers={"Authorization": "Bearer " + os.environ["SUPERVISOR_TOKEN"]},
            json={"bridge_key": key(), "bridge_id": self.bridge_id, "name": name, "params": params},
            timeout=ClientTimeout(total=30),
        ) as response:
            if response.status != 200:
                logging.warning("Home Assistant tool callback HTTP status: %s", response.status)
                raise RuntimeError("Home Assistant rejected the tool call")
            return await response.json()

    async def end_upstream(self, fish_id):
        return None


async def turn(request):
    body = await request.json()
    bridge_id, text = body.get("bridge_id", ""), body.get("text", "")
    if (
        not isinstance(bridge_id, str)
        or not 20 <= len(bridge_id) <= 100
        or not isinstance(text, str)
        or not 1 <= len(text) <= 10000
    ):
        raise web.HTTPBadRequest()
    for old_id, old in list(ROOMS.items()):
        if time.monotonic() - old.last_used > 360 and not old.lock.locked():
            ROOMS.pop(old_id, None)
            await old.close()
    session = ROOMS.get(bridge_id)
    if session is None:
        if len(ROOMS) >= 8:
            raise web.HTTPTooManyRequests()
        session = ROOMS[bridge_id] = WorkerTurn(CoreBridge(request.app, bridge_id), body["token"])
    try:
        text, wav = await session.reply(text)
        return web.json_response({"text": text, "audio": base64.b64encode(wav).decode()})
    except Exception:
        ROOMS.pop(bridge_id, None)
        await session.close()
        return web.json_response({"error": "Fish realtime conversation failed"}, status=502)


async def close(request):
    body = await request.json()
    session = ROOMS.pop(body.get("bridge_id"), None)
    if session:
        await session.close()
    return web.json_response({})


async def lifespan(app):
    app["http"] = ClientSession()
    registration = asyncio.create_task(register_worker(app))
    yield
    registration.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await registration
    await asyncio.gather(*(room.close() for room in ROOMS.values()), return_exceptions=True)
    await app["http"].close()


async def register_worker(app):
    """Announce the actual Supervisor hostname after startup and Core restarts."""
    while True:
        try:
            if KEY_PATH.exists() and os.environ.get("SUPERVISOR_TOKEN"):
                headers = {"Authorization": "Bearer " + os.environ["SUPERVISOR_TOKEN"]}
                async with app["http"].get(
                    "http://supervisor/addons/self/info",
                    headers=headers,
                    timeout=ClientTimeout(total=10),
                ) as response:
                    info = await response.json() if response.status == 200 else {}
                hostname = info.get("data", {}).get("hostname")
                if hostname:
                    async with app["http"].post(
                        "http://supervisor/core/api/fish_live3/worker-register",
                        headers=headers,
                        json={"bridge_key": key(), "worker_url": f"http://{hostname}:8789"},
                        timeout=ClientTimeout(total=10),
                    ) as response:
                        await response.read()
        except (ClientError, OSError, ValueError, TimeoutError):
            pass
        await asyncio.sleep(30)


app = web.Application(middlewares=[authenticate], client_max_size=100000)
app.cleanup_ctx.append(lifespan)


async def health(request):
    return web.json_response({"ready": KEY_PATH.exists()})


app.router.add_get("/health", health)
app.router.add_post("/turn", turn)
app.router.add_post("/close", close)
if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8789, access_log=None)
