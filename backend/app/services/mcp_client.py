"""
MCP 客户端 — Model Context Protocol 工具调用

MCP (Model Context Protocol) 标准化 AI-工具通信:
  - 工具发现 (list_tools)
  - 工具调用 (call_tool)
  - 资源访问 (read_resource)
  - 提示词模板 (get_prompt)

集成到现有的 tool_execution_node 中。
"""

import json
import logging
import httpx
from typing import Dict, List, Optional, Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCP 协议客户端。

    支持两种传输方式:
      - HTTP/SSE (默认)
      - Stdio (本地进程通信)
    """

    def __init__(self, server_url: Optional[str] = None):
        self.server_url = server_url or getattr(settings, 'mcp_server_url', 'http://localhost:8100')
        self._tools_cache: Optional[List[Dict]] = None

    async def list_tools(self) -> List[Dict]:
        """发现可用工具"""
        if self._tools_cache:
            return self._tools_cache

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.server_url}/mcp/list_tools",
                    json={"method": "tools/list", "params": {}},
                )
                resp.raise_for_status()
                data = resp.json()
                self._tools_cache = data.get("tools", [])
                logger.info(f"MCP: 发现 {len(self._tools_cache)} 个工具")
                return self._tools_cache
        except Exception as e:
            logger.warning(f"MCP工具发现失败: {e}，使用本地工具注册表")
            return self._get_local_tools()

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict:
        """通过MCP协议调用工具"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.server_url}/mcp/call_tool",
                    json={
                        "method": "tools/call",
                        "params": {
                            "name": tool_name,
                            "arguments": arguments,
                        },
                    },
                )
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"MCP调用成功: {tool_name}")
                return {"success": True, "data": result.get("content", result), "via": "mcp"}
        except Exception as e:
            logger.warning(f"MCP调用失败 {tool_name}: {e}，降级到直接执行")
            return await self._fallback_execute(tool_name, arguments)

    async def _fallback_execute(self, tool_name: str, arguments: Dict) -> Dict:
        """MCP不可用时降级到本地执行"""
        from app.services.remote_executor import execute_tool
        return execute_tool(tool_name, **arguments)

    def _get_local_tools(self) -> List[Dict]:
        """获取本地工具描述（MCP不可用时的降级方案）"""
        from app.services.tool_definitions import TOOLS
        return [
            {
                "name": t.get("function", {}).get("name", ""),
                "description": t.get("function", {}).get("description", ""),
                "parameters": t.get("function", {}).get("parameters", {}),
            }
            for t in TOOLS
        ]

    def clear_cache(self):
        """清除工具缓存"""
        self._tools_cache = None


# 全局单例
mcp_client = MCPClient()


async def mcp_execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> Dict:
    """统一工具执行入口：优先MCP，降级直接执行"""
    return await mcp_client.call_tool(tool_name, tool_args)


async def mcp_discover_tools() -> List[Dict]:
    """发现可用工具"""
    return await mcp_client.list_tools()
