from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class MCPEnvelope(BaseModel):
    success: bool = True
    data: Dict[str, Any] | None = None
    error: str | None = None
    errorCode: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MCPToolDefinition(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any] = Field(default_factory=dict)


class MCPResourceDefinition(BaseModel):
    uri: str
    name: str
    description: str
    mimeType: str = "application/json"


class MCPPromptDefinition(BaseModel):
    name: str
    description: str
    arguments: List[Dict[str, Any]] = Field(default_factory=list)


class MCPContent(BaseModel):
    type: Literal["text"] = "text"
    text: str


class MCPToolResult(BaseModel):
    content: List[MCPContent]
    isError: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MCPErrorResponse(BaseModel):
    success: bool = False
    error: str
    errorCode: str = "MCP_ERROR"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MCPCallToolRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class MCPReadResourceRequest(BaseModel):
    uri: str


class MCPGetPromptRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
