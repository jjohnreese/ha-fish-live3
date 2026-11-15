"""Offline contract tests. No household action or Fish call is performed."""

import asyncio
import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components/fish_live3"


def module(name, **attrs):
    entry = types.ModuleType(name)
    entry.__dict__.update(attrs)
    entry.__path__ = []
    sys.modules[name] = entry
    return entry


module("custom_components")
module("custom_components.fish_live3").__path__ = [str(COMPONENT)]
from custom_components.fish_live3.api import FishClient, FishError
from custom_components.fish_live3.const import TOOL_DEFINITIONS
from custom_components.fish_live3.end_request import is_end_request


def test_natural_conversation_closings():
    for text in [
        "Thank you, Jarvis",
        "That's it. Thank you.",
        "Thank you, that would be all",
        "Okay Jarvis that's all for now",
        "Please end this conversation now",
    ]:
        assert is_end_request(text), text
    for text in [
        "Thank you",
        "don't stop listening",
        "thank you Jarvis turn on the light",
        "nothing else is on",
    ]:
        assert not is_end_request(text), text


def test_session_prompt_preserves_home_rules():
    async def run():
        client = FishClient(None, "fake")
        client.request = AsyncMock(return_value={})
        await client.create_session("owned-agent", "UTC", "Be concise and witty")
        payload = client.request.call_args.args[2]
        assert payload["record_audio"] is False
        assert "Be concise and witty" in payload["overrides"]["system_prompt"]
        assert (
            "Never operate devices without a user request" in payload["overrides"]["system_prompt"]
        )

    asyncio.run(run())


def test_provision_resumes_owned_resources_without_duplicates():
    async def run():
        saved = {}

        async def progress(value):
            if value:
                saved.update(value)
            return dict(saved)

        client = FishClient(None, "fake-secret")
        calls = []
        failed = False

        async def request(method, path, payload):
            nonlocal failed
            calls.append((method, path, payload))
            if path == "/v1/agent/tools":
                return {"tool_id": "tool-" + str(len(saved.get("tool_ids", [])))}
            if path == "/v1/agent/agents":
                return {"agent_id": "agent-one"}
            if path.endswith("/publish") and not failed:
                failed = True
                raise FishError(503)
            return {}

        client.request = request
        with pytest.raises(FishError):
            await client.provision("House Talk", "Clara", "Asia/Jerusalem", progress)
        assert saved["agent_id"] == "agent-one" and len(saved["tool_ids"]) == 2
        await client.provision("House Talk", "Clara", "Asia/Jerusalem", progress)
        assert sum(path == "/v1/agent/agents" for _, path, _ in calls) == 1
        assert sum(path == "/v1/agent/tools" for _, path, _ in calls) == 2
        assert saved["published"]
        config = next(payload for _, path, payload in calls if path.endswith("/config"))
        assert config["voice"]["engine"] == "live3"
        assert config["tools"]["system_tools"]["hang_up_call"] is False
        assert config["conversation"]["record_audio"] is False

    asyncio.run(run())


def test_errors_never_contain_a_key_or_upstream_payload():
    for status in (401, 402, 403, 409, 429, 500):
        assert "secret" not in str(FishError(status)).lower()


def test_tool_and_agent_payloads_match_published_api_shape():
    spec = json.loads((ROOT / "tests/fixtures/fish-tool-schema.json").read_text(encoding="utf-8"))
    allowed = spec["components"]["schemas"]["PublicAgentToolCreatePayload"]["properties"]
    assert all(set(tool) <= set(allowed) for tool in TOOL_DEFINITIONS)
    assert [tool["name"] for tool in TOOL_DEFINITIONS] == ["get_home_context", "home_assistant"]


class HAError(Exception):
    pass


def install_ha_stubs():
    module("homeassistant")
    module("homeassistant.components")
    module("homeassistant.components.conversation", async_converse=AsyncMock())
    module("homeassistant.components.homeassistant")
    module(
        "homeassistant.components.homeassistant.exposed_entities",
        async_should_expose=lambda h, a, e: e != "sensor.hidden",
    )
    module("homeassistant.auth")
    module("homeassistant.auth.permissions")
    module("homeassistant.auth.permissions.const", POLICY_READ="read")
    module("homeassistant.core", Context=lambda **kw: types.SimpleNamespace(**kw))
    module("homeassistant.exceptions", HomeAssistantError=HAError)
    module("homeassistant.helpers")
    for name in ("area_registry", "device_registry", "entity_registry"):
        module(
            "homeassistant.helpers." + name,
            async_get=lambda h: types.SimpleNamespace(
                async_get=lambda _: None, async_get_area=lambda _: None
            ),
        )
    module("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda h: None)


install_ha_stubs()
from custom_components.fish_live3.bridge import Bridge, BrowserSession
from custom_components.fish_live3.const import CONFIG_REVISION


def test_voice_cache_does_not_change_the_default_agent():
    async def run():
        entry = types.SimpleNamespace(
            data={
                "api_key": "fixture",
                "voice": "Clara",
                "name": "HouseTalk",
                "agent_id": "base-agent",
                "published": True,
                "published_voice": "Clara",
                "config_revision": CONFIG_REVISION,
                "tool_ids": ["one", "two"],
            }
        )

        def update(entry, data):
            entry.data = data

        hass = types.SimpleNamespace(
            config=types.SimpleNamespace(time_zone="UTC"),
            config_entries=types.SimpleNamespace(async_update_entry=update),
        )
        item = Bridge(hass, entry)

        async def provision(name, voice, timezone, save):
            await save(
                {"agent_id": "nora-agent", "published": True, "config_revision": CONFIG_REVISION}
            )
            return await save(None)

        item.client.provision = AsyncMock(side_effect=provision)
        assert await item.ensure_agent("Nora") == "nora-agent"
        assert await item.ensure_agent("Nora") == "nora-agent"
        assert await item.ensure_agent() == "base-agent"
        assert item.client.provision.call_count == 1
        assert entry.data["voice"] == "Clara" and entry.data["agent_id"] == "base-agent"

    asyncio.run(run())


def test_invalid_voice_and_oversized_personality_never_create_a_session():
    async def run():
        item = bridge()
        item.client.create_session = AsyncMock()
        for voice, personality in [("unlisted", None), (None, "x" * 8001)]:
            with pytest.raises(HAError):
                await item.create_browser("user", None, voice, personality)
        item.client.create_session.assert_not_awaited()

    asyncio.run(run())


def bridge():
    entry = types.SimpleNamespace(data={"api_key": "not-a-real-key"})
    return Bridge(types.SimpleNamespace(), entry)


def test_session_cannot_be_used_by_another_user_or_after_expiry():
    item = bridge()
    item.sessions["one"] = BrowserSession("owner", "fish-one", None, float("inf"))
    assert item.browser("one", "owner").fish_id == "fish-one"
    with pytest.raises(HAError):
        item.browser("one", "other")
    item.sessions["one"].expires = 0
    with pytest.raises(HAError):
        item.browser("one", "owner")


def test_ending_revokes_local_control_even_if_upstream_end_fails():
    async def run():
        item = bridge()
        item.sessions["one"] = BrowserSession("owner", "fish-one", None, float("inf"))
        item.end_upstream = AsyncMock(side_effect=FishError(503))
        with pytest.raises(FishError):
            await item.end_browser("one", "owner")
        assert "one" not in item.sessions

    asyncio.run(run())


def test_bridge_rejects_arbitrary_services_and_invalid_parameters():
    async def run():
        item = bridge()
        for name, params in (
            ("call_service", {"domain": "lock"}),
            ("home_assistant", {"request": "x", "service": "restart"}),
            ("home_assistant", {"request": ""}),
            ("get_home_context", {"all": True}),
        ):
            with pytest.raises(HAError):
                await item.tool(name, params, None)

    asyncio.run(run())


def test_context_respects_both_exposure_and_user_read_permission():
    async def run():
        item = bridge()
        user = types.SimpleNamespace(
            is_active=True,
            permissions=types.SimpleNamespace(
                check_entity=lambda entity, policy: entity != "sensor.denied"
            ),
        )
        item.hass.auth = types.SimpleNamespace(async_get_user=AsyncMock(return_value=user))
        item.hass.states = types.SimpleNamespace(
            async_all=lambda: [
                types.SimpleNamespace(
                    entity_id=entity,
                    name=entity,
                    state="on",
                    attributes={"latitude": 123, "access_token": "SECRET", "brightness": 40},
                )
                for entity in ("light.exposed", "sensor.hidden", "sensor.denied")
            ]
        )
        result = await item.context(types.SimpleNamespace(user_id="owner"))
        assert [row["entity_id"] for row in result["devices"]] == ["light.exposed"]
        assert "SECRET" not in json.dumps(result) and "latitude" not in json.dumps(result)

    asyncio.run(run())


def test_audio_cache_is_bounded_and_expires():
    item = bridge()
    for i in range(30):
        item.cache_audio(str(i), b"RIFF")
    assert len(item.audio) == 24 and item.get_audio("29") == b"RIFF"
    item.audio["29"] = (0, b"RIFF")
    assert item.get_audio("29") is None


def test_home_requests_use_only_the_builtin_assist_agent():
    async def run():
        native = sys.modules["homeassistant.components.conversation"].async_converse
        native.reset_mock()
        native.return_value = types.SimpleNamespace(
            as_dict=lambda: {"response": {"speech": "No lights are on"}}
        )
        item = bridge()
        context = types.SimpleNamespace(user_id="owner")
        result = await item.tool("home_assistant", {"request": "Which lights are on?"}, context)
        assert native.call_args.kwargs["agent_id"] == "conversation.home_assistant"
        assert native.call_args.kwargs["conversation_id"] is None
        assert native.call_args.kwargs["context"] is context
        assert "response" in result

    asyncio.run(run())
