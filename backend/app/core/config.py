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
    llm_system_role_support: bool = True

    # 安全
    approval_timeout: int = 120
    max_conversation_rounds: int = 20
    react_max_rounds: int = 5
    max_user_input_length: int = 8192
    tool_default_timeout: int = 30
    enable_diagnostic_plan: bool = True
    workflow_lightweight_confidence: float = 0.9
    workflow_plan_confidence: float = 0.7
    approval_timeout_hours: int = 24
    command_max_retries: int = 2
    network_retry_interval_sec: int = 5
    # True 时 POST /chat/send 走 LangGraph 编排；False 走 chat_service（默认，功能更完整）
    use_langgraph_orchestrator: bool = False
    enable_multimodal_agent: bool = True
    vision_llm_api_base: str = ""
    vision_llm_api_key: str = ""
    vision_llm_model: str = ""
    enable_web_research: bool = False
    web_search_provider: str = "generic"
    web_search_api_url: str = ""
    web_search_api_key: str = ""
    web_search_secret_key: str = ""
    baidu_search_api_url: str = ""
    baidu_search_api_key: str = ""
    baidu_search_secret_key: str = ""
    modelscope_api_key: str = ""
    modelscope_api_base: str = "https://api-inference.modelscope.cn/v1"
    image_generation_model: str = "Tongyi-MAI/Z-Image-Turbo"
    flowchart_generation_model: str = "Tongyi-MAI/Z-Image-Turbo"
    flowchart_generation_provider: str = "zimage"
    tts_model: str = "Qwen3-TTS-12Hz-1.7B-VoiceDesign"
    tts_api_url: str = ""
    tts_voice: str = "Cherry"
    tts_voice_prompt: str = "磁性的女性播音员声音，语速适中，音量适中，表达清晰稳重，适合专业运维讲解。"
    dashscope_api_key: str = ""
    paddleocr_vl_model_dir: str = "models/PaddleOCR-VL-1.6"
    paddleocr_model: str = "PaddlePaddle/PP-OCRv5_server_det"
    paddleocr_api_url: str = ""
    paddleocr_mcp_tool: str = "paddleocr_ocr"
    image_review_min_score: float = 0.18
    image_review_soft_min_score: float = 0.06
    image_review_keep_min: int = 1
    image_review_max_candidates: int = 4
    image_review_total_timeout_sec: float = 5.0
    image_review_ocr_timeout_sec: float = 3.0
    generated_asset_dir: str = "data/generated_assets"
    mcp_server_url: str = "http://localhost:8100"

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
    ssh_user: str = "ty"
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
