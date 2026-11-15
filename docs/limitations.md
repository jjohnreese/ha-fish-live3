# Current limits

- Community beta; independent of Fish Audio, Home Assistant and the Marketplace/HACS catalog.
- Personal project provided as is, without warranty, guaranteed support or maintenance. See the [disclaimer](../DISCLAIMER.md).
- Fish account, Agent credit and internet access required. Prices and provider limits can change; check your Fish account.
- Live3 speaks English. The integration's conversational tool requests use English.
- A 60-minute provider session cap is configured. Client inactivity timeouts may end calls sooner.
- The satellite bridge needs HA OS/Supervised, an existing STT provider and compatible satellite firmware. Physical follow-up behavior is not certified for all devices.
- Stock satellites take turns. Full-duplex interruption is for the live Windows/dashboard transport.
- Browser microphones require a secure context such as HTTPS. This project does not change your HA network security or certificates.
- Windows release target: Windows 10/11 x64. WebView2 and an English Windows recognizer for the optional local wake phrase are separate prerequisites.
- Personality prompts can reduce narration but cannot guarantee that Live3 never acknowledges a request before a tool finishes.
- Selecting another stock Live3 voice may provision an additional private Fish agent. Voice selection applies to the next call.
- The reply TTS entity replays recent Fish conversation audio; it is not an arbitrary-text TTS service.
- Household actions depend on HA Assist exposure, permissions, language support and disambiguation. Always check the actual outcome for consequential actions.
