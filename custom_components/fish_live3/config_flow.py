"""UI configuration; the Fish key is never placed in dashboard YAML."""

from __future__ import annotations

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import FishClient, FishError
from .const import DOMAIN, NAME, VOICES
from .schema import vol


def schema(defaults=None, updating=False):
    defaults = defaults or {}
    return vol.Schema(
        {
            (vol.Optional if updating else vol.Required)(
                getattr(vol, "Secret", lambda key: key)(CONF_API_KEY)
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, NAME)): str,
            vol.Required("voice", default=defaults.get("voice", "Clara")): SelectSelector(
                SelectSelectorConfig(options=VOICES)
            ),
        }
    )


class FishFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors = {}
        if user_input is not None:
            user_input[CONF_API_KEY] = user_input[CONF_API_KEY].strip()
            try:
                await FishClient(
                    async_get_clientsession(self.hass), user_input[CONF_API_KEY]
                ).validate()
            except FishError as error:
                errors["base"] = "invalid_auth" if error.status in (401, 403) else "cannot_connect"
            else:
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
        return self.async_show_form(step_id="user", data_schema=schema(), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return FishOptions()


class FishOptions(OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            user_input[CONF_API_KEY] = (
                user_input.get(CONF_API_KEY) or ""
            ).strip() or self.config_entry.data[CONF_API_KEY]
            try:
                await FishClient(
                    async_get_clientsession(self.hass), user_input[CONF_API_KEY]
                ).validate()
            except FishError as error:
                errors["base"] = "invalid_auth" if error.status in (401, 403) else "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={**self.config_entry.data, **user_input}
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.config_entry.entry_id)
                )
                return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="init", data_schema=schema(self.config_entry.data, updating=True), errors=errors
        )
