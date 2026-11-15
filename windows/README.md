# HouseTalk for Windows - quick start

Unofficial personal project, unaffiliated with Fish Audio or Home Assistant. Provided as is without warranty or guaranteed support. See DISCLAIMER.md and LICENSE in this folder. You are responsible for your API account and charges.

1. Install the Fish Live3 integration in your own Home Assistant and save your own Fish API key there. The Windows app does not need the key.
2. Extract this entire ZIP. Close any existing HouseTalk process from its tray menu before upgrading.
3. Run `Install.ps1` in PowerShell if local scripts are permitted, or run `HouseTalk.exe` directly from the extracted folder. Installation is per user and needs no administrator rights. Microsoft Edge WebView2 must be installed.
4. Open HouseTalk Settings, enter your Home Assistant address and select **Connect Home Assistant**. Complete sign-in in your browser.
5. Choose Hands-free or Push-to-talk, start a conversation and approve the microphone prompt yourself.

The installer copies the app to `%LOCALAPPDATA%\Programs\HouseTalk` and adds a Start-menu shortcut. Right-click that shortcut to pin it to Start. Sign-in and preferences are saved separately under `%LOCALAPPDATA%\HouseTalk` and protected with Windows DPAPI. Never share that settings directory.

The tray menu includes enable/disable, wake word, voice, personality, microphone mode, inactivity timeout and optional **Run on Windows login**. Closing the window ends the call and leaves the tray app running. **Exit HouseTalk** stops it entirely. The optional local wake phrase needs Windows English speech recognition.

End calls with the **End** button, "stop listening", "that's it, thank you", or "thank you" followed by your configured wake name. The default inactivity timeout is 30 seconds, pausing while the assistant thinks or speaks. Muting does not end a connected cloud call. Fish usage may cost money while the session remains connected.

For uninstalling, exit HouseTalk and run `Uninstall.ps1`. It retains settings unless you explicitly pass `-RemoveSettings`.

- [Home Assistant and dashboard setup](https://github.com/jjohnreese/ha-fish-live3/blob/main/docs/home-assistant.md)
- [Full Windows guide](https://github.com/jjohnreese/ha-fish-live3/blob/main/docs/windows.md)
- [API cost examples](https://github.com/jjohnreese/ha-fish-live3/blob/main/docs/pricing.md)
- [Privacy and security](https://github.com/jjohnreese/ha-fish-live3/blob/main/SECURITY.md)
- [Troubleshooting and bug reports](https://github.com/jjohnreese/ha-fish-live3/issues)
- [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)
