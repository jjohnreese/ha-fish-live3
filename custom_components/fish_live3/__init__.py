"""A separate Fish assistant, live dashboard and satellite compatibility agent."""

from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path

from homeassistant.components import websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

from .api import FishError
from .bridge import Bridge
from .const import DEFAULT_PERSONALITY, DOMAIN, PLATFORMS, VOICES
from .schema import vol
from .worker_api import WorkerRegisterView, WorkerToolView, load_key

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN + "_worker_key"] = await hass.async_add_executor_job(
        load_key, hass.config.config_dir
    )
    hass.http.register_view(WorkerToolView())
    hass.http.register_view(WorkerRegisterView())
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                "/fish_live3/house-talk.js",
                str(Path(__file__).parent / "www" / "house-talk.js"),
                False,
            )
        ]
    )
    for command in (ws_status, ws_session, ws_tool, ws_end):
        websocket_api.async_register_command(hass, command)
    return True


async def async_setup_entry(hass, entry):
    bridge = Bridge(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = bridge
    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, lambda event: hass.async_create_task(bridge.close())
        )
    )

    async def cleanup(now):
        await bridge.cleanup_idle()

    entry.async_on_unload(async_track_time_interval(hass, cleanup, timedelta(seconds=30)))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        bridge = hass.data[DOMAIN].pop(entry.entry_id)
        await bridge.close()
        return True
    return False


def get_bridge(hass):
    bridges = hass.data.get(DOMAIN, {})
    if not bridges:
        raise HomeAssistantError(
            "Add Fish Live3 under Settings > Devices & services, and enter your Fish API key"
        )
    return next(iter(bridges.values()))


@websocket_api.websocket_command({vol.Required("type"): "fish_live3/status"})
@callback
def ws_status(hass, connection, msg):
    bridges = hass.data.get(DOMAIN, {})
    bridge = next(iter(bridges.values()), None)
    connection.send_result(
        msg["id"],
        {
            "configured": bridge is not None,
            "name": bridge.entry.title if bridge else "Fish Live3",
            "voice": bridge.entry.data["voice"] if bridge else "Clara",
            "published": bool(bridge and bridge.entry.data.get("published")),
            "satellite_mode": "turn_based",
            "live_language": "en",
            "voices": VOICES,
            "supports_preferences": True,
            "default_personality": DEFAULT_PERSONALITY,
            "satellite_worker_ready": time.monotonic()
            - hass.data.get(DOMAIN + "_worker_seen", float("-inf"))
            < 120,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fish_live3/session",
        vol.Optional("voice"): str,
        vol.Optional("personality"): str,
    }
)
@websocket_api.async_response
async def ws_session(hass, connection, msg):
    try:
        result = await get_bridge(hass).create_browser(
            connection.user.id, connection.context(msg), msg.get("voice"), msg.get("personality")
        )
        connection.send_result(msg["id"], result)
    except (FishError, HomeAssistantError) as error:
        connection.send_error(msg["id"], "fish_error", str(error))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fish_live3/tool",
        vol.Required("bridge_id"): str,
        vol.Required("name"): str,
        vol.Required("params"): dict,
    }
)
@websocket_api.async_response
async def ws_tool(hass, connection, msg):
    try:
        bridge = get_bridge(hass)
        session = bridge.browser(msg["bridge_id"], connection.user.id)
        result = await bridge.tool(msg["name"], msg["params"], session.context)
        connection.send_result(msg["id"], result)
    except (HomeAssistantError, ValueError) as error:
        connection.send_error(msg["id"], "home_error", str(error))


@websocket_api.websocket_command(
    {vol.Required("type"): "fish_live3/end", vol.Required("bridge_id"): str}
)
@websocket_api.async_response
async def ws_end(hass, connection, msg):
    try:
        await get_bridge(hass).end_browser(msg["bridge_id"], connection.user.id)
        connection.send_result(msg["id"], {})
    except (FishError, HomeAssistantError) as error:
        connection.send_error(msg["id"], "fish_error", str(error))
