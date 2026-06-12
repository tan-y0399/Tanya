# KylinOps Agent 人类监督分阶段流程

本文档描述已落地与规划中的分阶段流程，用于在**人类监督**下更安全地完成运维任务。

---

## 阶段 1：前端发起请求

| 步骤 | 实现状态 | 说明 |
|------|----------|------|
| 用户输入 / 快捷指令 | ✅ | `ChatPage.vue` |
| 前端预校验 | ✅ | `utils/chatValidate.ts`：空输入、>4096 字符、非法控制字符 |
| 统一入口 POST `/api/v1/chat/send` | ✅ | 携带 sessionId；JWT 含 user_id / role |
| SSE 连接 | ✅ | `api/chat.ts` |

---

## 阶段 2：全链路安全防护

### 步骤 1：入口安全预检（prompt_guard v2）

| 层级 | 实现状态 | 模块 |
|------|----------|------|
| 正则注入 + 高危命令嵌入 | ✅ | `prompt_guard.detect_injection` |
| LLM 辅助检测 | ✅ | `prompt_guard.llm_injection_check` |
| 角色权限预检 | ✅ | `human_supervision.role_blocks_l4_request` + `permission_service` |
| 拦截 → SSE → 终止 | ✅ | `prompt_injection_detected` |

### 步骤 2：并行【意图分类 + RAG】

| 输出 | 实现状态 |
|------|----------|
| intent + confidence | ✅ `intent_classifier` |
| RAG 片段 + sources | ✅ `knowledge_rag` |

### 步骤 3：注入二次复核（上下文感知）

| 检查项 | 实现状态 |
|--------|----------|
| 诱导绕过安全表述 | ✅ `context_injection_recheck` |
| RAG 中 Canary 异常 | ✅ |
| 不通过则终止 | ✅ |

---

## 阶段 3：路由分发

### 链路 A：general_qa / knowledge_qa

| 能力 | 实现状态 |
|------|----------|
| Handler 无工具回答 | ✅ `task_router` |
| 强制引用知识库来源 | ✅ KnowledgeQA 系统提示增强 |
| 禁止编造未检索内容 | ✅ 提示词约束 |

### 链路 B：ops_query / fault_analysis / high_risk（ReAct）

| 子步骤 | 实现状态 | 说明 |
|--------|----------|------|
| 诊断方案生成 | ✅ | `build_diagnostic_plan` + `diagnostic_plan` SSE |
| 用户确认方案 | ✅ | `DiagnosticPlanCard` → `confirmPlanId` |
| 环境预检 | ✅ | SSH 连通 + 磁盘；逻辑快照 ID |
| ReAct 闭环 | ✅ | 默认最多 5 轮 `react_max_rounds` |
| L1–L5 分级 | ✅ | `command_security` + `_check_tool_safety` |
| L2/L3 用户确认 | ✅ | `CommandConfirmCard` |
| L4 审批 + 用户执行确认 | ✅ | 审批管理 + `approved_run` 确认框 |
| L5 阻断 | ✅ | `blocked` 事件 |
| 命令超时 30s | ✅ | `tool_default_timeout=30` |
| 时间回溯/全量回滚 | ✅ 部分 | `POST /chat/sessions/{id}/rollback` |
| 磁盘清理执行防幻觉 | ✅ | `is_disk_cleanup_execution_request` → ReAct + L2-L4 分级 |
| 结构化运维报告 | ✅ | `build_structured_ops_report` 附录 |

---

## 阶段 4：审计与收尾

| 项 | 实现状态 |
|----|----------|
| AuditRecord 全链路 | ✅ |
| message_done.status | ✅ `completed` / `awaiting_approval` / `awaiting_plan_confirm` / `env_failed` 等 |
| 遥测 TraceTelemetry | ✅ |

---

## 阶段 5：用户反馈与知识迭代

| 项 | 实现状态 |
|----|----------|
| 解决 / 部分 / 未解决 | ✅ `TraceFeedbackBar` + `POST /chat/trace-outcome` |
| 未解决标记待专家 | ✅ `needs_expert=true` |
| 自动更新知识库 | 📋 规划 | 需专家审核后台对接 |

---

## 关键 API

```
POST /api/v1/chat/send
  body: { sessionId, content, serverId?, pendingApprovalId?, confirmPlanId? }

GET  /api/v1/chat/sessions/{id}/awaiting-run
POST /api/v1/chat/sessions/{id}/cancel-run
POST /api/v1/chat/trace-outcome
GET  /api/v1/chat/trace-outcome/stats  (admin)
```

---

## 相关代码

- `backend/app/services/human_supervision.py`
- `backend/app/services/chat_service.py`
- `backend/app/models/supervision.py`
- `frontend/src/views/ChatPage.vue`
- `docs/agent-workflow-overview.md`（总览图）
