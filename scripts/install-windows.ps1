# Install the live path for the current user on Windows. Mirrors install-user.sh.
#
# STATUS (WP10, see docs/11-PORTING-WINDOWS-MACOS.md): the Windows capture Source
# (Raw Input) and the notification-area indicator are not finished yet. This
# script installs what is ready, builds the recorder if it can, registers the
# daemon to run at logon, and opens the onboarding page once. Finish it on
# Windows.
#
#   powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot\..").Path
$data = Join-Path $env:LOCALAPPDATA 'FidusAchates'
New-Item -ItemType Directory -Force -Path $data | Out-Null

# Layout decides which key a letter shortcut is on (ADR-0012). Default qwerty.
$layout = if ($env:FIDUS_LAYOUT) { $env:FIDUS_LAYOUT } else { 'qwerty' }

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command python3 -ErrorAction SilentlyContinue).Source }
if (-not $py) { throw 'python not found on PATH' }

# Build the recorder. This fails until the Windows capture Source lands (the
# agent is evdev-only today), so the failure is expected and not fatal here.
$agent = Join-Path $data 'fidus-agent.exe'
if (Get-Command cargo -ErrorAction SilentlyContinue) {
    Write-Host 'building the recorder (expected to fail until the Windows capture lands, WP10)...'
    Push-Location $root
    try {
        cargo build --release --features research-trace
        Copy-Item (Join-Path $root 'target\release\fidus-agent.exe') $agent -Force
        Write-Host "recorder installed at $agent"
    } catch {
        Write-Warning 'recorder build failed (expected until WP10 Windows capture).'
    } finally { Pop-Location }
} else {
    Write-Warning 'cargo not found; install Rust (https://rustup.rs) to build the recorder.'
}

# The notification-area indicator (crates/fidus-tray) is not built here yet; see docs/11.

# Run the daemon at logon via a scheduled task.
$lab = Join-Path $root 'lab'
$action = New-ScheduledTaskAction -Execute $py `
    -Argument "-m fidus_lab.daemon --agent `"$agent`" --layout $layout --retention-days 30" `
    -WorkingDirectory $lab
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
# PYTHONPATH must reach fidus_lab; set it for the task's environment.
$env:PYTHONPATH = $lab
Register-ScheduledTask -TaskName 'FidusAchates' -Action $action -Trigger $trigger `
    -Settings $settings -Force | Out-Null
Write-Host "registered the FidusAchates logon task (layout $layout)."

# Open the onboarding page once, on first install.
$marker = Join-Path $data '.onboarded'
if (-not (Test-Path $marker)) {
    Start-Process (Join-Path $root 'contrib\onboarding\onboarding.html')
    New-Item -ItemType File -Path $marker | Out-Null
    Write-Host 'opened the onboarding page.'
}

Write-Host @'

NOT YET FINISHED (WP10, docs\11-PORTING-WINDOWS-MACOS.md):
  - the Windows capture Source (Raw Input) in fidus-agent
  - the notification-area indicator (crates\fidus-tray)

Remove with: Unregister-ScheduledTask -TaskName FidusAchates -Confirm:$false
'@
