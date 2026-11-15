"""A new conversation entity; never changes an existing pipeline."""

from __future__ import annotations

import time

from homeassistant.components import conversation
from homeassistant.helpers import intent
from homeassistant.util.ulid import ulid_now

from .const import DOMAIN
from .end_request import is_end_request
from .satellite import SatelliteTurn


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([FishConversation(entry)])


class FishConversation(conversation.ConversationEntity):
    _attr_name = "Fish Live3"
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(self, entry):
        self.entry = entry
        self._attr_unique_id = entry.entry_id + "_conversation"

    @property
    def supported_languages(self):
        return ["en"]

    async def async_process(self, user_input):
        bridge = self.hass.data[DOMAIN][self.entry.entry_id]
        conversation_id = user_input.conversation_id or ulid_now()
        key = (conversation_id, user_input.context.user_id, user_input.device_id)
        for old_key, old_turn in list(bridge.turns.items()):
            if time.monotonic() - old_turn.last_used > 300 and not old_turn.lock.locked():
                bridge.turns.pop(old_key, None)
                await old_turn.close()
        response = intent.IntentResponse(language="en")
        finish = is_end_request(user_input.text)
        try:
            turn = bridge.turns.get(key)
            if turn is None:
                if len(bridge.turns) >= 8:
                    raise RuntimeError("Too many conversations")
                turn = bridge.turns[key] = SatelliteTurn(
                    bridge, user_input.context, user_input.device_id
                )
            text = await turn.reply(user_input.text)
            response.async_set_speech(text)
            if finish:
                bridge.turns.pop(key, None)
                await turn.close()
            return conversation.ConversationResult(
                response=response, conversation_id=conversation_id, continue_conversation=not finish
            )
        except Exception:
            if turn := bridge.turns.pop(key, None):
                await turn.close()
            response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                "I couldn't connect to Fish Live3. Check the integration and Fish Agent credit.",
            )
            return conversation.ConversationResult(
                response=response, conversation_id=conversation_id
            )
