# KylinOps Docker 一键启动（默认 Demo SSH 模式）
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$KeyDir = Join-Path $Root "deploy\docker\demo-keys"
$PrivKey = Join-Path $KeyDir "id_ed25519"
$PubKey = "$PrivKey.pub"
$EnvFile = Join-Path $Root ".env.docker"

Write-Host "==> KylinOps Docker 一键部署"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "未检测到 Docker，请先安装 Docker Desktop"
}

if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.docker.example") $EnvFile
    Write-Host "已创建 .env.docker，请编辑并填入 LLM_API_KEY 后重新运行本脚本"
    exit 1
}

$envContent = Get-Content $EnvFile -Raw
$llmMatch = [regex]::Match($envContent, '(?m)^LLM_API_KEY=(.+)$')
$llmKey = if ($llmMatch.Success) { $llmMatch.Groups[1].Value.Trim() } else { "" }

if ([string]::IsNullOrWhiteSpace($llmKey) -or $llmKey -eq "your_deepseek_api_key") {
    Write-Error "请在 .env.docker 中配置有效的 LLM_API_KEY"
}

$portMatch = [regex]::Match($envContent, '(?m)^KYLINOPS_PORT=(.+)$')
$Port = if ($portMatch.Success) { $portMatch.Groups[1].Value.Trim() } else { "8000" }

if (-not (Test-Path $KeyDir)) {
    New-Item -ItemType Directory -Path $KeyDir -Force | Out-Null
}

if (-not (Test-Path $PrivKey)) {
    Write-Host "==> 生成 Demo SSH 密钥..."
    if (Get-Command ssh-keygen -ErrorAction SilentlyContinue) {
        & ssh-keygen -t ed25519 -f $PrivKey -N '""' -C "kylinops-demo"
    } else {
        Write-Error "未找到 ssh-keygen。请安装 OpenSSH 客户端，或手动在 deploy/docker/demo-keys/ 生成 id_ed25519 密钥对"
    }
}

Write-Host "==> 构建并启动容器（profile: demo）..."
docker compose --profile demo up -d --build

Write-Host "==> 等待服务就绪..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/v1/system/health" -UseBasicParsing -TimeoutSec 3
        $ready = $true
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host " KylinOps 已启动"
Write-Host " 访问地址: http://localhost:$Port"
Write-Host " 默认账号: admin / admin123"
Write-Host " 普通用户: ty / ty666"
Write-Host " Demo SSH: ops@target-vm (容器内)"
Write-Host "=========================================="
Write-Host ""
docker compose ps

if ($ready) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/system/health" -TimeoutSec 5
        Write-Host "健康检查: $($health | ConvertTo-Json -Compress -Depth 5)"
    } catch {
        Write-Host "健康检查请求失败，请稍后手动访问 /api/v1/system/health"
    }
} else {
    Write-Host "服务仍在启动中，请稍后访问 http://localhost:$Port"
}
