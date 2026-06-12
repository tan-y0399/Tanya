"""
SSH 客户端 —— 管理 Windows ↔ 麒麟VM 的通信通道。

本地 Agent 负责逻辑推理，远程 VM 负责执行操作。
通信方式：paramiko SSH（免密密钥认证）。
"""

import os
import socket
import paramiko
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def _load_private_key(key_path: str):
    """自动检测并加载私钥文件（支持 RSA、Ed25519、ECDSA 等格式）"""
    if not os.path.isfile(key_path):
        raise FileNotFoundError(f"私钥文件不存在: {key_path}")

    # paramiko >= 3.4 推荐用 PKey.from_path，避免各版本 Key 类名差异
    from_path = getattr(paramiko.PKey, "from_path", None)
    if callable(from_path):
        try:
            return from_path(key_path)
        except (ValueError, paramiko.SSHException, OSError):
            pass

    key_class_names = ("RSAKey", "Ed25519Key", "ECDSAKey", "DSSKey")
    for name in key_class_names:
        key_cls = getattr(paramiko, name, None)
        if key_cls is None:
            continue
        try:
            return key_cls.from_private_key_file(key_path)
        except (ValueError, paramiko.SSHException, OSError):
            continue
    raise ValueError(f"无法识别的密钥格式: {key_path}（已尝试 RSA/Ed25519/ECDSA）")


from app.core.config import settings as _settings
from app.services.server_user_policy import assert_allowed_ssh_user

# 最大重试次数
MAX_RETRIES = 2


class SSHClient:
    """SSH 连接管理器，封装与远程麒麟VM的通信。"""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        username: str = None,
        key_path: str = None,
        timeout: int = None,
    ):
        self.host = host or _settings.ssh_host
        self.port = port or _settings.ssh_port
        self.username = username or _settings.ssh_user
        self.key_path = key_path or _settings.ssh_key_path
        self.timeout = timeout or _settings.ssh_timeout
        self._client: Optional[paramiko.SSHClient] = None

    @property
    def client(self) -> paramiko.SSHClient:
        """获取或创建 SSH 连接（懒加载）。"""
        if self._client is None:
            self.connect()
        return self._client

    def connect(self) -> None:
        """建立 SSH 连接，启用 keepalive 防止空闲断开。"""
        self.username = assert_allowed_ssh_user(self.username)
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            key_path = os.path.expanduser(self.key_path)
            key = _load_private_key(key_path)
            self._client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                pkey=key,
                timeout=self.timeout,
            )
            transport = self._client.get_transport()
            if transport:
                transport.set_keepalive(30)
            logger.info(f"SSH connected to {self.host}")
        except Exception as e:
            logger.error(f"SSH connect failed: {e}")
            raise

    def execute(self, command: str, retry: bool = True):  # type: (...) -> Tuple[str, str, int]
        """执行远程命令，返回 (stdout, stderr, exit_code)。自动重试僵尸连接。"""
        last_error = None
        for attempt in range(MAX_RETRIES if retry else 1):
            try:
                stdin, stdout, stderr = self.client.exec_command(command, timeout=self.timeout)
                exit_code = stdout.channel.recv_exit_status()
                out = stdout.read().decode("utf-8", errors="replace").strip()
                err = stderr.read().decode("utf-8", errors="replace").strip()
                return out, err, exit_code
            except (socket.error, EOFError, OSError) as e:
                last_error = e
                logger.warning(f"SSH execute attempt {attempt + 1} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    try:
                        self.reconnect()
                    except Exception:
                        pass
            except Exception as e:
                last_error = e
                logger.warning(f"SSH execute attempt {attempt + 1} failed (unexpected): {e}")
                if attempt < MAX_RETRIES - 1:
                    try:
                        self.reconnect()
                    except Exception:
                        pass

        raise last_error or RuntimeError("SSH execute failed after retries")

    def reconnect(self) -> None:
        """断开并重新连接。"""
        self.close()
        self.connect()

    def close(self) -> None:
        """关闭 SSH 连接。"""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def is_alive(self) -> bool:
        """检查连接是否存活（发送实际探测而非仅检查 transport 标志）。"""
        if self._client is None:
            return False
        transport = self._client.get_transport()
        if transport is None or not transport.is_active():
            return False
        try:
            # 发送实际探测，避免僵尸连接
            transport.send_ignore()
            return True
        except Exception:
            return False


# ── SSH 连接池（多机集群管理）──

class SSHPool:
    """管理多台麒麟服务器的 SSH 连接，按 server_id 索引"""

    def __init__(self):
        self._clients: dict[str, SSHClient] = {}

    def get_or_create(self, server_id: str, host: str = None,
                      port: int = None, username: str = None,
                      key_path: str = None) -> SSHClient:
        """获取或创建指定服务器的 SSH 连接"""
        key = server_id
        if key not in self._clients:
            username = assert_allowed_ssh_user(username)
            client = SSHClient(host=host, port=port, username=username, key_path=key_path)
            client.connect()
            self._clients[key] = client
        else:
            client = self._clients[key]
            if not client.is_alive():
                client.reconnect()
        return client

    def get(self, server_id: str) -> Optional[SSHClient]:
        """获取已存在的连接（不自动创建）"""
        return self._clients.get(server_id)

    def remove(self, server_id: str) -> None:
        """移除并断开指定服务器的连接"""
        client = self._clients.pop(server_id, None)
        if client:
            client.close()

    def get_default(self) -> Optional[SSHClient]:
        """获取默认连接（兼容旧代码）"""
        if self._clients:
            return next(iter(self._clients.values()))
        return None

    def close_all(self) -> None:
        """关闭所有连接"""
        for client in self._clients.values():
            client.close()
        self._clients.clear()


SSH_POOL = SSHPool()

# 全局单例（兼容旧代码）
_ssh_client: Optional[SSHClient] = None


def get_ssh_client() -> SSHClient:
    """获取全局 SSH 客户端单例（优先使用连接池默认连接）。"""
    global _ssh_client
    pooled = SSH_POOL.get_default()
    if pooled:
        return pooled
    if _ssh_client is None:
        _ssh_client = SSHClient()
        _ssh_client.connect()
    return _ssh_client


async def get_ssh_for_server(server_id: str = None, db=None) -> SSHClient:
    """
    根据 server_id 获取 SSH 连接，未指定则返回默认连接
    如果 server_id 存在但连接池里没有，从数据库获取服务器信息并建立连接
    """
    if server_id:
        client = SSH_POOL.get(server_id)
        if client and client.is_alive():
            return client
        # 如果连接不存在或断开了，从数据库获取服务器信息并建立新连接
        if db:
            from sqlalchemy import select
            from app.models.server import Server
            result = await db.execute(select(Server).where(Server.id == server_id))
            server = result.scalar_one_or_none()
            if server:
                return SSH_POOL.get_or_create(
                    server_id=server.id,
                    host=server.host,
                    port=server.port,
                    username=server.username,
                    key_path=server.key_path
                )
    return get_ssh_client()


def get_ssh_for_server_sync(server_id: str = None) -> SSHClient:
    """
    同步版本的获取 SSH 连接（用于不需要 db 的场景）
    """
    if server_id:
        client = SSH_POOL.get(server_id)
        if client and client.is_alive():
            return client
    return get_ssh_client()
