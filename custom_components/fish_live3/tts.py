"""Replay the actual Live3 reply audio for a satellite's TTS stage."""

from homeassistant.components.tts import TextToSpeechEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([FishReplyVoice(entry)])


class FishReplyVoice(TextToSpeechEntity):
    _attr_name = "Fish Live3 Reply Voice"
    _attr_default_language = "en"
    _attr_supported_languages = ["en"]

    def __init__(self, entry):
        self.entry = entry
        self._attr_unique_id = entry.entry_id + "_reply_voice"

    async def async_get_tts_audio(self, message, language, options=None):
        bridge = self.hass.data[DOMAIN][self.entry.entry_id]
        if audio := bridge.get_audio(message):
            return "wav", audio
        raise HomeAssistantError(
            "This voice replays replies from the Fish Live3 conversation agent. Select both Fish Live3 and Fish Live3 Reply Voice in its separate pipeline."
        )
