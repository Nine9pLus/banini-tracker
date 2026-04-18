<#
.SYNOPSIS
  Register Windows Task Scheduler tasks for the banini Telegram pipeline.

.DESCRIPTION
  Creates two weekly tasks (Mon-Fri) that each run weekday_scheduler.py once
  with TG_ONCE_RUN=1, then exit. Replaces existing tasks of the same name.

  Run from any shell:
      powershell -ExecutionPolicy Bypass -File .\register_tasks.ps1

  Remove later with:
      Unregister-ScheduledTask -TaskName 'BaniniTracker_0920' -Confirm:$false
      Unregister-ScheduledTask -TaskName 'BaniniTracker_1220' -Confirm:$false
#>

$ErrorActionPreference = 'Stop'

$ScriptDir       = Split-Path -Parent $MyInvocation.MyCommand.Path
$TelegramAuthDir = $ScriptDir
$PythonExe       = Join-Path $TelegramAuthDir '.venv\Scripts\python.exe'
$WeekdayScript   = Join-Path $TelegramAuthDir 'weekday_scheduler.py'
$EnvFile         = Join-Path $TelegramAuthDir '.env'
$LogDir          = Join-Path $TelegramAuthDir 'logs'
$LogFile         = Join-Path $LogDir 'task_scheduler.log'

# ---- sanity checks ----
if (-not (Test-Path $PythonExe))     { throw "Python venv not found: $PythonExe" }
if (-not (Test-Path $WeekdayScript)) { throw "weekday_scheduler.py not found: $WeekdayScript" }
if (-not (Test-Path $EnvFile))       { Write-Warning ".env not found at $EnvFile -- script will fail at runtime until you create one." }
if (-not (Test-Path $LogDir))        { New-Item -ItemType Directory -Path $LogDir | Out-Null }

# ---- schedule definition ----
$Schedules = @(
    [pscustomobject]@{ Name = 'BaniniTracker_0920'; Hour = 9;  Minute = 20 }
    [pscustomobject]@{ Name = 'BaniniTracker_1220'; Hour = 12; Minute = 20 }
)
$Days = @('Monday','Tuesday','Wednesday','Thursday','Friday')

foreach ($s in $Schedules) {
    $taskName = $s.Name

    # cmd /c "set VAR=1 && python script >> log 2>&1"
    # double-quotes around paths handle spaces; outer single-quotes keep PowerShell from re-parsing.
    $cmdLine = 'set TG_ONCE_RUN=1 && "' + $PythonExe + '" "' + $WeekdayScript + '" >> "' + $LogFile + '" 2>&1'
    $argString = '/c ' + $cmdLine

    $action = New-ScheduledTaskAction `
        -Execute 'cmd.exe' `
        -Argument $argString `
        -WorkingDirectory $TelegramAuthDir

    $triggerTime = Get-Date -Hour $s.Hour -Minute $s.Minute -Second 0
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Days -At $triggerTime

    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -DontStopIfGoingOnBatteries `
        -AllowStartIfOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
        -MultipleInstances IgnoreNew

    $principal = New-ScheduledTaskPrincipal `
        -UserId $env:USERNAME `
        -LogonType Interactive `
        -RunLevel Limited

    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "Removed existing task: $taskName"
    }

    Register-ScheduledTask `
        -TaskName $taskName `
        -Description "Run banini Telegram pipeline once at $('{0:D2}:{1:D2}' -f $s.Hour, $s.Minute) Mon-Fri" `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal | Out-Null

    Write-Host ("Registered: {0}  ->  {1:D2}:{2:D2}  (Mon-Fri)" -f $taskName, $s.Hour, $s.Minute)
}

Write-Host ''
Write-Host '=== Done ==='
Write-Host "Logs will append to: $LogFile"
Write-Host ''
Write-Host 'Verify:'
Write-Host "    Get-ScheduledTask -TaskName 'BaniniTracker_*' | Format-Table TaskName, State, @{n='NextRun';e={(Get-ScheduledTaskInfo `$_).NextRunTime}}"
Write-Host ''
Write-Host 'Test-fire one immediately:'
Write-Host "    Start-ScheduledTask -TaskName 'BaniniTracker_0920'"
