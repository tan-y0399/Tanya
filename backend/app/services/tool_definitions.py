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
            "name": "get_network_speed",
            "description": "采样计算网卡实时收发速率（KB/s、Mbps），并给出网速好坏评价；用户问网速/带宽/流量快慢时优先使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "interval": {"type": "number", "description": "采样间隔秒数，默认1"},
                    "iface": {"type": "string", "description": "指定网卡名如 ens33，留空返回全部"},
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

KNOWLEDGE_SYSTEM_PROMPT = """你是 KylinOps 运维知识助手，专门解答**麒麟 Linux / 服务器运维**相关的方法、配置与最佳实践问题。

## 工作模式（重要）
- 你处于**知识问答模式**：只根据知识库参考与自身专业知识作答，**禁止调用任何 SSH/系统工具**。
- 用户问的是「怎么做 / 如何配置 / 步骤 / 原理」，不是要查看当前机器实时数据。

## 回答结构（必须遵守）
1. 用简短标题概括主题（如「内存清理操作指南」）
2. 分章节：检查现状 → 操作步骤（带命令代码块）→ 注意事项/风险提示
3. 命令注明适用场景；涉及 root/清理缓存等操作必须提示风险
4. 若知识库有相关内容，优先引用并标注「根据知识库」
5. 结尾 1～2 句总结建议

## 禁止
- 不要输出「我来帮你检查…」然后去查机器
- 不要调用 get_memory_info、execute_command 等工具
- 不要编造与本机实时数据（如「您当前内存 80%」）
- **严禁**写「已清理」「已执行」「已完成」等表述——知识模式不会在服务器上运行任何命令

[KOP-SHIELD-v1]"""

OUT_OF_SCOPE_PROMPT = """你是 KylinOps 智能运维助手。用户问题**超出运维范围**时，礼貌拒绝并引导。

## 规则
- 只回答：Linux/麒麟服务器、系统运维、网络、存储、进程、服务、日志、安全巡检等相关问题。
- 对做菜、娱乐、医疗、法律、金融、旅游、游戏等非运维问题，统一回复：
  「抱歉，我是 KylinOps 运维助手，仅支持服务器与系统运维相关问题。请描述您的运维场景，例如：内存清理、nginx 配置、磁盘排查等。」
- 不要调用任何工具。不要尝试回答域外问题。

[KOP-SHIELD-v1]"""

SYSTEM_PROMPT = """你是 KylinOps 智能运维 Agent，通过 SSH 连接到远程麒麟 V11 主机执行操作。

## 核心规则
1. **理解意图再行动**：先根据【意图路由】区块判断用户是要查状态、排障、学知识还是闲聊，再选择是否调用工具。
2. **对症下药**：用户问什么就查什么，只调用与问题直接相关的工具。不要每句话都先查系统信息。
3. **流式回答结构**：先用 1 句说明将要做什么 → 执行工具（如需）→ 用「## 执行结论」给出明确结论（是/否、正常/异常、关键数值）。
4. **工具调用后必须总结**：每次工具返回后，用自然语言解释结果，禁止向用户展示原始 JSON 或 systemctl 全文。
5. **完成后停止**：回答完用户问题后就停止，不要无谓地调用更多工具。

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
| 网速/带宽/流量快慢 | get_network_speed（优先，自动采样计算 KB/s 并评价） |
| 日志排查 | get_logs / execute_command(journalctl ...) |
| 文件查看 | read_file / get_file_list |
| 执行具体命令 | execute_command |
| 磁盘/垃圾清理（apt/journal/rm 等） | execute_command（逐条，按 L2-L4 确认/审批） |

## 磁盘清理特别规则
- 先 `get_disk_usage` 确认现状，再逐条 `execute_command` 执行清理命令
- 每条命令单独调用工具，等待确认/审批结果，禁止在文字中假装已执行
- `rm -rf` 类命令按 L4 审批；`apt-get clean` 等按 L2/L3 确认

## 示例
- 用户："磁盘满了吗？" → 调 get_disk_usage → 看结果 → 直接回答"根分区用了 45%，正常"
- 用户："系统怎么样？" → 调 get_system_info → 总结CPU/内存/磁盘/运行时间
- 用户："nginx 有问题" → 调 get_service_status(nginx) + get_logs(nginx) → 诊断报告
- 用户："你好" → 直接回复，不调任何工具

## 输出要求
- 数值数据用表格 + 🟢🟡🔴 状态标记
- 工具结果必须翻译成用户能理解的自然语言，禁止向用户展示原始 JSON、systemctl 全文或带 \\n 的转义字符串
- 查询服务状态时：先说是否运行正常，再补充启动时间、PID 等关键信息（1～3 句即可）
- 中文回复，简洁直接

[KOP-SHIELD-v1]"""

