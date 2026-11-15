using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace HouseTalk;

public sealed class Settings
{
    public string Url { get; set; } = "http://homeassistant.local:8123";
    public string RefreshToken { get; set; } = "";
    public string ClientId { get; set; } = "";
    public string WakePhrase { get; set; } = "Hey House";
    public bool WakeEnabled
    {
        get; set;
    }
    public bool Enabled { get; set; } = true;
    public bool RunOnLogin
    {
        get; set;
    }
    public string Voice { get; set; } = "Clara";
    public string MicrophoneMode { get; set; } = "handsfree";
    public int IdleSeconds { get; set; } = 30;
    public bool MicrophoneAllowed
    {
        get; set;
    }
    public int WindowWidth { get; set; } = 800;
    public int WindowHeight { get; set; } = 900;
    public const string DefaultPersonality = "You are Jarvis, a calm, capable household assistant inspired by Iron Man's JARVIS. Be concise, composed and quietly witty. Use natural English, with occasional dry humor when it fits. Do not narrate routine actions or tool calls. Avoid fillers such as 'Let me check', 'One moment', 'I'll switch it on', and repeated acknowledgements. For a routine home request, silently use the tools and then give one brief result. Speak before a tool only if you need clarification or there is a meaningful delay or risk to explain. Answer naturally and briefly; do not sound like a robotic checklist.";
    public string Personality { get; set; } = DefaultPersonality;
    public static readonly string[] Voices = ["Clara", "Nora", "Harper", "Patricia", "Owen", "Marco", "Milo", "Jonah"];
    public static string DataPath => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "HouseTalk");
    private static string FilePath => Path.Combine(DataPath, "connection.dpapi");
    public static Settings Load()
    {
        if (File.Exists(FilePath))
            return JsonSerializer.Deserialize<Settings>(ProtectedData.Unprotect(File.ReadAllBytes(FilePath), null, DataProtectionScope.CurrentUser)) ?? new();
        var initial = Path.Combine(AppContext.BaseDirectory, "home-assistant.json");
        return File.Exists(initial) ? JsonSerializer.Deserialize<Settings>(File.ReadAllText(initial)) ?? new() : new();
    }
    public void Save()
    {
        Directory.CreateDirectory(DataPath);
        var encrypted = ProtectedData.Protect(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(this)), null, DataProtectionScope.CurrentUser);
        var temp = FilePath + ".tmp";
        File.WriteAllBytes(temp, encrypted);
        File.Move(temp, FilePath, true);
    }
}
