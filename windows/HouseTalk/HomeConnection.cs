using System.Collections.Concurrent;
using System.Diagnostics;
using System.Net.Http.Json;
using System.Net.WebSockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;

namespace HouseTalk;

public sealed class HomeConnection : IDisposable
{
    readonly Settings settings;
    readonly HttpClient http = new(new HttpClientHandler { AllowAutoRedirect = false }) { Timeout = TimeSpan.FromSeconds(30) };
    readonly SemaphoreSlim connectLock = new(1, 1), sendLock = new(1, 1);
    readonly ConcurrentDictionary<int, TaskCompletionSource<JsonNode?>> pending = new();
    ClientWebSocket? socket;
    string accessToken = "";
    DateTime expires;
    int sequence;
    public HomeConnection(Settings settings) => this.settings = settings;
    public bool HasLogin => !string.IsNullOrEmpty(settings.RefreshToken);

    public async Task Login(string url)
    {
        if (!Uri.TryCreate(url.Trim().TrimEnd('/'), UriKind.Absolute, out var uri) || (uri.Scheme != "http" && uri.Scheme != "https") || !string.IsNullOrEmpty(uri.UserInfo) || uri.AbsolutePath != "/" || !string.IsNullOrEmpty(uri.Query))
            throw new Exception("Enter the base address of your Home Assistant (http:// or https://).");
        // Loopback callback plus PKCE: no HA password is ever read by this app.
        using var callback = new LoopbackLogin();
        string client = callback.ClientId, redirect = callback.RedirectUri;
        string state = Convert.ToHexString(RandomNumberGenerator.GetBytes(24));
        string verifier = Convert.ToBase64String(RandomNumberGenerator.GetBytes(48)).TrimEnd('=').Replace('+', '-').Replace('/', '_');
        string challenge = Convert.ToBase64String(SHA256.HashData(Encoding.UTF8.GetBytes(verifier))).TrimEnd('=').Replace('+', '-').Replace('/', '_');
        string authorize = uri.GetLeftPart(UriPartial.Authority) + "/auth/authorize?client_id=" + Uri.EscapeDataString(client) + "&redirect_uri=" + Uri.EscapeDataString(redirect) + "&state=" + state + "&code_challenge_method=S256&code_challenge=" + challenge;
        Process.Start(new ProcessStartInfo(authorize) { UseShellExecute = true });
        using var loginTimeout = new CancellationTokenSource(TimeSpan.FromMinutes(5));
        string code;
        try
        {
            code = await callback.WaitForCode(state, loginTimeout.Token);
        }
        catch (OperationCanceledException) { throw new Exception("Home Assistant login timed out. Try connecting again."); }
        using var response = await http.PostAsync(uri.GetLeftPart(UriPartial.Authority) + "/auth/token", new FormUrlEncodedContent(new Dictionary<string, string> { ["grant_type"] = "authorization_code", ["code"] = code, ["client_id"] = client, ["code_verifier"] = verifier }));
        if (!response.IsSuccessStatusCode)
            throw new Exception("Home Assistant did not accept the login. Try again.");
        var token = (await response.Content.ReadFromJsonAsync<JsonObject>())!;
        settings.Url = uri.GetLeftPart(UriPartial.Authority);
        settings.ClientId = client;
        settings.RefreshToken = token["refresh_token"]!.GetValue<string>();
        settings.Save();
        accessToken = token["access_token"]!.GetValue<string>();
        expires = DateTime.UtcNow.AddSeconds(token["expires_in"]!.GetValue<int>() - 60);
        socket?.Abort();
        socket?.Dispose();
        socket = null;
        await EnsureConnection();
    }

    async Task Refresh()
    {
        if (!HasLogin)
            throw new Exception("Open Settings and connect Home Assistant first.");
        if (!string.IsNullOrEmpty(accessToken) && DateTime.UtcNow < expires)
            return;
        using var response = await http.PostAsync(settings.Url + "/auth/token", new FormUrlEncodedContent(new Dictionary<string, string> { ["grant_type"] = "refresh_token", ["refresh_token"] = settings.RefreshToken, ["client_id"] = settings.ClientId }));
        if (!response.IsSuccessStatusCode)
            throw new Exception("Your Home Assistant login has expired. Connect again in Settings.");
        var token = (await response.Content.ReadFromJsonAsync<JsonObject>())!;
        accessToken = token["access_token"]!.GetValue<string>();
        expires = DateTime.UtcNow.AddSeconds(token["expires_in"]!.GetValue<int>() - 60);
    }

    public async Task EnsureConnection()
    {
        await connectLock.WaitAsync();
        try
        {
            if (socket?.State == WebSocketState.Open)
                return;
            await Refresh();
            socket?.Dispose();
            socket = new ClientWebSocket();
            var uri = new UriBuilder(settings.Url) { Scheme = settings.Url.StartsWith("https:") ? "wss" : "ws", Path = "/api/websocket" }.Uri;
            await socket.ConnectAsync(uri, CancellationToken.None).WaitAsync(TimeSpan.FromSeconds(15));
            var hello = await Read(socket);
            if (hello?["type"]?.GetValue<string>() != "auth_required")
                throw new Exception("Unexpected Home Assistant handshake.");
            await Send(socket, new JsonObject { ["type"] = "auth", ["access_token"] = accessToken });
            var auth = await Read(socket);
            if (auth?["type"]?.GetValue<string>() != "auth_ok")
                throw new Exception("Home Assistant authentication failed.");
            _ = Receive(socket);
        }
        finally { connectLock.Release(); }
    }

    public async Task<JsonNode?> Call(string type, JsonObject payload)
    {
        if (type is not ("status" or "session" or "tool" or "end"))
            throw new Exception("Unsupported House Talk operation.");
        await EnsureConnection();
        int id = Interlocked.Increment(ref sequence);
        var completion = new TaskCompletionSource<JsonNode?>(TaskCreationOptions.RunContinuationsAsynchronously);
        pending[id] = completion;
        var message = (JsonObject)payload.DeepClone();
        message["type"] = "fish_live3/" + type;
        message["id"] = id;
        try
        {
            await sendLock.WaitAsync();
            try
            {
                await Send(socket!, message);
            }
            finally { sendLock.Release(); }
            return await completion.Task.WaitAsync(TimeSpan.FromSeconds(90));
        }
        finally { pending.TryRemove(id, out _); }
    }

    async Task Receive(ClientWebSocket current)
    {
        try
        {
            while (current.State == WebSocketState.Open)
            {
                var msg = await Read(current);
                if (msg?["type"]?.GetValue<string>() != "result")
                    continue;
                var id = msg["id"]!.GetValue<int>();
                if (!pending.TryRemove(id, out var completion))
                    continue;
                if (msg["success"]!.GetValue<bool>())
                    completion.TrySetResult(msg["result"]?.DeepClone());
                else
                    completion.TrySetException(new Exception(msg["error"]?["message"]?.GetValue<string>() ?? "Home Assistant request failed."));
            }
        }
        catch { foreach (var item in pending.Values) item.TrySetException(new Exception("Connection to Home Assistant was lost. End the conversation and reconnect.")); }
    }
    static async Task Send(ClientWebSocket ws, JsonObject message) => await ws.SendAsync(Encoding.UTF8.GetBytes(message.ToJsonString()), WebSocketMessageType.Text, true, CancellationToken.None);
    static async Task<JsonObject?> Read(ClientWebSocket ws)
    {
        var buffer = new byte[16384];
        using var stream = new MemoryStream();
        WebSocketReceiveResult received;
        do
        {
            received = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), CancellationToken.None);
            if (received.MessageType == WebSocketMessageType.Close)
                throw new Exception("Home Assistant closed the connection.");
            stream.Write(buffer, 0, received.Count);
            if (stream.Length > 2_000_000)
                throw new Exception("Home Assistant response is too large.");
        } while (!received.EndOfMessage);
        return JsonNode.Parse(stream.ToArray())?.AsObject();
    }
    public void Dispose()
    {
        socket?.Abort();
        socket?.Dispose();
        http.Dispose();
    }
}
