# Registers the GEO engine's scheduled tasks for the signed-in Windows user.
# Run in your own PowerShell window (not from inside Claude):
#   powershell -ExecutionPolicy Bypass -File C:\geo\scripts\register_tasks.ps1
param([string]$Root = "C:\geo")

$engine = Join-Path $Root "engine"
$pythonw = Join-Path $Root ".venv\Scripts\pythonw.exe"   # the engine's own Python; no console window
if (-not (Test-Path $pythonw)) { throw "Create the virtual environment first: python -m venv $Root\.venv" }

function Add-GeoTask($name, $script, $triggers, $settings) {
    $action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$engine\$script`"" -WorkingDirectory $engine
    Register-ScheduledTask -TaskName $name -TaskPath "\GEO\" -Action $action -Trigger $triggers `
        -Settings $settings -Force | Out-Null
    Write-Host "Registered \GEO\$name"
}

$batch = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 6)
$forever = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

Add-GeoTask "GEO Daily" "daily.py" @(
    (New-ScheduledTaskTrigger -Daily -At 6am),
    (New-ScheduledTaskTrigger -Daily -At 12pm),
    (New-ScheduledTaskTrigger -Daily -At 6pm)) $batch
Add-GeoTask "GEO Weekly Report" "weekly_report.py" (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 7am) $batch
Add-GeoTask "GEO Learn Lift" "learn_lift.py" (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 9pm) $batch
Add-GeoTask "GEO Listener" "listener.py" (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME) $forever

Write-Host "`nStart the listener now with:  Start-ScheduledTask -TaskPath '\GEO\' -TaskName 'GEO Listener'"
