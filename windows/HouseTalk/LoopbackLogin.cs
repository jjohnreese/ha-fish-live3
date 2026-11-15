using System.Net;
using System.Net.Sockets;
using System.Text;

namespace HouseTalk;

/// <summary>Unprivileged, loopback-only OAuth callback; no HTTP.sys URL reservation needed.</summary>
public sealed class LoopbackLogin : IDisposable
{
    readonly TcpListener listener = new(IPAddress.Loopback, 0);
    public string ClientId
    {
        get;
    }
    public string RedirectUri => ClientId + "callback";

    public LoopbackLogin()
    {
        listener.Start();
        ClientId = $"http://127.0.0.1:{((IPEndPoint)listener.LocalEndpoint).Port}/";
    }

    public async Task<string> WaitForCode(string expectedState, CancellationToken cancellation)
    {
        while (true)
        {
            using var client = await listener.AcceptTcpClientAsync(cancellation);
            using var stream = client.GetStream();
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
            timeout.CancelAfter(TimeSpan.FromSeconds(10));
            var buffer = new byte[1024];
            using var header = new MemoryStream();
            string request = "";
            try
            {
                while (header.Length <= 16384)
                {
                    var read = await stream.ReadAsync(buffer, timeout.Token);
                    if (read == 0)
                        break;
                    header.Write(buffer, 0, read);
                    request = Encoding.ASCII.GetString(header.ToArray());
                    if (request.Contains("\r\n\r\n", StringComparison.Ordinal))
                        break;
                }
                string? code = null;
                var valid = header.Length <= 16384 && TryParseCallback(request.Split("\r\n")[0], new Uri(ClientId), expectedState, out code);
                var html = valid ? "<h2>Home Assistant connected</h2><p>Return to HouseTalk.</p>" : "<h2>This login callback is not valid.</h2>";
                var body = Encoding.UTF8.GetBytes(html);
                var response = Encoding.ASCII.GetBytes($"HTTP/1.1 {(valid ? "200 OK" : "400 Bad Request")}\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {body.Length}\r\nConnection: close\r\n\r\n");
                await stream.WriteAsync(response, timeout.Token);
                await stream.WriteAsync(body, timeout.Token);
                if (valid)
                    return code!;
            }
            catch (OperationCanceledException) when (!cancellation.IsCancellationRequested) { }
            catch (IOException) { }
        }
    }

    public static bool TryParseCallback(string line, Uri origin, string expectedState, out string? code)
    {
        code = null;
        var pieces = line.Split(' ');
        if (pieces.Length != 3 || pieces[0] != "GET" || !pieces[2].StartsWith("HTTP/1.", StringComparison.Ordinal)
            || !Uri.TryCreate(origin, pieces[1], out var uri) || uri.Scheme != "http" || uri.Host != origin.Host
            || uri.Port != origin.Port || uri.AbsolutePath != "/callback" || !string.IsNullOrEmpty(uri.UserInfo))
            return false;
        var fields = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var field in uri.Query.TrimStart('?').Split('&', StringSplitOptions.RemoveEmptyEntries))
        {
            var pair = field.Split('=', 2);
            var name = WebUtility.UrlDecode(pair[0]);
            if (!fields.TryAdd(name, pair.Length == 2 ? WebUtility.UrlDecode(pair[1]) : ""))
                return false;
        }
        return fields.TryGetValue("state", out var state) && state == expectedState
            && fields.TryGetValue("code", out code) && !string.IsNullOrEmpty(code);
    }

    public void Dispose() => listener.Stop();
}
