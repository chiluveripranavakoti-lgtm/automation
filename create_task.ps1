# PowerShell script to register Daily AI Morning Briefing in Windows Task Scheduler
# Scheduled to run every day at 08:00 AM IST (Asia/Kolkata)

param(
    [string]$TaskName = "DailyAIMorningBriefing",
    [string]$DailyTime = "08:00",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = (Get-Command python.exe).Source

if (-not $PythonExe) {
    Write-Error "Python executable not found in PATH. Please install Python or specify full path."
    exit 1
}

$AppPyPath = Join-Path $ScriptDir "app.py"

if (-not (Test-Path $AppPyPath)) {
    Write-Error "Could not locate app.py at $AppPyPath"
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Creating Windows Scheduled Task: $TaskName" -ForegroundColor Cyan
Write-Host "Target Script : $AppPyPath"
Write-Host "Python Path   : $PythonExe"
Write-Host "Daily Time    : $DailyTime AM"
Write-Host "==========================================================" -ForegroundColor Cyan

# Action: Run python.exe app.py inside workspace working directory
$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "app.py" -WorkingDirectory $ScriptDir

# Trigger: Daily at specified time
$Trigger = New-ScheduledTaskTrigger -Daily -At $DailyTime

# Settings: Allow on battery, start when available if missed, wake to run
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# Check if task already exists
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($ExistingTask) {
    if ($Force) {
        Write-Host "Task '$TaskName' already exists. Unregistering previous task..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    } else {
        Write-Host "Task '$TaskName' already exists. Use -Force to overwrite." -ForegroundColor Yellow
        exit 0
    }
}

# Register the task under the current logged-in user
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Automated Daily AI Morning Briefing executed at 08:00 AM IST."

Write-Host ""
Write-Host "Scheduled task '$TaskName' successfully registered!" -ForegroundColor Green
Write-Host "To verify: Get-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Green
Write-Host "To run manually now: Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Green
Write-Host "To remove: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor Yellow
