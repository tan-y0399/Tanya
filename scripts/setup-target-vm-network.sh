#!/bin/bash
# 在「目标虚拟机」控制台以 root 执行，使其可被 KylinOps（192.168.64.x 网段）访问
set -e

PLATFORM_NET="${1:-192.168.64}"
TARGET_IP="${2:-192.168.64.128}"
TARGET_USER="${3:-ty}"

echo "=== 1. 配置网卡到 ${PLATFORM_NET}.0/24 ==="
CONN=$(nmcli -t -f NAME,TYPE con show --active | awk -F: '$2=="802-3-ethernet"{print $1; exit}')
if [ -z "$CONN" ]; then
  CONN=$(nmcli -t -f NAME con show | head -1)
fi
nmcli con mod "$CONN" ipv4.method manual ipv4.addresses "${TARGET_IP}/24" ipv4.gateway "${PLATFORM_NET}.2" ipv4.dns "8.8.8.8"
nmcli con up "$CONN"
echo "当前 IP: $(hostname -I)"

echo "=== 2. 开放 SSH 防火墙 ==="
if systemctl is-active firewalld >/dev/null 2>&1; then
  firewall-cmd --permanent --add-service=ssh
  firewall-cmd --reload
  firewall-cmd --list-services
else
  echo "firewalld 未运行，跳过"
fi

echo "=== 3. 启动 SSH ==="
systemctl enable --now sshd
ss -tlnp | grep ':22' || { echo "sshd 未监听 22 端口"; exit 1; }

echo "=== 4. 创建运维用户 ${TARGET_USER}（若不存在）==="
id "$TARGET_USER" >/dev/null 2>&1 || useradd -m -s /bin/bash "$TARGET_USER"
usermod -aG wheel "$TARGET_USER" 2>/dev/null || usermod -aG sudo "$TARGET_USER" 2>/dev/null || true
echo "${TARGET_USER} ALL=(ALL) NOPASSWD: ALL" > "/etc/sudoers.d/kylinops-${TARGET_USER}"
chmod 440 "/etc/sudoers.d/kylinops-${TARGET_USER}"

echo "=== 完成 ==="
echo "请在 KylinOps 中添加服务器："
echo "  主机地址: ${TARGET_IP}"
echo "  SSH 用户名: ${TARGET_USER}"
echo "  主机密码: ${TARGET_USER} 或 root 的登录密码"
