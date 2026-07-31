#!/usr/bin/env bash
# KylinOps Docker 一键启动（默认 Demo SSH 模式）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

KEY_DIR="$ROOT/deploy/docker/demo-keys"
PRIV_KEY="$KEY_DIR/id_ed25519"
PUB_KEY="$PRIV_KEY.pub"
ENV_FILE="$ROOT/.env.docker"
PORT="${KYLINOPS_PORT:-8000}"

echo "==> KylinOps Docker 一键部署"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: 未检测到 Docker，请先安装 Docker Desktop"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  cp "$ROOT/.env.docker.example" "$ENV_FILE"
  echo "已创建 .env.docker，请编辑并填入 LLM_API_KEY 后重新运行本脚本"
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "$ENV_FILE"
set +a

if [ -z "${LLM_API_KEY:-}" ] || [ "${LLM_API_KEY}" = "your_deepseek_api_key" ]; then
  echo "ERROR: 请在 .env.docker 中配置有效的 LLM_API_KEY"
  exit 1
fi

mkdir -p "$KEY_DIR"
if [ ! -f "$PRIV_KEY" ]; then
  echo "==> 生成 Demo SSH 密钥..."
  ssh-keygen -t ed25519 -f "$PRIV_KEY" -N "" -C "kylinops-demo"
fi

echo "==> 构建并启动容器（profile: demo）..."
docker compose --profile demo up -d --build

echo "==> 等待服务就绪..."
for i in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${PORT}/api/v1/system/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo ""
echo "=========================================="
echo " KylinOps 已启动"
echo " 访问地址: http://localhost:${PORT}"
echo " 默认账号: admin / admin123"
echo " 普通用户: ty / ty666"
echo " Demo SSH: ops@target-vm (容器内)"
echo "=========================================="
echo ""
docker compose ps

HEALTH=$(curl -sf "http://127.0.0.1:${PORT}/api/v1/system/health" || echo "{}")
echo "健康检查: $HEALTH"
