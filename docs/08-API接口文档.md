# API 接口文档

> **项目名称**：面向麒麟操作系统的安全智能运维 Agent 设计与实现
> **版本**：V1.0&emsp;**日期**：2026-05-18&emsp;**编写**：项目组

---

## 1 概述

### 1.1 基础信息

| 项目 | 说明 |
|------|------|
| 基础路径 | `/api/v1` |
| 协议 | HTTPS（生产）/ HTTP（开发） |
| 数据格式 | JSON |
| 字符编码 | UTF-8 |
| 流式响应 | SSE (Server-Sent Events) |

### 1.2 认证方式

除登录和健康检查外，所有接口需携带 JWT Token：

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

Token 有效期：24 小时。过期后需重新登录。

### 1.3 通用响应格式

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": { ... },
  "traceId": "trace-20260518T103000-a1b2c3d4"
}
```

**错误响应**：

```json
{
  "code": 1001,
  "message": "工具执行超时",
  "traceId": "trace-20260518T103000-a1b2c3d4"
}
```

### 1.4 错误码定义

| 错误码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1001 | 参数校验失败 |
| 1002 | 资源不存在 |
| 1003 | 未授权（Token 无效或过期） |
| 1004 | 权限不足 |
| 2001 | 模型 API 调用失败 |
| 2002 | 模型 API 超时 |
| 3001 | 工具未注册 |
| 3002 | 工具执行超时 |
| 3003 | 工具执行失败 |
| 4001 | 安全规则拦截 |
| 4002 | 需要审批 |
| 4003 | 审批已超时 |
| 5001 | 服务器内部错误 |

---

## 2 认证模块

### 2.1 用户登录

```
POST /api/v1/auth/login
```

**请求**：

```json
{
  "username": "admin",
  "password": "admin123"
}
```

**响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "accessToken": "eyJhbGciOi...",
    "tokenType": "Bearer",
    "expiresIn": 86400,
    "user": {
      "id": "user-001",
      "username": "admin",
      "role": "admin"
    }
  },
  "traceId": "trace-xxx"
}
```

### 2.2 退出登录

```
POST /api/v1/auth/logout
```

**请求头**：`Authorization: Bearer <token>`

**响应**：

```json
{
  "code": 0,
  "message": "退出成功"
}
```

### 2.3 获取当前用户信息

```
GET /api/v1/auth/me
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "id": "user-001",
    "username": "admin",
    "role": "admin"
  }
}
```

---

## 3 会话与对话模块

### 3.1 获取会话列表

```
GET /api/v1/chat/sessions?page=1&size=20
```

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码，默认 1 |
| size | integer | 否 | 每页条数，默认 20 |

**响应**：

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "sess-001",
        "title": "磁盘巡检对话",
        "createdAt": "2026-05-18T10:00:00Z",
        "updatedAt": "2026-05-18T10:30:00Z",
        "messageCount": 12
      }
    ],
    "total": 5,
    "page": 1,
    "size": 20
  }
}
```

### 3.2 创建新会话

```
POST /api/v1/chat/sessions
```

**请求**：

```json
{
  "title": "新会话"
}
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "id": "sess-002",
    "title": "新会话",
    "createdAt": "2026-05-18T11:00:00Z"
  }
}
```

### 3.3 删除会话

```
DELETE /api/v1/chat/sessions/{sessionId}
```

**响应**：

```json
{
  "code": 0,
  "message": "删除成功"
}
```

### 3.4 获取会话消息列表

```
GET /api/v1/chat/sessions/{sessionId}/messages?page=1&size=50
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "msg-001",
        "role": "user",
        "content": "帮我看看磁盘使用情况",
        "createdAt": "2026-05-18T10:00:00Z"
      },
      {
        "id": "msg-002",
        "role": "assistant",
        "content": "正在查询系统磁盘使用情况...",
        "toolCalls": [
          {
            "id": "tc-001",
            "toolName": "get_disk_usage",
            "params": {},
            "riskLevel": "L1"
          }
        ],
        "traceId": "trace-xxx",
        "createdAt": "2026-05-18T10:00:02Z"
      },
      {
        "id": "msg-003",
        "role": "assistant",
        "content": "磁盘使用情况如下：\n- /dev/sda1: 使用率 78% (已用 78G/100G)\n- /dev/sdb1: 使用率 45% (已用 225G/500G)\n\n/var/log 目录占用了约 12G 空间，建议清理 30 天前的旧日志。",
        "createdAt": "2026-05-18T10:00:05Z"
      }
    ],
    "total": 3
  }
}
```

### 3.5 发送消息（SSE 流式）

```
POST /api/v1/chat/send
```

**请求**：

```json
{
  "sessionId": "sess-001",
  "content": "清理 /var/log 下 30 天前的日志"
}
```

**响应**：SSE 流式推送

```
event: message_start
data: {"messageId":"msg-004","traceId":"trace-yyy"}

event: token
data: {"token":"好的"}

event: token
data: {"token":"，"}

event: tool_call
data: {"toolName":"clean_old_logs","params":{"log_dir":"/var/log","days_old":30},"status":"executing","riskLevel":"L2"}

event: approval_required
data: {"approvalId":"apv-001","toolName":"clean_old_logs","riskLevel":"L2","detail":"将执行: find /var/log -mtime +30 -name '*.log' -delete"}

event: approval_result
data: {"approvalId":"apv-001","result":"approved","approver":"admin"}

event: tool_result
data: {"toolName":"clean_old_logs","status":"completed","result":{"success":true,"data":{"cleanedCount":15,"freedBytes":"2.3G"}}}

event: token
data: {"token":"清理完成"}

event: message_done
data: {"messageId":"msg-004","traceId":"trace-yyy","usage":{"inputTokens":800,"outputTokens":300}}
```

**SSE 事件类型说明**：

| 事件类型 | 说明 |
|----------|------|
| `message_start` | 消息开始，返回 messageId + traceId |
| `token` | LLM 输出 token（逐字流式） |
| `tool_call` | 工具调用请求 |
| `approval_required` | 需要审批 |
| `approval_result` | 审批结果 |
| `tool_result` | 工具执行结果 |
| `error` | 错误发生 |
| `message_done` | 消息完成 |

---

## 4 审计模块

### 4.1 查询审计日志

```
GET /api/v1/audit/records?page=1&size=20&userId=admin&eventType=TOOL_EXECUTION&startTime=2026-05-01&endTime=2026-05-18
```

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码 |
| size | integer | 否 | 每页条数 |
| userId | string | 否 | 过滤用户 |
| eventType | string | 否 | 事件类型：LLM_CALL / TOOL_EXECUTION / APPROVAL / SECURITY_CHECK |
| riskLevel | string | 否 | 风险等级：L1 / L2 / L3 / L4 |
| startTime | string | 否 | 开始时间（ISO 8601） |
| endTime | string | 否 | 结束时间（ISO 8601） |
| traceId | string | 否 | 精确搜索 traceId |

**响应**：

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "audit-001",
        "traceId": "trace-xxx",
        "timestamp": "2026-05-18T10:30:00Z",
        "userId": "admin",
        "eventType": "TOOL_EXECUTION",
        "summary": "执行 clean_old_logs 清理 /var/log 旧日志",
        "riskLevel": "L2",
        "exitCode": 0
      }
    ],
    "total": 42,
    "page": 1,
    "size": 20
  }
}
```

### 4.2 获取审计记录详情

```
GET /api/v1/audit/records/{traceId}
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "traceId": "trace-xxx",
    "sessionId": "sess-001",
    "events": [
      {
        "sequence": 1,
        "timestamp": "2026-05-18T10:30:00.000Z",
        "eventType": "USER_MESSAGE",
        "data": {
          "content": "清理 /var/log 下 30 天前的日志"
        }
      },
      {
        "sequence": 2,
        "timestamp": "2026-05-18T10:30:01.000Z",
        "eventType": "LLM_CALL",
        "data": {
          "model": "qwen-plus",
          "inputTokens": 500,
          "outputTokens": 100,
          "reasoning": "用户要求清理旧日志，调用 clean_old_logs 工具..."
        }
      },
      {
        "sequence": 3,
        "timestamp": "2026-05-18T10:30:01.500Z",
        "eventType": "SECURITY_CHECK",
        "data": {
          "staticGuard": "PASSED",
          "intentAlignment": { "score": 0.95, "aligned": true },
          "riskLevel": "L2"
        }
      },
      {
        "sequence": 4,
        "timestamp": "2026-05-18T10:30:02.000Z",
        "eventType": "APPROVAL",
        "data": {
          "required": true,
          "approver": "admin",
          "result": "APPROVED"
        }
      },
      {
        "sequence": 5,
        "timestamp": "2026-05-18T10:30:03.000Z",
        "eventType": "TOOL_EXECUTION",
        "data": {
          "command": "find /var/log -mtime +30 -name '*.log' -delete",
          "exitCode": 0,
          "duration": 1234
        }
      }
    ]
  }
}
```

---

## 5 审批模块

### 5.1 获取待审批列表

```
GET /api/v1/approval/pending
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "apv-001",
        "traceId": "trace-xxx",
        "sessionId": "sess-001",
        "toolName": "restart_service",
        "toolParams": { "service_name": "nginx" },
        "riskLevel": "L3",
        "detail": "将执行 systemctl restart nginx",
        "requestedBy": "admin",
        "requestedAt": "2026-05-18T10:30:00Z",
        "expiresAt": "2026-05-18T10:31:00Z"
      }
    ],
    "total": 1
  }
}
```

### 5.2 审批通过

```
POST /api/v1/approval/{approvalId}/approve
```

**请求**：

```json
{
  "comment": "确认需要重启"
}
```

**响应**：

```json
{
  "code": 0,
  "message": "审批通过，操作已执行"
}
```

### 5.3 审批拒绝

```
POST /api/v1/approval/{approvalId}/reject
```

**请求**：

```json
{
  "reason": "当前不是重启时机"
}
```

**响应**：

```json
{
  "code": 0,
  "message": "审批拒绝"
}
```

---

## 6 系统管理模块

### 6.1 健康检查

```
GET /api/v1/system/health
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "status": "healthy",
    "version": "1.0.0",
    "components": {
      "database": { "status": "up", "latencyMs": 2 },
      "llmApi": { "status": "up", "latencyMs": 150 },
      "mcpServers": {
        "system-info": { "status": "up", "port": 9101 },
        "logs": { "status": "up", "port": 9102 },
        "actions": { "status": "up", "port": 9103 }
      }
    }
  }
}
```

### 6.2 获取系统配置

```
GET /api/v1/system/config
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "llm": {
      "model": "qwen-plus",
      "apiBase": "https://api.example.com/v1",
      "temperature": 0.1,
      "maxTokens": 4096
    },
    "tool": {
      "defaultTimeout": 60,
      "enabledTools": ["get_cpu_info","get_memory_info","get_disk_usage","list_processes","search_journal_logs","restart_service","clean_old_logs"]
    },
    "security": {
      "approvalTimeout": 60,
      "maxConversationRounds": 20
    }
  }
}
```

### 6.3 更新系统配置

```
PUT /api/v1/system/config
```

**请求**：

```json
{
  "llm": {
    "temperature": 0.2
  },
  "tool": {
    "defaultTimeout": 90
  }
}
```

**响应**：

```json
{
  "code": 0,
  "message": "配置已更新"
}
```

---

## 7 MCP 工具接口（内部）

### 7.1 工具列表

Agent 通过 MCP 协议 `tools/list` 获取可用工具：

```json
{
  "tools": [
    {
      "name": "get_disk_usage",
      "description": "查询磁盘使用情况，返回各挂载点的容量、已用、可用和百分比",
      "inputSchema": {
        "type": "object",
        "properties": {
          "mount_point": {
            "type": "string",
            "description": "指定挂载点，留空则查询全部"
          }
        }
      }
    }
  ]
}
```

### 7.2 工具调用

Agent 通过 MCP 协议 `tools/call` 调用工具：

```json
// 请求
{
  "name": "get_disk_usage",
  "arguments": { "mount_point": "/var" }
}

// 响应
{
  "content": [
    {
      "type": "text",
      "text": "{\"success\":true,\"data\":[{\"mount\":\"/var\",\"total\":\"50G\",\"used\":\"30G\",\"available\":\"20G\",\"percent\":\"60%\"}]}"
    }
  ]
}
```

---

## 8 错误处理最佳实践

1. **错误体统一**：所有错误响应遵循 `{ code, message, traceId }` 结构
2. **TraceId 必带**：错误响应也需携带 traceId，方便后端日志关联排查
3. **前端处理**：
   - 401 → 跳转登录页
   - 403 → 提示权限不足
   - 4xx → 展示错误信息，不重试
   - 5xx → 展示错误信息 + "重试"按钮
   - 网络错误 → "连接失败，请检查网络" + 重试按钮
4. **SSE 错误**：通过 `error` 事件推送，格式 `{"code": 3002, "message": "工具执行超时"}`
