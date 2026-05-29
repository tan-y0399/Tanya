import os
from typing import List

import pydantic
# pydantic_settings 需要 pydantic v2，pydantic v1 用自带的 BaseSettings
if pydantic.__version__.startswith("2"):
    from pydantic_settings import BaseSettings
else:
    from pydantic import BaseSettings
from pydantic import Field

# 项目根目录（backend/app/core/config.py → backend/）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DB_DIR = os.path.join(_PROJECT_ROOT, "data")
_DB_PATH = os.path.join(_DB_DIR, "kylinops.db")
os.makedirs(_DB_DIR, exist_ok=True)


class Settings(BaseSettings):
    if pydantic.__version__.startswith("2"):
        model_config = {
            "env_file": os.path.join(_PROJECT_ROOT, ".env"),
            "extra": "ignore",
            "env_file_encoding": "utf-8",
        }
    else:
        class Config:
            env_file = os.path.join(_PROJECT_ROOT, ".env")
            env_file_encoding = "utf-8"

    app_name: str = "KylinOps Agent"
    version: str = "1.0.0"
    debug: bool = True

    # SQLite（绝对路径，不受启动目录影响）
    database_url: str = f"sqlite+aiosqlite:///{_DB_PATH}"

    # JWT
    jwt_secret: str = Field(default="change-me-in-production", env="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # LLM API
    llm_api_base: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096

    # 安全
    approval_timeout: int = 120
    max_conversation_rounds: int = 20
    tool_default_timeout: int = 60

    # SMTP
    smtp_host: str = "smtp.qq.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "KylinOps 运维平台"

    dev_mode: bool = True

    # SSH
    ssh_host: str = "192.168.163.15"
    ssh_port: int = 22
    ssh_user: str = "root"
    ssh_key_path: str = "~/.ssh/id_rsa"
    ssh_timeout: int = 15

    # CORS — 支持局域网访问（多个IP段 + localhost）
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])

    # 服务绑定地址（0.0.0.0 表示接受所有网络接口的请求，局域网可访问）
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # 微信开放平台
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_redirect_uri: str = "http://localhost:5173/auth/wechat/callback"



settings = Settings()
