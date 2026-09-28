# 一键初始化本地开发环境
#
# 用法：  .\scripts\bootstrap.ps1
#         .\scripts\bootstrap.ps1 -SkipFrontend
#
# 作用：
#   1. 检查 conda 环境 pd 与 Python 3.11
#   2. 安装后端依赖（不含 torch / mediapipe / opencv，见下方说明）
#   3. 安装前端依赖
#   4. 生成 .env（若不存在）
#   5. 初始化数据库（alembic upgrade head）
#   6. 运行 pytest

[CmdletBinding()]
param(
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $projectRoot 'backend'
$frontendDir = Join-Path $projectRoot 'frontend'
$python = 'D:\App\Business\Coding\Python\Miniconda\envs\pd\python.exe'

function Step($message) { Write-Host "`n=== $message ===" -ForegroundColor Cyan }
function Ok($message) { Write-Host "  [OK] $message" -ForegroundColor Green }
function Warn($message) { Write-Host "  [!!] $message" -ForegroundColor Yellow }

Step '1. 检查 Python 环境'
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "找不到 $python" -ForegroundColor Red
    Write-Host "请先创建 conda 环境：conda create -n pd python=3.11 -y" -ForegroundColor Yellow
    exit 1
}
$version = & $python --version 2>&1
Write-Host "  $python"
Write-Host "  $version"
if ($version -notmatch '3\.11') {
    Warn "项目要求 Python 3.11，当前为 $version"
} else {
    Ok 'Python 3.11'
}

if (-not $SkipBackend) {
    Step '2. 安装后端依赖'
    & $python -m pip install --upgrade pip
    # 注意：requirements.txt 不含 torch / mediapipe / opencv。
    #   torch     -> 按 GPU 架构单独安装（本机 RTX 5070 为 sm_120，需 cu128 / cu130）
    #   mediapipe / opencv -> Phase 4 接入 Finger Tapping 时再安装
    & $python -m pip install -r (Join-Path $backendDir 'requirements.txt')
    Ok '后端依赖安装完成'

    Step '3. 生成 .env'
    $envFile = Join-Path $projectRoot '.env'
    if (Test-Path -LiteralPath $envFile) {
        Ok '.env 已存在，未覆盖'
    } else {
        Copy-Item -LiteralPath (Join-Path $projectRoot '.env.example') -Destination $envFile
        $secret = & $python -c "import secrets; print(secrets.token_hex(32))"
        $content = Get-Content -LiteralPath $envFile -Raw
        $content = $content -replace 'JWT_SECRET=CHANGE_ME', "JWT_SECRET=$secret"
        [System.IO.File]::WriteAllText($envFile, $content, (New-Object System.Text.UTF8Encoding($false)))
        Ok '.env 已生成，并写入随机 JWT_SECRET'
        Warn '请修改 .env 中的 BOOTSTRAP_ADMIN_PASSWORD'
    }

    Step '4. 初始化数据库'
    $env:PYTHONPATH = $backendDir
    Push-Location $backendDir
    try {
        & $python -m alembic upgrade head
        Ok '数据库迁移完成'
    } finally {
        Pop-Location
    }
}

if (-not $SkipFrontend) {
    Step '5. 安装前端依赖'
    Push-Location $frontendDir
    try {
        npm install
        Ok '前端依赖安装完成'
    } finally {
        Pop-Location
    }
}

if (-not $SkipTests) {
    Step '6. 运行后端测试'
    $env:PYTHONPATH = $backendDir
    Push-Location $backendDir
    try {
        & $python -m pytest tests -q
        Ok '测试通过'
    } finally {
        Pop-Location
    }
}

Step '完成'
Write-Host '启动后端： .\scripts\run_backend.ps1'
Write-Host '启动前端： .\scripts\run_frontend.ps1'
Write-Host '浏览器：   http://localhost:5173'
