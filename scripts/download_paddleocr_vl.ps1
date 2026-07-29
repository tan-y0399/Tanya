param(
  [string]$Model = "PaddlePaddle/PaddleOCR-VL-1.6",
  [string]$Target = "backend/models/PaddleOCR-VL-1.6"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$targetPath = Join-Path $root $Target

New-Item -ItemType Directory -Force -Path $targetPath | Out-Null

if (-not (Get-Command modelscope -ErrorAction SilentlyContinue)) {
  Write-Host "modelscope CLI not found. Install it in your project Python environment first:"
  Write-Host "  pip install modelscope"
  exit 1
}

modelscope download --model $Model --local_dir $targetPath
