"""Local home tools and user-scoped browser sessions."""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FishClient
from .const import CONFIG_REVISION, VOICES


@dataclass
class BrowserSession:
    owner: str
    fish_id: str
    context: Context
    expires: float


class Bridge:
    def __init__(self, hass, entry):
        self.hass, self.entry = hass, entry
        self.client = FishClient(async_get_clientsession(hass), entry.data["api_key"])
        self.sessions: dict[str, BrowserSession] = {}
        self.turns: dict[str, Any] = {}
        self.audio: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
        self.provision_lock = asyncio.Lock()

    async def ensure_agent(self, voice=None):
        async with self.provision_lock:
            data = self.entry.data
            voice = voice or data["voice"]
            if voice not in VOICES:
                raise HomeAssistantError("Choose a supported Fish Live3 voice")
            if voice != data["voice"]:
                progress_data = dict(data.get("voice_agents", {}).get(voice, {}))
                if (
                    progress_data.get("agent_id")
                    and progress_data.get("published")
                    and progress_data.get("config_revision") == CONFIG_REVISION
                ):
                    return progress_data["agent_id"]
                progress_data.setdefault("tool_ids", list(data.get("tool_ids", [])))

                async def voice_progress(update):
                    if update is not None:
                        progress_data.update(update)
                        agents = {
                            **self.entry.data.get("voice_agents", {}),
                            voice: dict(progress_data),
                        }
                        self.hass.config_entries.async_update_entry(
                            self.entry, data={**self.entry.data, "voice_agents": agents}
                        )
                    return dict(progress_data)

                result = await self.client.provision(
                    data["name"] + " · " + voice, voice, self.hass.config.time_zone, voice_progress
                )
                return result["agent_id"]
            if (
                data.get("agent_id")
                and data.get("published")
                and data.get("published_voice") == data["voice"]
                and data.get("config_revision") == CONFIG_REVISION
            ):
                return data["agent_id"]

            async def progress(update):
                if update is not None:
                    values = dict(update)
                    if "voice" in values:
                        values["published_voice"] = values.pop("voice")
                    self.hass.config_entries.async_update_entry(
                        self.entry, data={**self.entry.data, **values}
                    )
                return dict(self.entry.data)

            result = await self.client.provision(
                data["name"], data["voice"], self.hass.config.time_zone, progress
            )
            return result["agent_id"]

    async def context(self, context: Context) -> dict:
        user = await self.hass.auth.async_get_user(context.user_id) if context.user_id else None
        if context.user_id and (not user or not user.is_active):
            raise HomeAssistantError("This Home Assistant user is not active")
        entities = er.async_get(self.hass)
        devices = dr.async_get(self.hass)
        areas = ar.async_get(self.hass)
        result = []
        for state in self.hass.states.async_all():
            if not async_should_expose(self.hass, "conversation", state.entity_id):
                continue
            if user and not user.permissions.check_entity(state.entity_id, POLICY_READ):
                continue
            row = entities.async_get(state.entity_id)
            area_id = row.area_id if row else None
            if (
                not area_id
                and row
                and row.device_id
                and (device := devices.async_get(row.device_id))
            ):
                area_id = device.area_id
            area = areas.async_get_area(area_id) if area_id else None
            attrs = {
                key: state.attributes[key]
                for key in (
                    "unit_of_measurement",
                    "device_class",
                    "brightness",
                    "temperature",
                    "current_temperature",
                    "hvac_modes",
                    "volume_level",
                    "percentage",
                    "position",
                    "supported_features",
                )
                if key in state.attributes
            }
            result.append(
                {
                    "name": state.name,
                    "entity_id": state.entity_id,
                    "state": state.state,
                    "area": area.name if area else None,
                    **attrs,
                }
            )
        total = len(result)
        # Fish's client-tool result uses a 64 KB data channel packet.
        while result and len(json.dumps(result).encode()) > 48000:
            result.pop()
        return {
            "devices": result,
            "count": len(result),
            "total_exposed": total,
            "partial": len(result) < total,
            "instructions": "Only exposed entities can be controlled. Use names and areas exactly as returned.",
        }

    async def tool(self, name: str, params: dict, context: Context, device_id=None):
        if name == "get_home_context":
            if params:
                raise HomeAssistantError("get_home_context accepts no parameters")
            return await self.context(context)
        if name != "home_assistant" or set(params) != {"request"}:
            raise HomeAssistantError("Unknown tool or invalid parameters")
        text = params["request"]
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
            raise HomeAssistantError("A clear home request is required")
        result = await conversation.async_converse(
            self.hass,
            text=text,
            conversation_id=None,
            context=context,
            language="en",
            agent_id="conversation.home_assistant",
            device_id=device_id,
        )
        return result.as_dict()

    async def create_browser(self, user_id, context, voice=None, personality=None):
        if voice is not None and voice not in VOICES:
            raise HomeAssistantError("Choose a supported Fish Live3 voice")
        if personality is not None and (
            not isinstance(personality, str) or len(personality) > 8000
        ):
            raise HomeAssistantError("Keep personality instructions under 8,000 characters")
        now = time.monotonic()
        for key, value in list(self.sessions.items()):
            if value.expires <= now:
                self.sessions.pop(key, None)
        if len(self.sessions) >= 8:
            raise HomeAssistantError("Too many live conversations; end an existing one first")
        agent_id = await self.ensure_agent(voice)
        token = await self.client.create_session(agent_id, self.hass.config.time_zone, personality)
        if token.get("transport") != "livekit":
            await self.end_upstream(token["session_id"])
            raise HomeAssistantError("Fish returned an unsupported voice transport")
        key = secrets.token_urlsafe(32)
        self.sessions[key] = BrowserSession(user_id, token["session_id"], context, now + 3660)
        return {
            "session_token": token,
            "bridge_id": key,
            "tools": ["get_home_context", "home_assistant"],
        }

    def browser(self, key, user_id):
        item = self.sessions.get(key)
        if not item or item.owner != user_id or item.expires < time.monotonic():
            raise HomeAssistantError("This voice session has ended or belongs to another user")
        return item

    async def end_upstream(self, session_id):
        await self.client.request("POST", f"/v1/agent/sessions/{session_id}/end", {})

    async def end_browser(self, key, user_id):
        item = self.browser(key, user_id)
        self.sessions.pop(key, None)  # Revoke local control before waiting for Fish.
        await self.end_upstream(item.fish_id)

    def cache_audio(self, text, wav):
        self.audio[text.strip()] = (time.monotonic(), wav)
        self.audio.move_to_end(text.strip())
        while len(self.audio) > 24:
            self.audio.popitem(last=False)

    def get_audio(self, text):
        item = self.audio.get(text.strip())
        return item[1] if item and time.monotonic() - item[0] < 180 else None

    async def close(self):
        sessions, self.sessions = self.sessions, {}
        await asyncio.gather(
            *(self.end_upstream(item.fish_id) for item in sessions.values()), return_exceptions=True
        )
        await asyncio.gather(
            *(turn.close() for turn in self.turns.values()), return_exceptions=True
        )
        self.turns.clear()

    async def cleanup_idle(self):
        """End abandoned cloud sessions even if no later request arrives."""
        now = time.monotonic()
        for key, turn in list(self.turns.items()):
            if not turn.lock.locked() and now - turn.last_used > 300:
                self.turns.pop(key, None)
                await turn.close()
        for key, session in list(self.sessions.items()):
            if session.expires <= now:
                self.sessions.pop(key, None)
                try:
                    await self.end_upstream(session.fish_id)
                except Exception:
                    pass
