from typing import Optional
from pydantic import BaseModel


class LLMConfig(BaseModel):
    model: str = "qwen-plus"
    apiBase: str = ""
    temperature: float = 0.1
    maxTokens: int = 4096


class ToolConfig(BaseModel):
    defaultTimeout: int = 60
    enabledTools: list = []


class SecurityConfig(BaseModel):
    approvalTimeout: int = 60
    maxConversationRounds: int = 20


class ConfigData(BaseModel):
    llm: LLMConfig
    tool: ToolConfig
    security: SecurityConfig


class ConfigUpdateRequest(BaseModel):
    llm: Optional[dict] = None
    tool: Optional[dict] = None
    security: Optional[dict] = None
