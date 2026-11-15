"""Fish REST client. Credentials stay in Home Assistant."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import API_BASE, CONFIG_REVISION, HOME_RULES, SYSTEM_PROMPT, TOOL_DEFINITIONS


class FishError(Exception):
    """Sanitized upstream error; never includes the key or raw response."""

    def __init__(self, status: int):
        self.status = status
        messages = {
            401: "Fish rejected the API key",
            403: "Fish denied access",
            402: "Fish Agent credit is required",
            409: "The Fish agent needs publishing",
            429: "Fish rate limit reached",
        }
        super().__init__(messages.get(status, f"Fish API request failed (HTTP {status})"))


class FishClient:
    def __init__(self, session: ClientSession, key: str):
        self.session, self.key = session, key

    async def request(self, method: str, path: str, payload: dict | None = None) -> Any:
        try:
            async with self.session.request(
                method,
                API_BASE + path,
                json=payload,
                headers={"Authorization": f"Bearer {self.key}"},
                timeout=ClientTimeout(total=30),
                allow_redirects=False,
            ) as response:
                if response.status >= 300:
                    await response.read()
                    raise FishError(response.status)
                if response.status == 204:
                    return {}
                body = await response.read()
                if not body:
                    return {}
                import json

                return json.loads(body)
        except (ClientError, TimeoutError, ValueError) as error:
            raise FishError(503) from error

    async def validate(self) -> None:
        await self.request("GET", "/v1/agent/agents?limit=1")

    async def provision(self, name: str, voice: str, timezone: str, save_progress) -> dict:
        """Create only resources owned by this entry, checkpointing every ID."""
        progress = dict(await save_progress(None))
        tool_ids = list(progress.get("tool_ids", []))
        for definition in TOOL_DEFINITIONS[len(tool_ids) :]:
            tool = await self.request("POST", "/v1/agent/tools", definition)
            tool_ids.append(tool["tool_id"])
            progress["tool_ids"] = tool_ids
            await save_progress(progress)
        config = {
            "prompt": {"system_prompt": SYSTEM_PROMPT, "first_message_mode": "off"},
            "voice": {"engine": "live3", "live3_voice": voice, "speaking_language": "en"},
            "conversation": {
                "max_duration_seconds": 3600,
                "hangup_after_seconds": 3600,
                "record_audio": False,
                "reengage_enabled": False,
                "timezone": timezone,
                "interruptible": True,
            },
            "tools": {
                "enabled": True,
                "tool_ids": tool_ids,
                "system_tools": {"hang_up_call": False},
            },
            "context": {"current_time": True},
        }
        if not progress.get("agent_id"):
            agent = await self.request("POST", "/v1/agent/agents", {"name": name, "config": config})
            progress["agent_id"] = agent["agent_id"]
            await save_progress(progress)
        else:
            await self.request("PATCH", f"/v1/agent/agents/{progress['agent_id']}/config", config)
        await self.request(
            "PATCH",
            f"/v1/agent/agents/{progress['agent_id']}",
            {"overrides_allowed": ["system_prompt"]},
        )
        await self.request("POST", f"/v1/agent/agents/{progress['agent_id']}/publish", {})
        progress["voice"] = voice
        progress["published"] = True
        progress["config_revision"] = CONFIG_REVISION
        await save_progress(progress)
        return progress

    async def create_session(
        self, agent_id: str, timezone: str, personality: str | None = None
    ) -> dict:
        payload = {
            "agent_id": agent_id,
            "timezone": timezone,
            "record_audio": False,
            "tool_events": True,
        }
        if personality:
            payload["overrides"] = {"system_prompt": personality + "\n\n" + HOME_RULES}
        return await self.request("POST", "/v1/agent/sessions", payload)
