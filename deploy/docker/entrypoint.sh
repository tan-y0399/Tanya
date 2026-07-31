#!/bin/bash
set -euo pipefail

if [ -z "${LLM_API_KEY:-}" ] || [ "${LLM_API_KEY}" = "your_deepseek_api_key" ]; then
  echo "ERROR: 请在 .env.docker 中配置有效的 LLM_API_KEY"
  exit 1
fi

mkdir -p \
  /app/backend/data/chat_uploads \
  /app/backend/data/feedback_uploads \
  /app/backend/data/generated_assets

if [ -n "${SSH_KEY_PATH:-}" ] && [ ! -f "${SSH_KEY_PATH}" ]; then
  echo "WARNING: SSH 私钥不存在: ${SSH_KEY_PATH}（SSH 运维功能可能不可用）"
fi

if [ "${SSH_HOST:-}" = "target-vm" ] && [ -f "${SSH_KEY_PATH:-/run/secrets/ssh_key}" ]; then
  echo "等待 Demo SSH 目标机就绪..."
  key="${SSH_KEY_PATH:-/run/secrets/ssh_key}"
  user="${SSH_USER:-ops}"
  for _ in $(seq 1 30); do
    if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 -i "$key" "${user}@${SSH_HOST}" echo ok >/dev/null 2>&1; then
      echo "Demo SSH 目标机已就绪"
      break
    fi
    sleep 2
  done
fi

exec "$@"
