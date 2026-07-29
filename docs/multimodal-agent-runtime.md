# 多模态多 Agent 运行配置

## 外部资料专家

真实 API Key 只写入 `backend/.env`，不要提交到仓库。

```env
ENABLE_WEB_RESEARCH=true
WEB_SEARCH_PROVIDER=baidu
BAIDU_SEARCH_API_URL=
BAIDU_SEARCH_API_KEY=
BAIDU_SEARCH_SECRET_KEY=
```

如果不是百度搜索 API，也可以改为通用 HTTP 搜索：

```env
WEB_SEARCH_PROVIDER=generic
WEB_SEARCH_API_URL=
WEB_SEARCH_API_KEY=
WEB_SEARCH_SECRET_KEY=
```

## drawio MCP

可在本地 MCP 配置中增加：

```json
{
  "mcpServers": {
    "drawio": {
      "command": "npx",
      "args": ["@next-ai-drawio/mcp-server@latest"]
    }
  }
}
```

后端当前通过 `MCP_SERVER_URL` 访问 MCP 网关；如果 MCP 不可用，会回退为 Mermaid 流程图。

## PaddleOCR-VL

模型建议下载到：

```text
backend/models/PaddleOCR-VL-1.6
```

下载脚本：

```powershell
.\scripts\download_paddleocr_vl.ps1
```

## ModelScope 图片生成与 TTS

```env
MODELSCOPE_API_KEY=
MODELSCOPE_API_BASE=https://api-inference.modelscope.cn/v1
IMAGE_GENERATION_MODEL=Z-Image-Turbo
TTS_MODEL=Qwen3-TTS-12Hz-1.7B-VoiceDesign
```
