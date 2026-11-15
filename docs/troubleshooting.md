# Troubleshooting

## Start is disabled or login is lost

Open app Settings and connect to your own HA instance. Confirm the Fish integration is loaded in Devices & services. For an expired Fish key, replace it in HA, not in Windows. A newly loaded dashboard resource may need a browser reload.

## The microphone says muted

Start a conversation first. In push-to-talk, hold its button or Space. Unmute switches to hands-free so it actually opens the microphone. Approve the native permission prompt yourself. Capture failures restore a muted state, so another Unmute attempt can retry. Check the selected Windows input device and its privacy permission manually if no audio is captured.

## The dashboard says Unknown command

Confirm HA has restarted after installing the integration and the entry is loaded. Reload the browser after HA finishes starting. Do not change an existing pipeline or paste a key into the card to fix a stale frontend connection.

## Fish refuses a session

Check that the key can use Fish Agents and that Agent credit is available. API authentication, credit, rate-limit and connectivity errors are presented without including the key. Do not paste full credential-bearing HTTP responses into issues.

## Satellite worker unavailable

Install and start the worker app, then configure the Fish integration. Wait up to 30 seconds for registration. The private bridge key must be readable in the worker's read-only HA configuration mount. Do not publish the worker port to your LAN to work around discovery. Both components need matching versions.

## No follow-up listening on a satellite

Check the device's firmware and assistant selection. It must preserve conversation IDs and honor the follow-up listening request. Return to your old assistant if needed. Report model, firmware, HA version and whether the first turn/TTS worked; do not include transcripts or home entity lists by default.

## Tray app seems to have closed

Closing or minimizing hides it in the tray. Open it again from the Start shortcut; the existing instance is reused. Use Exit HouseTalk from the tray to stop it fully.

## Reporting a bug

Use the repository's bug template. Include component/version, install method and a short redacted error. Never attach `connection.dpapi`, the WebView profile, `.storage`, `secrets.yaml`, the worker bridge key, complete HA diagnostics, raw audio or private home transcripts.
