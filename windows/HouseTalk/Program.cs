using System.Diagnostics;
using System.Security.Cryptography;
using System.Speech.Recognition;
using System.Text;
using System.Text.Json.Nodes;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace HouseTalk;

static class Program
{
    const string InstanceName = "Local\\HouseTalk.73d428c0";
    [STAThread]
    static void Main(string[] args)
    {
        if (args.Contains("--settings-check"))
        {
            var current = Settings.Load();
            Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new
            {
                current.Enabled,
                current.WakeEnabled,
                current.WakePhrase,
                current.Voice,
                current.MicrophoneMode,
                current.IdleSeconds,
                RunOnLogin = StartupRegistration.IsEnabled,
                PersonalityCharacters = current.Personality.Length,
                HasLogin = !string.IsNullOrEmpty(current.RefreshToken)
            }));
            return;
        }
        if (args.Contains("--self-test"))
        {
            var data = Encoding.UTF8.GetBytes("HouseTalk DPAPI test");
            var encrypted = ProtectedData.Protect(data, null, DataProtectionScope.CurrentUser);
            if (!data.SequenceEqual(ProtectedData.Unprotect(encrypted, null, DataProtectionScope.CurrentUser)))
                throw new Exception("Credential protection failed.");
            var callbackOrigin = new Uri("http://127.0.0.1:12345/");
            if (!LoopbackLogin.TryParseCallback("GET /callback?state=test-state&code=sample%2Bcode HTTP/1.1", callbackOrigin, "test-state", out var code) || code != "sample+code")
                throw new Exception("OAuth callback parsing failed.");
            foreach (var invalid in new[] { "GET /callback?state=wrong&code=x HTTP/1.1", "GET /callback?state=test-state&state=test-state&code=x HTTP/1.1", "GET //other-host/callback?state=test-state&code=x HTTP/1.1", "POST /callback?state=test-state&code=x HTTP/1.1" })
            if (LoopbackLogin.TryParseCallback(invalid, callbackOrigin, "test-state", out _))
                throw new Exception("Unsafe OAuth callback accepted.");
            var recognizers = SpeechRecognitionEngine.InstalledRecognizers().Select(x => new { x.Name, Language = x.Culture.Name }).ToArray();
            var preferences = new Settings { WakeEnabled = true, Voice = "Nora", MicrophoneMode = "ptt", IdleSeconds = 60, Enabled = false };
            var roundTrip = System.Text.Json.JsonSerializer.Deserialize<Settings>(System.Text.Json.JsonSerializer.Serialize(preferences))!;
            if (!roundTrip.WakeEnabled || roundTrip.Voice != "Nora" || roundTrip.MicrophoneMode != "ptt" || roundTrip.IdleSeconds != 60 || roundTrip.Enabled)
                throw new Exception("Preference serialization failed.");
            Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new
            {
                dpapi = true,
                preferences = true,
                recognizers,
                webView2 = CoreWebView2Environment.GetAvailableBrowserVersionString()
            }));
            return;
        }
        using var mutex = new Mutex(true, InstanceName, out var first);
        if (!first)
        {
            try
            {
                using var existing = EventWaitHandle.OpenExisting(InstanceName + ".Show");
                existing.Set();
            }
            catch (WaitHandleCannotBeOpenedException) { }
            return;
        }
        using var showSignal = new EventWaitHandle(false, EventResetMode.AutoReset, InstanceName + ".Show");
        ApplicationConfiguration.Initialize();
        using var window = new MainWindow(args.Contains("--tray"));
        var registration = ThreadPool.RegisterWaitForSingleObject(showSignal, (_, _) => { if (window.IsHandleCreated) window.BeginInvoke(window.ShowWindow); }, null, Timeout.Infinite, false);
        Application.Run(window);
        registration.Unregister(null);
    }
}

public sealed class MainWindow : Form
{
    const string Origin = "https://house-talk.local/";
    readonly WebView2 browser = new() { Dock = DockStyle.Fill };
    readonly Settings settings;
    readonly HomeConnection home;
    readonly NotifyIcon tray;
    readonly ToolStripMenuItem enabledItem = new("HouseTalk enabled"), wakeItem = new("Wake word enabled"), loginItem = new("Run on Windows login"), voiceMenu = new("Voice"), modeMenu = new("Microphone mode"), idleMenu = new("Auto-end after");
    readonly ToolStripMenuItem startItem = new("Start conversation"), endItem = new("End conversation"), muteItem = new("Mute microphone");
    SpeechRecognitionEngine? recognizer;
    bool paused, closing, exitRequested, ready, active, micMuted = true;

    public MainWindow(bool startInTray)
    {
        settings = Settings.Load();
        home = new HomeConnection(settings);
        if (!Settings.Voices.Contains(settings.Voice))
            settings.Voice = "Clara";
        if (settings.MicrophoneMode is not ("handsfree" or "ptt"))
            settings.MicrophoneMode = "handsfree";
        if (settings.IdleSeconds is not (0 or 30 or 60 or 120))
            settings.IdleSeconds = 30;
        Text = "House Talk";
        MinimumSize = new Size(430, 480);
        StartPosition = FormStartPosition.CenterScreen;
        var work = Screen.PrimaryScreen?.WorkingArea ?? new Rectangle(0, 0, 1280, 900);
        Width = Math.Min(Math.Max(430, settings.WindowWidth), work.Width);
        Height = Math.Min(Math.Max(480, settings.WindowHeight), work.Height);
        BackColor = Color.FromArgb(12, 19, 29);
        Controls.Add(browser);
        Icon = Icon.ExtractAssociatedIcon(Environment.ProcessPath!) ?? SystemIcons.Application;
        tray = new NotifyIcon { Icon = Icon, Text = "HouseTalk", Visible = true, ContextMenuStrip = BuildTrayMenu() };
        tray.DoubleClick += (_, _) => ShowWindow();
        RefreshTray();
        if (startInTray)
        {
            Opacity = 0;
            ShowInTaskbar = false;
        }
        Shown += async (_, _) => { await Initialize(); if (startInTray) Hide(); Opacity = 1; };
        Resize += (_, _) => { if (WindowState == FormWindowState.Minimized) { ShowInTaskbar = false; Hide(); } };
        ResizeEnd += (_, _) => SaveSize();
        FormClosing += async (_, eventArgs) =>
        {
            if (closing)
                return;
            eventArgs.Cancel = true;
            SaveSize();
            if (!exitRequested && eventArgs.CloseReason == CloseReason.UserClosing)
            {
                Hide();
                ShowInTaskbar = false;
                await EndConversation();
                return;
            }
            closing = true;
            StopWake();
            try
            {
                await EndConversation().WaitAsync(TimeSpan.FromSeconds(3));
            }
            catch { }
            tray.Visible = false;
            tray.Dispose();
            home.Dispose();
            Close();
        };
    }

    ContextMenuStrip BuildTrayMenu()
    {
        var menu = new ContextMenuStrip();
        menu.Items.Add("Open HouseTalk", null, (_, _) => ShowWindow());
        menu.Items.Add(new ToolStripSeparator());
        enabledItem.Click += async (_, _) => await SetEnabled(!settings.Enabled);
        menu.Items.Add(enabledItem);
        wakeItem.Click += (_, _) => ChangeWake(!settings.WakeEnabled, settings.WakePhrase);
        menu.Items.Add(wakeItem);
        foreach (var voice in Settings.Voices)
        {
            var item = new ToolStripMenuItem(voice) { Tag = voice };
            item.Click += (_, _) => { settings.Voice = voice; SaveAndNotify(); };
            voiceMenu.DropDownItems.Add(item);
        }
        menu.Items.Add(voiceMenu);
        menu.Items.Add("Personality instructions…", null, (_, _) => EditPersonality());
        foreach (var (label, mode) in new[] { ("Hands-free", "handsfree"), ("Push-to-talk", "ptt") })
        {
            var item = new ToolStripMenuItem(label) { Tag = mode };
            item.Click += (_, _) => { settings.MicrophoneMode = mode; SaveAndNotify(); };
            modeMenu.DropDownItems.Add(item);
        }
        menu.Items.Add(modeMenu);
        foreach (var seconds in new[] { 30, 60, 120, 0 })
        {
            var item = new ToolStripMenuItem(seconds == 0 ? "Off · end manually" : seconds + " seconds of quiet") { Tag = seconds };
            item.Click += (_, _) => { settings.IdleSeconds = seconds; SaveAndNotify(); };
            idleMenu.DropDownItems.Add(item);
        }
        menu.Items.Add(idleMenu);
        menu.Items.Add(new ToolStripSeparator());
        startItem.Click += (_, _) => { ShowWindow(); PostEvent("start"); };
        menu.Items.Add(startItem);
        muteItem.Click += (_, _) => PostEvent("toggleMic");
        menu.Items.Add(muteItem);
        endItem.Click += async (_, _) => await EndConversation();
        menu.Items.Add(endItem);
        menu.Items.Add(new ToolStripSeparator());
        loginItem.Click += (_, _) => { try { StartupRegistration.SetEnabled(!StartupRegistration.IsEnabled); settings.RunOnLogin = StartupRegistration.IsEnabled; SaveAndNotify(); } catch (Exception error) { ShowError(error.Message); } };
        menu.Items.Add(loginItem);
        menu.Items.Add("Exit HouseTalk", null, (_, _) => { exitRequested = true; Close(); });
        menu.Opening += (_, _) => RefreshTray();
        return menu;
    }
    void EditPersonality()
    {
        ShowWindow();
        using var dialog = new Form { Text = "HouseTalk personality", Width = 700, Height = 450, StartPosition = FormStartPosition.CenterParent, MinimizeBox = false, MaximizeBox = false };
        var editor = new TextBox { Multiline = true, ScrollBars = ScrollBars.Vertical, Dock = DockStyle.Fill, Text = settings.Personality, MaxLength = 8000 };
        var buttons = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 48, FlowDirection = FlowDirection.RightToLeft };
        var save = new Button { Text = "Save", DialogResult = DialogResult.OK };
        var cancel = new Button { Text = "Cancel", DialogResult = DialogResult.Cancel };
        var reset = new Button { Text = "Jarvis default", AutoSize = true };
        reset.Click += (_, _) => editor.Text = Settings.DefaultPersonality;
        buttons.Controls.AddRange([save, cancel, reset]);
        dialog.Controls.Add(editor);
        dialog.Controls.Add(buttons);
        dialog.AcceptButton = save;
        dialog.CancelButton = cancel;
        if (dialog.ShowDialog(this) == DialogResult.OK)
        {
            settings.Personality = string.IsNullOrWhiteSpace(editor.Text) ? Settings.DefaultPersonality : editor.Text.Trim();
            SaveAndNotify();
        }
    }
    void SaveSize()
    {
        if (WindowState == FormWindowState.Normal && Visible)
        {
            settings.WindowWidth = Width;
            settings.WindowHeight = Height;
            settings.Save();
        }
    }
    public void ShowWindow()
    {
        if (closing)
            return;
        ShowInTaskbar = true;
        Show();
        WindowState = FormWindowState.Normal;
        Activate();
        browser.Focus();
    }
    void ShowError(string message)
    {
        tray.ShowBalloonTip(5000, "HouseTalk", message, ToolTipIcon.Warning);
    }
    void RefreshTray()
    {
        enabledItem.Checked = settings.Enabled;
        wakeItem.Checked = settings.WakeEnabled;
        wakeItem.Enabled = settings.Enabled;
        loginItem.Checked = StartupRegistration.IsEnabled;
        voiceMenu.Text = "Voice: " + settings.Voice + " (next conversation)";
        foreach (ToolStripMenuItem item in voiceMenu.DropDownItems)
            item.Checked = (string)item.Tag! == settings.Voice;
        foreach (ToolStripMenuItem item in modeMenu.DropDownItems)
            item.Checked = (string)item.Tag! == settings.MicrophoneMode;
        foreach (ToolStripMenuItem item in idleMenu.DropDownItems)
            item.Checked = (int)item.Tag! == settings.IdleSeconds;
        startItem.Enabled = ready && settings.Enabled && !active && home.HasLogin;
        endItem.Enabled = ready && active;
        muteItem.Enabled = ready && active;
        muteItem.Text = micMuted ? "Unmute microphone (hands-free)" : "Mute microphone";
        var tooltip = !settings.Enabled ? "HouseTalk · disabled" : active ? (micMuted ? "HouseTalk · microphone muted" : "HouseTalk · live conversation") : settings.WakeEnabled ? "HouseTalk · waiting for " + settings.WakePhrase : "HouseTalk · microphone off";
        tray.Text = tooltip.Length > 63 ? tooltip[..63] : tooltip;
    }
    JsonObject Preferences() => new() { ["url"] = settings.Url, ["wakeAvailable"] = EnglishRecognizer() != null, ["connected"] = home.HasLogin, ["wakeEnabled"] = settings.WakeEnabled, ["wakePhrase"] = settings.WakePhrase, ["enabled"] = settings.Enabled, ["voice"] = settings.Voice, ["personality"] = settings.Personality, ["microphoneMode"] = settings.MicrophoneMode, ["idleSeconds"] = settings.IdleSeconds, ["runOnLogin"] = StartupRegistration.IsEnabled, ["installLocation"] = AppContext.BaseDirectory };
    void SaveAndNotify()
    {
        settings.Save();
        RefreshTray();
        PostEvent("settingsChanged", Preferences());
    }
    async Task SetEnabled(bool enabled)
    {
        settings.Enabled = enabled;
        if (!enabled)
        {
            StopWake();
            await EndConversation();
        }
        else if (settings.WakeEnabled && !paused)
            TryStartWake();
        SaveAndNotify();
    }
    void ChangeWake(bool enabled, string phrase)
    {
        phrase = phrase.Trim();
        if (phrase.Length < 3 || phrase.Length > 50)
        {
            ShowError("Choose a wake phrase between 3 and 50 characters.");
            return;
        }
        settings.WakePhrase = phrase;
        settings.WakeEnabled = enabled;
        StopWake();
        if (enabled && settings.Enabled && !paused)
            TryStartWake();
        SaveAndNotify();
    }
    async Task EndConversation()
    {
        if (browser.CoreWebView2 != null)
            await browser.CoreWebView2.ExecuteScriptAsync("window.houseTalk?.end()");
    }

    async Task Initialize()
    {
        try
        {
            var environment = await CoreWebView2Environment.CreateAsync(userDataFolder: Path.Combine(Settings.DataPath, "WebView"));
            await browser.EnsureCoreWebView2Async(environment);
            browser.CoreWebView2.SetVirtualHostNameToFolderMapping("house-talk.local", Path.Combine(AppContext.BaseDirectory, "www"), CoreWebView2HostResourceAccessKind.DenyCors);
            browser.CoreWebView2.Settings.AreDevToolsEnabled = false;
            browser.CoreWebView2.NavigationStarting += (_, eventArgs) => { if (!eventArgs.Uri.StartsWith(Origin, StringComparison.Ordinal)) eventArgs.Cancel = true; };
            browser.CoreWebView2.NewWindowRequested += (_, eventArgs) => eventArgs.Handled = true;
            browser.CoreWebView2.PermissionRequested += (_, eventArgs) =>
            {
                if (eventArgs.PermissionKind != CoreWebView2PermissionKind.Microphone || !eventArgs.Uri.StartsWith(Origin, StringComparison.Ordinal) || !settings.Enabled)
                {
                    eventArgs.State = CoreWebView2PermissionState.Deny;
                    return;
                }
                if (!settings.MicrophoneAllowed)
                {
                    settings.MicrophoneAllowed = MessageBox.Show(this, "Allow HouseTalk to use your microphone for conversations? This choice is remembered. You can mute, end, or disable HouseTalk at any time.", "HouseTalk microphone", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes;
                    settings.Save();
                }
                eventArgs.State = settings.MicrophoneAllowed ? CoreWebView2PermissionState.Allow : CoreWebView2PermissionState.Deny;
                eventArgs.SavesInProfile = false;
            };
            browser.CoreWebView2.WebMessageReceived += HandleMessage;
            browser.CoreWebView2.NavigationCompleted += (_, _) => { ready = true; RefreshTray(); if (settings.Enabled && settings.WakeEnabled && !paused) TryStartWake(); };
            browser.Source = new Uri(Origin + "index.html");
        }
        catch (Exception error) { ShowError("Could not start: " + error.Message); }
    }

    async void HandleMessage(object? sender, CoreWebView2WebMessageReceivedEventArgs eventArgs)
    {
        if (!eventArgs.Source.StartsWith(Origin, StringComparison.Ordinal))
            return;
        JsonObject? message = null;
        try
        {
            message = JsonNode.Parse(eventArgs.WebMessageAsJson)?.AsObject();
            if (message is null)
                return;
            var action = message["action"]?.GetValue<string>() ?? "";
            var payload = message["payload"]?.AsObject() ?? new JsonObject();
            JsonNode? result;
            switch (action)
            {
                case "rpc":
                    var type = payload["type"]!.GetValue<string>();
                    if (!settings.Enabled && (type is "session" or "tool"))
                        throw new Exception("HouseTalk is disabled. Enable it from the tray menu.");
                    result = await home.Call(type, payload["params"]?.AsObject() ?? new JsonObject());
                    break;
                case "settings":
                    result = Preferences();
                    break;
                case "trayMenu":
                    tray.ContextMenuStrip!.Show(this, new Point(20, 50));
                    result = new JsonObject();
                    break;
                case "preferences":
                    if (payload["voice"] is JsonNode voice)
                    {
                        var value = voice.GetValue<string>();
                        if (!Settings.Voices.Contains(value))
                            throw new Exception("Choose a supported Fish Live3 voice.");
                        settings.Voice = value;
                    }
                    if (payload["personality"] is JsonNode personality)
                    {
                        var value = personality.GetValue<string>().Trim();
                        if (value.Length > 8000)
                            throw new Exception("Keep personality instructions under 8,000 characters.");
                        settings.Personality = value.Length == 0 ? Settings.DefaultPersonality : value;
                    }
                    if (payload["microphoneMode"] is JsonNode mode)
                    {
                        var value = mode.GetValue<string>();
                        if (value is not ("handsfree" or "ptt"))
                            throw new Exception("Unknown microphone mode.");
                        settings.MicrophoneMode = value;
                    }
                    if (payload["idleSeconds"] is JsonNode idle)
                    {
                        var value = idle.GetValue<int>();
                        if (value is not (0 or 30 or 60 or 120))
                            throw new Exception("Choose a supported timeout.");
                        settings.IdleSeconds = value;
                    }
                    if (payload["runOnLogin"] is JsonNode login)
                    {
                        StartupRegistration.SetEnabled(login.GetValue<bool>());
                        settings.RunOnLogin = StartupRegistration.IsEnabled;
                    }
                    if (payload["enabled"] is JsonNode enabled)
                        await SetEnabled(enabled.GetValue<bool>());
                    SaveAndNotify();
                    result = Preferences();
                    break;
                case "state":
                    active = payload["active"]?.GetValue<bool>() ?? false;
                    micMuted = payload["micMuted"]?.GetValue<bool>() ?? true;
                    RefreshTray();
                    result = new JsonObject();
                    break;
                case "connect":
                    await home.Login(payload["url"]!.GetValue<string>());
                    RefreshTray();
                    result = new JsonObject { ["connected"] = true };
                    break;
                case "openSettings":
                    Process.Start(new ProcessStartInfo(settings.Url + "/config/integrations/dashboard?domain=fish_live3") { UseShellExecute = true });
                    result = new JsonObject();
                    break;
                case "wake":
                    ChangeWake(payload["enabled"]!.GetValue<bool>(), payload["phrase"]?.GetValue<string>() ?? settings.WakePhrase);
                    result = Preferences();
                    break;
                case "pauseWake":
                    paused = true;
                    StopWake();
                    result = new JsonObject();
                    break;
                case "resumeWake":
                    paused = false;
                    if (settings.Enabled && settings.WakeEnabled && !closing)
                        TryStartWake();
                    RefreshTray();
                    result = new JsonObject();
                    break;
                default:
                    throw new Exception("Unsupported app request.");
            }
            Post(new JsonObject { ["id"] = message["id"]?.DeepClone(), ["result"] = result });
        }
        catch (Exception error) { if (message != null) Post(new JsonObject { ["id"] = message["id"]?.DeepClone(), ["error"] = error.Message }); }
    }
    RecognizerInfo? EnglishRecognizer() => SpeechRecognitionEngine.InstalledRecognizers().FirstOrDefault(x => x.Culture.TwoLetterISOLanguageName == "en");
    void TryStartWake()
    {
        try
        {
            StartWake();
        }
        catch (Exception error) { settings.WakeEnabled = false; settings.Save(); ShowError(error.Message); RefreshTray(); PostEvent("settingsChanged", Preferences()); }
    }
    void StartWake()
    {
        if (recognizer != null || closing || !settings.Enabled || !settings.WakeEnabled)
            return;
        var info = EnglishRecognizer() ?? throw new Exception("Install an English Windows speech recognition language to enable the wake word.");
        var engine = new SpeechRecognitionEngine(info);
        try
        {
            engine.LoadGrammar(new Grammar(new GrammarBuilder(settings.WakePhrase) { Culture = info.Culture }));
            engine.SpeechRecognized += (_, eventArgs) => { if (eventArgs.Result.Confidence < .6 || !string.Equals(eventArgs.Result.Text, settings.WakePhrase, StringComparison.OrdinalIgnoreCase)) return; BeginInvoke(() => { if (paused || closing || !settings.Enabled) return; paused = true; StopWake(); PostEvent("wake"); }); };
            engine.SetInputToDefaultAudioDevice();
            engine.RecognizeAsync(RecognizeMode.Multiple);
            recognizer = engine;
        }
        catch { engine.Dispose(); throw; }
    }
    void StopWake()
    {
        var previous = recognizer;
        recognizer = null;
        if (previous is null)
            return;
        try
        {
            previous.RecognizeAsyncCancel();
            previous.SetInputToNull();
        }
        catch { }
        previous.Dispose();
    }
    void PostEvent(string name, JsonObject? data = null) => Post(new JsonObject { ["event"] = name, ["settings"] = data });
    void Post(JsonObject message)
    {
        if (!closing && browser.CoreWebView2 != null)
            browser.CoreWebView2.PostWebMessageAsJson(message.ToJsonString());
    }
}

