#!/usr/bin/env bash
# 导入 deploy/sql 与 deploy/knowledge 到当前数据库
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
if [ ! -d .venv ] && [ ! -d .venv_linux ]; then
  echo "请先创建 Python 虚拟环境并安装依赖"
  exit 1
fi
PY="$ROOT/backend/.venv/Scripts/python.exe"
[ -f "$PY" ] || PY="$ROOT/backend/.venv_linux/bin/python"
[ -f "$PY" ] || PY="python3"
"$PY" scripts/import_deploy_data.py
