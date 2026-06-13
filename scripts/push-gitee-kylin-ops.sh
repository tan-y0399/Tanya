#!/usr/bin/env bash
# 推送 KylinOps 到 Gitee: https://gitee.com/xiao11ji/kylin-ops
set -euo pipefail
cd "$(dirname "$0")/.."

GIT="git -c safe.directory=$(pwd)"
REMOTE="${1:-origin}"
BRANCH="${2:-main}"

echo ">>> 远程: $($GIT remote get-url "$REMOTE")"
echo ">>> 分支: $BRANCH"
$GIT push -u "$REMOTE" "$BRANCH"
echo ">>> 推送完成"
