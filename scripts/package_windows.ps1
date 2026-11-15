param([string]$Destination = 'dist\HouseTalk')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$destinationPath = [IO.Path]::GetFullPath((Join-Path $root $Destination))
$distRoot = [IO.Path]::GetFullPath((Join-Path $root 'dist'))
if (-not $destinationPath.StartsWith($distRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Package destination must stay inside dist.' }
if (Test-Path -LiteralPath $destinationPath) { Remove-Item -LiteralPath $destinationPath -Recurse -Force }
dotnet publish (Join-Path $root 'windows\HouseTalk\HouseTalk.csproj') -c Release -r win-x64 --self-contained true -o $destinationPath -p:NuGetAudit=true -p:DebugType=None -p:DebugSymbols=false
if ($LASTEXITCODE -ne 0) { throw 'Windows build failed' }
Copy-Item -LiteralPath (Join-Path $root 'windows\Install.ps1'),(Join-Path $root 'windows\Uninstall.ps1'),(Join-Path $root 'LICENSE'),(Join-Path $root 'DISCLAIMER.md'),(Join-Path $root 'THIRD_PARTY_NOTICES.md') -Destination $destinationPath
Copy-Item -LiteralPath (Join-Path $root 'third_party') -Destination $destinationPath -Recurse
$nugetRoot = if ($env:NUGET_PACKAGES) { $env:NUGET_PACKAGES } else { Join-Path $env:USERPROFILE '.nuget\packages' }
$licenseDir = Join-Path $destinationPath 'third_party\windows'
New-Item -ItemType Directory -Path $licenseDir -Force | Out-Null
foreach ($package in @('microsoft.web.webview2','system.speech','system.security.cryptography.protecteddata','microsoft.netcore.app.runtime.win-x64')) {
    $packageRoot = Join-Path $nugetRoot $package
    if (Test-Path -LiteralPath $packageRoot) {
        foreach ($version in Get-ChildItem -LiteralPath $packageRoot -Directory) {
            foreach ($file in Get-ChildItem -LiteralPath $version.FullName -File | Where-Object Name -Match '^(LICENSE|NOTICE|THIRD-PARTY)') {
                Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $licenseDir ($package + '-' + $version.Name + '-' + $file.Name))
            }
        }
    }
}
$archive = Join-Path $distRoot 'HouseTalk-Windows-x64.zip'
Compress-Archive -Path (Join-Path $destinationPath '*') -DestinationPath $archive -Force
Write-Host ('Built ' + $archive)
