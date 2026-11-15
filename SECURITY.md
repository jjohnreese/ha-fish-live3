# Security and privacy

## Credentials and trust boundaries

- The Fish API key is entered in HA's integration setup and stored in HA's config entry. HA config entries are not a standalone encrypted secrets vault; protect HA configuration and backups.
- Windows uses HA OAuth with PKCE and a loopback callback. Its refresh token and preferences are protected with Windows DPAPI for the current user. No Fish key is stored in Windows or dashboard YAML.
- A generated worker bridge key lives in `fish_live3_worker_secret` in the HA configuration directory. It is not a Fish key. It must never be committed or attached to an issue.
- Live clients receive short-lived Fish session tokens. Home-tool bridge IDs are random, user-scoped and expire. Ending a call revokes local tool access before waiting for the provider's response.
- Only the two scoped tools are exposed: read Assist-exposed context and send a natural-language request to HA's built-in Assist agent. The bridge does not expose a generic service-call API.

## What leaves the home

Fish is a cloud service. Live-call audio, recognized/typed messages, responses and relevant Assist-exposed device names/areas/states may be sent to Fish. The project asks Fish not to record session audio, but this does not override Fish's account policies, transcript storage or provider retention terms. Consult your Fish account and policy before using sensitive content.

The local Windows wake recognizer runs on the PC while enabled. It pauses during Fish calls. Ending the cloud call does not disable that local listener; disabling the wake word, disabling HouseTalk or exiting the app does.

## Worker privileges

The optional worker app has `homeassistant_api: true` so it can call its scoped callback through the Supervisor. It mounts HA configuration read-only to read its generated bridge key. This permission/mount is sensitive: only install worker code you trust. The worker has no published LAN port, validates its private key, and registers only a constrained internal Supervisor hostname. Do not expose it publicly or weaken HA authentication.

The native LiveKit library runs in a Debian worker because it is incompatible with HA Core's Alpine runtime. Python/SDK dependencies are pinned. The worker never needs the Fish API key.

## Sharing and releases

Never share runtime `Data`/WebView folders, DPAPI files, `.storage`, `secrets.yaml`, private keys, logs containing tokens, home transcripts or audio. Releases are built from source in clean CI and scanned before publication. This cannot replace review of future contributions.

## Vulnerability reports

Use GitHub's private vulnerability reporting if available, or contact the repository owner privately through GitHub. Do not include a working token in a public issue. If a credential is exposed, revoke/rotate it at the service that issued it; deleting a commit alone is insufficient.
