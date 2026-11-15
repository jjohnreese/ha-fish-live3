"""A pure-Python Core client for the separate Debian voice-transport App."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import secrets
import time

from aiohttp import ClientTimeout

from .const import DOMAIN

WORKER = "http://local-fish-live3-worker:8789"


class SatelliteTurn:
    def __init__(self, bridge, context, device_id):
        self.bridge, self.context, self.device_id = bridge, context, device_id
        self.bridge_id = secrets.token_urlsafe(32)
        self.token = None
        self.lock = asyncio.Lock()
        self.last_used = time.monotonic()
        self.pending = False

    async def request(self, path, data):
        key = self.bridge.hass.data[DOMAIN + "_worker_key"]
        worker = self.bridge.hass.data.get(DOMAIN + "_worker_url", WORKER)
        async with self.bridge.client.session.post(
            worker + path,
            json=data,
            headers={"X-Bridge-Key": key},
            timeout=ClientTimeout(total=110),
        ) as response:
            if response.status != 200:
                raise RuntimeError("The Fish Live3 satellite worker is unavailable")
            return await response.json()

    async def reply(self, text):
        async with self.lock:
            if self.token is None:
                agent = await self.bridge.ensure_agent()
                self.token = await self.bridge.client.create_session(
                    agent, self.bridge.hass.config.time_zone
                )
            self.last_used = time.monotonic()
            self.pending = True
            try:
                result = await self.request(
                    "/turn", {"bridge_id": self.bridge_id, "token": self.token, "text": text}
                )
                audio = base64.b64decode(result["audio"], validate=True)
                if not audio.startswith(b"RIFF"):
                    raise RuntimeError("Worker returned invalid voice audio")
                self.bridge.cache_audio(result["text"], audio)
                return result["text"]
            except Exception:
                await self.close()
                raise
            finally:
                self.pending = False
                self.last_used = time.monotonic()

    async def close(self):
        self.pending = False
        with contextlib.suppress(Exception):
            await self.request("/close", {"bridge_id": self.bridge_id})
        if self.token:
            token, self.token = self.token, None
            with contextlib.suppress(Exception):
                await self.bridge.end_upstream(token["session_id"])
