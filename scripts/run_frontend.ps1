# 启动前端（开发模式）
#
# 用法：  .\scripts\run_frontend.ps1

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $projectRoot 'frontend'

if (-not (Test-Path -LiteralPath (Join-Path $frontendDir 'node_modules'))) {
    Write-Host "未找到 frontend/node_modules，请先执行：" -ForegroundColor Yellow
    Write-Host "  cd frontend; npm install" -ForegroundColor Yellow
    exit 1
}

Push-Location $frontendDir
Write-Host "前端开发服务器： http://localhost:5173" -ForegroundColor Green
Write-Host "（/api 请求会代理到 http://127.0.0.1:8000，请先启动后端）" -ForegroundColor Cyan
try {
    npm run dev
} finally {
    Pop-Location
}
