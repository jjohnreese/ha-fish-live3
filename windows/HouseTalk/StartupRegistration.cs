using Microsoft.Win32;
namespace HouseTalk;

public static class StartupRegistration
{
    const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";
    public static bool IsEnabled
    {
        get
        {
            using var key = Registry.CurrentUser.OpenSubKey(RunKey);
            return key?.GetValue("HouseTalk") is string;
        }
    }
    public static void SetEnabled(bool enabled)
    {
        using var key = Registry.CurrentUser.CreateSubKey(RunKey);
        if (enabled)
            key.SetValue("HouseTalk", "\"" + Environment.ProcessPath + "\" --tray", RegistryValueKind.String);
        else
            key.DeleteValue("HouseTalk", false);
    }
}
