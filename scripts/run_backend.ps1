# 启动后端（开发模式）
#
# 用法：  .\scripts\run_backend.ps1
#         .\scripts\run_backend.ps1 -Port 8000 -NoReload
#
# 说明：--reload 仅用于开发。生产 / 服务器必须使用 systemd
#       （见 docs/server_deployment_plan.md），不要长期运行 --reload。

[CmdletBinding()]
param(
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8000,
    [switch]$NoReload
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $projectRoot 'backend'
$python = 'D:\App\Business\Coding\Python\Miniconda\envs\pd\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "找不到 pd 环境的 Python：$python" -ForegroundColor Red
    Write-Host "请确认 conda 环境 pd 存在，或修改本脚本中的 `$python 路径。" -ForegroundColor Yellow
    exit 1
}

# 校验解释器版本，避免误用系统 Python 3.13
$version = & $python --version 2>&1
if ($version -notmatch '3\.11') {
    Write-Host "警告：当前解释器为 $version，项目要求 Python 3.11。" -ForegroundColor Yellow
}

Write-Host "Python : $python" -ForegroundColor Cyan
Write-Host "版本   : $version" -ForegroundColor Cyan
Write-Host "工作目录: $backendDir" -ForegroundColor Cyan

$env:PYTHONPATH = $backendDir
Push-Location $backendDir

$arguments = @('-m', 'uvicorn', 'app.main:app', '--host', $BindHost, '--port', "$Port")
if (-not $NoReload) { $arguments += '--reload' }

Write-Host "启动   : uvicorn $($arguments -join ' ')" -ForegroundColor Green
Write-Host "文档   : http://${BindHost}:$Port/docs" -ForegroundColor Green

try {
    & $python @arguments
} finally {
    Pop-Location
}
