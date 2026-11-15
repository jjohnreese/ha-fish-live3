param([switch]$RemoveSettings)
$ErrorActionPreference = 'Stop'
$installRoot = Join-Path $env:LOCALAPPDATA 'Programs\HouseTalk'
$settingsRoot = Join-Path $env:LOCALAPPDATA 'HouseTalk'
if (Get-Process -Name HouseTalk -ErrorAction SilentlyContinue) { throw 'Exit HouseTalk from the tray first.' }
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$run = (Get-ItemProperty -LiteralPath $runKey -Name HouseTalk -ErrorAction SilentlyContinue).HouseTalk
if ($run -and $run.StartsWith(('"' + (Join-Path $installRoot 'HouseTalk.exe') + '"'), [StringComparison]::OrdinalIgnoreCase)) {
    Remove-ItemProperty -LiteralPath $runKey -Name HouseTalk
}
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Programs')) 'HouseTalk.lnk'
if (Test-Path -LiteralPath $shortcutPath) {
    $shell = New-Object -ComObject WScript.Shell
    if ($shell.CreateShortcut($shortcutPath).TargetPath -eq (Join-Path $installRoot 'HouseTalk.exe')) { Remove-Item -LiteralPath $shortcutPath }
}
if (Test-Path -LiteralPath $installRoot) {
    $resolved = (Resolve-Path -LiteralPath $installRoot).Path
    $expected = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs\HouseTalk'))
    if ($resolved -ne $expected -or (Get-Item -LiteralPath $resolved).LinkType) { throw 'Unexpected install path; refusing removal.' }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
if ($RemoveSettings -and (Test-Path -LiteralPath $settingsRoot)) {
    $resolved = (Resolve-Path -LiteralPath $settingsRoot).Path
    $expected = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'HouseTalk'))
    if ($resolved -ne $expected -or (Get-Item -LiteralPath $resolved).LinkType) { throw 'Unexpected settings path; refusing removal.' }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
Write-Host 'HouseTalk removed. Settings were retained unless -RemoveSettings was specified.'
