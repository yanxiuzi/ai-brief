# 生成一期简报。加 -Mock 参数可离线演示（不花 token，输出到 mock/ 子目录）。
param([switch]$Mock)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

# 明确解析 python 路径，避免在计划任务环境中找不到命令
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $python) { $python = (Get-Command python3 -ErrorAction SilentlyContinue).Source }
if (-not $python) {
    Write-Host "[错误] 找不到 python，请先安装 Python 3 或把它加入 PATH。" -ForegroundColor Red
    exit 1
}

if ($Mock) {
    & $python .\bot.py --mock
} else {
    & $python .\bot.py
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[失败] 简报生成失败，退出码 $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

# 生成成功后：用 GitHub API 更新线上公开站
# （不用 git push：国内直连 GitHub 时 push 常被连接重置，API 通道稳定得多）
if (-not $Mock) {
    $cred = "protocol=https`nhost=github.com`n`n" | git credential fill 2>$null
    $line = ($cred | Select-String -Pattern "^password=").Line
    if ($line) {
        $env:GITHUB_TOKEN = $line.Substring(9)
        & $python .\publish_api.py
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] 线上公开站已更新" -ForegroundColor Green
        } else {
            Write-Host "[warn] 线上更新失败，下次运行会再试" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[warn] 未找到 GitHub 凭据，跳过线上发布" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "完整版： start .\latest.html" -ForegroundColor Cyan
Write-Host "公开站： start .\site\index.html" -ForegroundColor Cyan