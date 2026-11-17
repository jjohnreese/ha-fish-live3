# Home Assistant setup

## Requirements

- Home Assistant 2026.11.0 or later.
- A Fish Audio account with an API key that can use Agents and sufficient Agent credit.
- Outbound HTTPS and WebRTC connectivity to Fish's service.
- The built-in Marketplace, or permission to copy a custom integration and restart HA.

## Install

In **Settings → Marketplace**, select **Add from link** and add `https://github.com/jjohnreese/ha-fish-live3` as an Integration. Install it and follow its setup flow. A first Marketplace install on HA 2026.11 does not need a restart; updating an already loaded integration does. Manual installs copy only `custom_components/fish_live3` to your own `custom_components` directory and restart HA before adding the integration. The Marketplace is built in; do not install HACS separately on this version.

Add **Fish Live3** from Devices & services. Paste your API key into its password field. Never put it into dashboard YAML, a Windows config file, an automation example, or a GitHub issue.

Version 0.5.0 is a regular, non-prerelease release; leave the repository's **Pre-release** switch off for normal installation. A manual install of the release ZIP is also available. See Home Assistant's [release guide](https://contributors.home-assistant.io/marketplace/guides/releases/).

The integration adds a conversation entity and a reply-voice TTS entity. Creating an entry alone does not operate devices or change your preferred pipeline. Fish agents and tools are provisioned privately on the first call. Other voice choices may create additional private agents owned by this integration; this avoids changing another client's voice during a call.

Use the integration's Configure form to change the default satellite voice or replace its key. Leave the optional key field blank to keep the existing key. Windows and dashboard voice/personality selections apply to that client's next conversation, not to existing pipelines.

## Expose only the entities you want

Use HA's **Settings → Voice assistants → Expose** controls. The integration reads only Assist-exposed entities for home context, and checks the logged-in user's entity read permissions. Commands go through the built-in Assist agent using the original user context. Ambiguous or unsupported requests can still fail; only report an action as complete after HA confirms it.

## Add a live dashboard card

Register `/fish_live3/house-talk.js?v=0.5.0` as a **JavaScript module** resource in your dashboard resources. Create a new dashboard/view and add the example in `examples/dashboard.yaml` as a manual card. Reload the browser after adding a resource.

Use your instance's existing HTTPS address for microphone access. Plain LAN HTTP usually cannot use a browser microphone. The Windows app uses a secure local WebView origin and can connect to a LAN HA address.

## Remove

Remove the Fish integration, its own new pipeline/dashboard/resource and, if installed, the Fish satellite worker. Do not manually edit HA `.storage` files. Other pipelines are independent. Private Fish agents/tools created by this integration remain in your Fish account for manual review/removal; uninstall does not silently delete cloud resources.
