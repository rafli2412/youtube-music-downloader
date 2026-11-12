param(
    [Parameter(Mandatory = $true)][string]$Installer,
    [string]$Report = "build/reports/install-windows.json"
)
$ErrorActionPreference = 'Stop'
$reportPath = [IO.Path]::GetFullPath($Report)
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($reportPath)) | Out-Null
$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{BB27ABBE-3AC2-4DBA-9DED-120D682B93D6}_is1'
if (Test-Path -LiteralPath $uninstallKey) {
    throw 'An existing app installation was found. Run installer QA on a disposable Windows account instead.'
}
$installerPath = (Resolve-Path -LiteralPath $Installer).Path
$workspace = Join-Path ([IO.Path]::GetTempPath()) ('ytmp3-install-check-' + [Guid]::NewGuid().ToString('N'))
$appDirectory = Join-Path $workspace 'App folder'
$sentinelDirectory = Join-Path $workspace 'unrelated PATH entry'
$null = New-Item -ItemType Directory -Path $workspace, $sentinelDirectory -Force
$checks = [ordered]@{}
$installed = $false
$sentinelAdded = $false

function Read-UserPath {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment')
    try {
        if ($null -eq $key) { return '' }
        return [string]$key.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
    } finally { if ($key) { $key.Dispose() } }
}
function Write-UserPath([string]$Value) {
    $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Environment')
    try { $key.SetValue('Path', $Value, [Microsoft.Win32.RegistryValueKind]::ExpandString) }
    finally { $key.Dispose() }
}
function Path-Entries([string]$Value) {
    return @($Value.Split(';') | Where-Object { $_.Trim() -ne '' } | ForEach-Object { $_.Trim().Trim('"').TrimEnd('\') })
}
function Invoke-Checked([string]$Executable, [string[]]$Arguments) {
    $output = & $Executable @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Executable $output" }
    return $output
}
function Uninstall-TestApp {
    $uninstaller = Join-Path $appDirectory 'unins000.exe'
    if (Test-Path -LiteralPath $uninstaller) {
        $process = Start-Process -FilePath $uninstaller -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART' -PassThru
        if (-not $process.WaitForExit(120000)) {
            $process.Kill($true)
            $process.WaitForExit()
            throw 'App uninstallation timed out.'
        }
        if ($process.ExitCode -ne 0) { throw "App uninstallation failed: $($process.ExitCode)" }
    }
}

try {
    $before = Read-UserPath
    $logPath = Join-Path ([IO.Path]::GetDirectoryName($reportPath)) 'windows-setup.log'
    $parameters = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/DIR="' + $appDirectory + '"'), '/TASKS=addtopath', ('/LOG="' + $logPath + '"'))
    $process = Start-Process -FilePath $installerPath -ArgumentList $parameters -PassThru
    if (-not $process.WaitForExit(240000)) {
        $process.Kill($true)
        $process.WaitForExit()
        throw 'App installation timed out.'
    }
    if ($process.ExitCode -ne 0) { throw "App installation failed: $($process.ExitCode). See windows-setup.log." }
    $installed = $true
    $cli = Join-Path $appDirectory 'ytmp3.exe'
    $desktop = Join-Path $appDirectory 'ytmp3-desktop.exe'
    if (-not (Test-Path $cli) -or -not (Test-Path $desktop)) { throw 'Installed launchers are missing.' }
    $checks.launchers_installed = $true
    $after = Read-UserPath
    if (@((Path-Entries $after) | Where-Object { $_ -ieq $appDirectory }).Count -ne 1) { throw 'The app PATH entry was not added once.' }
    foreach ($entry in (Path-Entries $before)) {
        if ($entry -notin (Path-Entries $after)) { throw 'An existing PATH entry was changed.' }
    }
    $checks.user_path_preserved = $true

    $originalProcessPath = $env:PATH
    try {
        $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
        $version = Invoke-Checked $cli @('--version')
        if ($version -notmatch '^ytmp3 \d+\.\d+\.\d+$') { throw 'Unexpected installed CLI version output.' }
        $doctorPath = Join-Path $workspace 'doctor.json'
        $null = Invoke-Checked $cli @('doctor', '--report', $doctorPath)
        if (-not (Get-Content -Raw $doctorPath | ConvertFrom-Json).ok) { throw 'Installed CLI diagnostics failed.' }
        $desktopPath = Join-Path $workspace 'desktop.json'
        $null = Invoke-Checked $desktop @('--self-check', '--report', $desktopPath)
        if (-not (Get-Content -Raw $desktopPath | ConvertFrom-Json).ok) { throw 'Installed desktop diagnostics failed.' }
    } finally { $env:PATH = $originalProcessPath }
    $checks.installed_offline_engine = $true

    # Simulate another app adding PATH after this installation. Uninstall must keep it.
    Write-UserPath ($after.TrimEnd(';') + ';' + $sentinelDirectory)
    $sentinelAdded = $true
    $keepFile = Join-Path $workspace 'download-to-keep.mp3'
    [IO.File]::WriteAllText($keepFile, 'Existing download')
    Uninstall-TestApp
    $installed = $false
    if (Test-Path $cli) { throw 'Uninstall left the app launcher behind.' }
    $remaining = Path-Entries (Read-UserPath)
    if ($appDirectory -in $remaining) { throw 'Uninstall left its app PATH entry behind.' }
    if ($sentinelDirectory -notin $remaining) { throw 'Uninstall removed another PATH entry.' }
    foreach ($entry in (Path-Entries $before)) {
        if ($entry -notin $remaining) { throw 'Uninstall removed a pre-existing PATH entry.' }
    }
    if ([IO.File]::ReadAllText($keepFile) -ne 'Existing download') { throw 'Uninstall touched downloaded files.' }
    $checks.uninstall_preserves_other_paths_and_downloads = $true
    $result = @{ ok = $true; checks = $checks; clean_machine_verified = $false; native_gui_verified = $false }
} catch {
    $result = @{ ok = $false; checks = $checks; error = $_.Exception.Message; clean_machine_verified = $false }
} finally {
    try {
        if ($installed -or (Test-Path (Join-Path $appDirectory 'unins000.exe'))) { Uninstall-TestApp }
        if ($sentinelAdded) {
            $value = Read-UserPath
            $tokens = @($value.Split(';') | Where-Object { $_.Trim().Trim('"').TrimEnd('\') -ine $sentinelDirectory })
            Write-UserPath ($tokens -join ';')
        }
        if (Test-Path $workspace) { Remove-Item -LiteralPath $workspace -Recurse -Force }
    } catch {
        $result.ok = $false
        $result.cleanup_error = $_.Exception.Message
    }
}
$result | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath $reportPath
$result | ConvertTo-Json -Depth 6 | Write-Host
if (-not $result.ok) { exit 1 }
