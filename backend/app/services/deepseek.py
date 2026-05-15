import httpx

from app.core.config import settings


class DeepSeekAgent:
    def __init__(self) -> None:
        self.api_key = settings.deepseek_api_key
        self.base_url = settings.deepseek_base_url.rstrip('/')
        self.model = settings.deepseek_model

    def plan(self, message: str) -> list[dict[str, str]]:
        lowered = message.lower()
        if any(keyword in lowered for keyword in ['日志', 'log', '异常']):
            return [
                {'name': 'search_logs', 'status': 'planned', 'description': '查询近期日志并筛选异常关键字'},
            ]
        if any(keyword in lowered for keyword in ['磁盘', 'disk', 'cpu', '内存', 'memory']):
            return [
                {'name': 'get_system_metrics', 'status': 'planned', 'description': '获取系统资源使用情况'},
            ]
        return [
            {'name': 'chat_only', 'status': 'planned', 'description': '仅进行自然语言回复'},
        ]

    def chat(self, message: str) -> str:
        if not self.api_key:
            return f'DeepSeek 未配置，当前为本地降级回复：{message}'

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': '你是麒麟操作系统安全智能运维助手。'},
                {'role': 'user', 'content': message},
            ],
        }

        try:
            response = httpx.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception as exc:
            return f'DeepSeek 调用失败，已降级：{exc}'
