<#
.SYNOPSIS
  注册 Windows 每日定时任务：到点自动生成一期简报 + 更新公开站。
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\install_daily_task.ps1 -Time 08:30
.EXAMPLE
  Unregister-ScheduledTask -TaskName "AI-Briefing-Bot" -Confirm:$false   # 删除任务
#>
param(
    [string]$Time = "08:30",
    [string]$TaskName = "AI-Briefing-Bot"
)

$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "run_once.ps1"

if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "找不到 run_once.ps1，请确认脚本和 bot.py 在同一个目录。"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`"" `
    -WorkingDirectory $PSScriptRoot

$trigger = New-ScheduledTaskTrigger -Daily -At $Time

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "AI 简报机器人：每天 $Time 自动生成简报并更新公开试读站" -Force | Out-Null

Write-Host "[OK] 已注册每日任务：$TaskName（每天 $Time）" -ForegroundColor Green
Write-Host "     立即测试：Start-ScheduledTask -TaskName $TaskName"
Write-Host "     查看状态：Get-ScheduledTaskInfo -TaskName $TaskName"
Write-Host "     删除任务：Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
Write-Host ""
Write-Host "注意：用户级任务需要电脑开着并处于登录状态；本机 Claude Code Router 也要在运行。" -ForegroundColor Yellow