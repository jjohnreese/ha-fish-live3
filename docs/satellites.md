# Stock voice satellites

This optional mode bridges standard Assist turns to Fish Live3. It is different from the live Windows/dashboard transport.

## Worker app

1. On HA OS/Supervised, add this repository to the App Store repositories.
2. Install **Fish Live3 Satellite Worker**, enable start on boot and start it.
3. Configure the Fish integration if you have not already done so. The integration generates a private worker bridge key in the HA configuration directory.
4. Allow up to 30 seconds for the worker to register its actual Supervisor hostname. No repository hash or LAN port needs to be entered.

The worker uses a Debian container because its native LiveKit library does not run in HA Core's Alpine environment. It has no published LAN port. Its Supervisor API permission and read-only configuration mount are described in `SECURITY.md`.

## Create a separate assistant pipeline

Create a new pipeline in **Settings → Voice assistants**. Choose:

| Stage | Selection |
| --- | --- |
| Language | English |
| Conversation | Fish Live3 |
| Speech-to-text | Your already working English STT provider |
| Text-to-speech | Fish Live3 Reply Voice |
| Wake word | A wake-word provider/model already supported by your satellite |
| Prefer handling commands locally | Off, if you want Fish to receive the conversational turn |

Do not change an existing pipeline just to try this. Record the satellite's current assistant selection, select the new pipeline for a test, and restore the previous selection if needed.

## Conversation behavior

The agent preserves context when the satellite preserves the conversation ID and requests follow-up listening with `continue_conversation`. Your device's firmware decides how it listens again and when its own listening window ends. You may still need another wake word after a device timeout.

Speech is transcribed by your chosen STT, sent to Fish, then the actual Fish response is played through the matching reply-voice TTS stage. Do not use Fish Live3 Reply Voice as a general TTS engine: it only replays recent responses from its conversation agent.

Stock satellites do not gain simultaneous listening during playback or full-duplex interruption. The Windows/dashboard 30-second inactivity control is a client feature, not a firmware change to satellites. Abandoned satellite cloud sessions are cleaned up after five minutes of inactivity.

“Goodbye,” “stop listening,” “that would be all,” and “thank you, Jarvis” end this compatibility conversation. A physical satellite follow-up test is still needed for each supported firmware/device combination. No firmware is modified by this repository.
