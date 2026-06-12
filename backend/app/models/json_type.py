"""兼容 SQLite 与 PostgreSQL(JSONB) 的 JSON 列类型。"""

import json
from typing import Any

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator


class JSONType(TypeDecorator):
    """写入时自动解析 JSON 字符串；读取时统一返回 JSON 字符串，兼容现有 json.loads 调用。"""

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Any, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value

    def process_result_value(self, value: Any, dialect):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return value
