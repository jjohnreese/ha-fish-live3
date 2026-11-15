param([switch]$RunOnLogin)
$ErrorActionPreference = 'Stop'
$installRoot = Join-Path $env:LOCALAPPDATA 'Programs\HouseTalk'
$sourceExe = Join-Path $PSScriptRoot 'HouseTalk.exe'
if (-not (Test-Path -LiteralPath $sourceExe)) { throw 'Extract the complete release ZIP before running this installer.' }
$running = Get-Process -Name HouseTalk -ErrorAction SilentlyContinue
if ($running) { throw 'Exit HouseTalk from its tray menu before installing or upgrading.' }
New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
Get-ChildItem -LiteralPath $PSScriptRoot | Where-Object Name -ne 'Data' | Copy-Item -Destination $installRoot -Recurse -Force
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Programs')) 'HouseTalk.lnk'))
$shortcut.TargetPath = Join-Path $installRoot 'HouseTalk.exe'
$shortcut.WorkingDirectory = $installRoot
$shortcut.IconLocation = (Join-Path $installRoot 'HouseTalk.exe') + ',0'
$shortcut.Description = 'Talk to your Home Assistant'
$shortcut.Save()
if ($RunOnLogin) {
    $runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
    New-Item -Path $runKey -Force | Out-Null
    Set-ItemProperty -LiteralPath $runKey -Name HouseTalk -Value ('"' + (Join-Path $installRoot 'HouseTalk.exe') + '" --tray')
}
Write-Host ('Installed HouseTalk in ' + $installRoot)
Write-Host 'Open HouseTalk from Start. Existing settings and sign-in are preserved.'
Write-Host 'To pin it, right-click its Start-menu shortcut and choose Pin to Start.'
