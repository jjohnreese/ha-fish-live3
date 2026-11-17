# Changelog

## 0.5.0

First full, non-prerelease community release, available without opting into beta versions in HACS/Marketplace.

- Release the existing beta feature set with matching 0.5.0 versions for the integration, satellite worker and Windows app.
- Update installation instructions for the regular release and include the clean interface screenshot documentation.
- No feature behavior changes from 0.5.0 beta 1. Existing privacy notices, personal-project disclaimer and known satellite limitations still apply.

The Windows ZIP includes its installer, quick start and dependency licenses. Save your own Fish API key only in Home Assistant; the app never needs it. See the [setup guide](https://github.com/jjohnreese/ha-fish-live3#install-in-home-assistant), [pricing estimates](https://github.com/jjohnreese/ha-fish-live3/blob/main/docs/pricing.md) and [disclaimer](https://github.com/jjohnreese/ha-fish-live3/blob/main/DISCLAIMER.md).

## 0.5.0 beta 1

First public community beta.

- Home Assistant conversation integration, authenticated browser bridge and actual Fish reply-voice TTS.
- Separate private satellite worker with registration independent of repository hostname hashes.
- Live dashboard card with hands-free, push-to-talk, transcript, typed turns and explicit End.
- Windows tray app, local wake word, run-on-login option and DPAPI-protected persistent settings.
- Explicit Unmute fixes the push-to-talk waiting-state confusion and supports retry after denied capture.
- Per-client voice/personality selection and a Jarvis-inspired default.
- Configurable inactivity end plus natural closing phrases, including thanks with the configured wake name.
- Installation examples, privacy documentation, tests and clean CI-built Windows release packaging.
- Dated API cost estimates with per-call/monthly examples and a prominent independent-project disclaimer.

Stock satellite full-duplex audio and universal firmware follow-up support are not included. See known limitations.
