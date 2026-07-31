#!/bin/bash
set -euo pipefail

mkdir -p /home/ops/.ssh
chmod 700 /home/ops/.ssh

if [ -f /run/secrets/demo_pubkey ]; then
  cp /run/secrets/demo_pubkey /home/ops/.ssh/authorized_keys
else
  echo "WARNING: 未挂载 Demo 公钥，SSH 密钥登录不可用"
  touch /home/ops/.ssh/authorized_keys
fi

chmod 600 /home/ops/.ssh/authorized_keys
chown -R ops:ops /home/ops/.ssh

sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config

echo "Demo SSH target-vm ready (user: ops, port: 22)"
exec /usr/sbin/sshd -D -e
