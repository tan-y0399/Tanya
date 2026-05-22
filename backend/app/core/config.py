try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "KylinOps Agent"
    version: str = "1.0.0"
    debug: bool = True

    # PostgreSQL 数据库
    database_url: str = "postgresql+asyncpg://postgres:Aa10154650%21@127.0.0.1:5432/yunwei"
    audit_database_url: str = "postgresql+asyncpg://postgres:Aa10154650%21@127.0.0.1:5432/yunwei"

    # JWT
    jwt_secret: str = "kylinops-jwt-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # DeepSeek API
    llm_api_base: str = "https://api.deepseek.com/v1"
    llm_api_key: str = "sk-492fa8a2578e43c88bac175fdad9fbfb"
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096

    # 安全
    approval_timeout: int = 60
    max_conversation_rounds: int = 20
    tool_default_timeout: int = 60

    # SMTP 邮件
    smtp_host: str = "smtp.qq.com"
    smtp_port: int = 587
    smtp_username: str = "3325519906@qq.com"
    smtp_password: str = "lpzikfyzsqlycijb"
    smtp_from_name: str = "KylinOps 运维平台"

    # 开发模式：true 时 API 返回验证码明文（生产环境必须 false）
    dev_mode: bool = True

    # SSH 默认连接
    ssh_host: str = "192.168.163.15"
    ssh_port: int = 22
    ssh_user: str = "root"
    ssh_key_path: str = "~/.ssh/id_rsa"
    ssh_timeout: int = 15

    # CORS
    cors_origins: list = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # 微信开放平台（网站应用扫码登录）
    wechat_app_id: str = "wxe84872fe9405e272"
    wechat_app_secret: str = "e97c805b2b2fb425d813746129909650"
    wechat_redirect_uri: str = "http://localhost:5173/auth/wechat/callback"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
