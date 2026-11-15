# Development

Use a test HA instance or a separate pipeline. Never operate somebody's household devices just to validate an unrelated change.

## Layout

- `custom_components/fish_live3`: HA integration, REST client and scoped tools.
- `fish_live3_worker`: private Supervisor app and LiveKit transport.
- `frontend/src`: dashboard/client controls and testable microphone/idle logic.
- `windows/HouseTalk`: Windows tray host, OAuth and local wake recognizer.
- `examples` and `docs`: generic user-facing configuration and instructions.
- `tests`: offline protocol/security/regression checks. HA stubs do not replace physical satellite or real-instance tests.

## Checks

Use Python 3.13 for unit tests (HA itself provides its supported interpreter), Node 22.22+ and the .NET 8 SDK for Windows.

```sh
python -m pip install -r requirements-test.txt
pytest -q
python scripts/check_public_tree.py
cd frontend
npm ci
npm test
npm run build
```

On Windows, `dotnet publish windows/HouseTalk/HouseTalk.csproj -c Release -r win-x64 --self-contained true -o dist/HouseTalk` builds the native host. `--self-test` checks DPAPI/preference round-trips without starting a microphone. `--settings-check` prints only non-secret settings; do not expand it to print credentials.

Keep the generated dashboard bundle in sync with frontend source. Release CI rebuilds it, checks the public tree, runs HACS and Hassfest validation, and builds the Windows archive in a clean runner. Runtime data and `.env` files are ignored and prohibited by the scan.

## Release

Update the integration/app/Windows versions and changelog together. Push changes, wait for Validation to pass, then push a `v...` tag. Release automation builds fresh artifacts, includes license notices and checksums, and creates a GitHub release. A beta tag creates a prerelease. Do not attach a ZIP copied from a running user installation.

HACS custom-repository installation does not require default-list inclusion. Submit to `hacs/default` only after the HACS Action and Hassfest pass without ignores and a full GitHub release exists. Maintainers decide acceptance; do not claim default-store availability beforehand.
