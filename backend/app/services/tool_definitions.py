"""工具定义和系统提示词 —— 供 Agent 使用"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "获取系统概览信息，包括CPU、内存、磁盘、系统版本等",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_disk_usage",
            "description": "查询磁盘挂载和使用情况",
            "parameters": {
                "type": "object",
                "properties": {
                    "mount_point": {"type": "string", "description": "指定挂载点路径，留空查询全部"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cpu_info",
            "description": "获取CPU使用率、核心数、负载等信息",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_memory_info",
            "description": "获取内存和交换区使用情况",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_processes",
            "description": "获取进程列表，可按CPU或内存排序",
            "parameters": {
                "type": "object",
                "properties": {
                    "sort_by": {"type": "string", "enum": ["cpu", "mem"], "description": "排序字段"},
                    "limit": {"type": "integer", "description": "返回数量，默认10"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_process_detail",
            "description": "获取指定进程的详细信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "pid": {"type": "integer", "description": "进程ID"},
                },
                "required": ["pid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kill_process",
            "description": "终止指定进程，默认发送TERM信号",
            "parameters": {
                "type": "object",
                "properties": {
                    "pid": {"type": "integer", "description": "进程ID"},
                    "signal": {"type": "string", "description": "信号类型，如TERM、KILL，默认TERM"},
                },
                "required": ["pid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_network_connections",
            "description": "查询网络连接状态和监听端口",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {"type": "string", "description": "连接状态过滤: LISTEN, ESTABLISHED 等"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_service_status",
            "description": "获取指定系统服务的状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string", "description": "服务名称"},
                },
                "required": ["service_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_service",
            "description": "管理系统服务：启动、停止、重启、重载",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string", "description": "服务名称"},
                    "action": {"type": "string", "enum": ["start", "stop", "restart", "reload"], "description": "操作类型"},
                },
                "required": ["service_name", "action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_list",
            "description": "获取指定目录的文件列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径，默认为当前目录"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定文件的内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径"},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_journal_logs",
            "description": "搜索系统日志",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "服务名过滤，如 nginx, mysql"},
                    "priority": {"type": "string", "enum": ["err", "warning", "info"], "description": "日志级别"},
                    "lines": {"type": "integer", "description": "返回行数，默认20"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_users",
            "description": "获取系统用户列表",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_groups",
            "description": "获取系统用户组列表",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "在远程系统上执行shell命令。⚠ 高危操作，需经过安全检查",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的shell命令"},
                    "timeout": {"type": "integer", "description": "命令超时秒数，默认30"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_task",
            "description": "总结当前任务，结束对话，提供最终报告",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "任务总结内容"},
                },
                "required": [],
            },
        },
    },
]

SYSTEM_PROMPT = """你是 KylinOps 智能运维 Agent，通过 SSH 连接到远程麒麟 V11 主机执行操作。

## 核心规则
1. **对症下药**：用户问什么就查什么，只调用与问题直接相关的工具。不要每句话都先查系统信息。
2. **先回答再扩展**：先直接回答用户的问题，如果数据不够再调用工具获取。
3. **工具调用后必须总结**：每次工具返回结果后，你必须用自然语言把结果解释给用户，不要只丢原始数据。
4. **完成后停止**：回答完用户问题后就停止，不要无谓地调用更多工具。

## 何时用什么工具
| 用户关心的内容 | 应使用的工具 |
|-------------|------------|
| 磁盘空间/使用率 | get_disk_usage |
| CPU/负载 | get_cpu_info |
| 内存 | get_memory_info |
| 进程 | list_processes / get_process_detail |
| 服务状态 | get_service_status |
| 系统整体概况 | get_system_info |
| 网络/端口 | get_network_connections |
| 日志排查 | get_logs / execute_command(journalctl ...) |
| 文件查看 | read_file / get_file_list |
| 执行具体命令 | execute_command |

## 示例
- 用户："磁盘满了吗？" → 调 get_disk_usage → 看结果 → 直接回答"根分区用了 45%，正常"
- 用户："系统怎么样？" → 调 get_system_info → 总结CPU/内存/磁盘/运行时间
- 用户："nginx 有问题" → 调 get_service_status(nginx) + get_logs(nginx) → 诊断报告
- 用户："你好" → 直接回复，不调任何工具

## 输出要求
- 数值数据用表格 + 🟢🟡🔴 状态标记
- 工具结果必须翻译成用户能理解的自然语言
- 中文回复，简洁直接

[KOP-SHIELD-v1]"""

