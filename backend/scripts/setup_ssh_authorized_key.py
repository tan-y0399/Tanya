"""
将本机 SSH 公钥写入远程主机的 authorized_keys，实现免密登录。

用法（需先输入一次 root 密码）:
  cd backend
  .venv\\Scripts\\activate
  python scripts/setup_ssh_authorized_key.py

也可通过环境变量传入密码（仅本地一次性使用）:
  set SSH_PASSWORD=你的root密码
  python scripts/setup_ssh_authorized_key.py
"""

import getpass
import os
import sys

import paramiko

# 将 backend 加入 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402


def main() -> int:
    host = settings.ssh_host
    port = settings.ssh_port
    username = settings.ssh_user
    key_path = os.path.expanduser(settings.ssh_key_path)
    pub_path = key_path + ".pub"

    if not os.path.isfile(pub_path):
        print(f"错误: 公钥不存在 {pub_path}")
        print("请先生成密钥: ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519")
        return 1

    with open(pub_path, encoding="utf-8") as f:
        pub_key = f.read().strip()

    password = os.environ.get("SSH_PASSWORD") or getpass.getpass(
        f"请输入 {username}@{host} 的 SSH 密码（仅本次使用，不会保存）: "
    )

    print(f"正在连接 {username}@{host}:{port} ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=15,
            allow_agent=False,
            look_for_keys=False,
        )
    except paramiko.AuthenticationException:
        print("认证失败：密码错误或该用户禁止密码登录。")
        return 1
    except Exception as e:
        print(f"连接失败: {e}")
        return 1

    # 写入 authorized_keys（去重）
    cmd = (
        "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
        f"touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && "
        f"grep -qxF '{pub_key}' ~/.ssh/authorized_keys || "
        f"echo '{pub_key}' >> ~/.ssh/authorized_keys && "
        "echo KEY_INSTALLED"
    )
    _, stdout, stderr = client.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    client.close()

    if "KEY_INSTALLED" not in out:
        print(f"写入公钥失败。stdout={out!r} stderr={err!r}")
        return 1

    print("公钥已写入远程 authorized_keys。")

    # 验证密钥登录
    print("正在验证密钥登录 ...")
    test = paramiko.SSHClient()
    test.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        pkey = paramiko.PKey.from_path(key_path)
        test.connect(
            hostname=host,
            port=port,
            username=username,
            pkey=pkey,
            timeout=15,
            allow_agent=False,
            look_for_keys=False,
        )
        _, stdout, _ = test.exec_command("hostname && uname -r")
        result = stdout.read().decode().strip()
        test.close()
        print(f"密钥登录成功！远程信息:\n{result}")
        return 0
    except Exception as e:
        print(f"公钥已写入，但密钥登录验证失败: {e}")
        print("请检查远程 /etc/ssh/sshd_config 是否允许 PubkeyAuthentication yes")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
