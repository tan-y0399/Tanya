/** 各审计 Tab / 事件类型的流程节点与模块说明 */

import type { AuditEventType, AuditRecordItem } from './auditEventMeta'
import { eventLabel } from './auditEventMeta'

export interface TabHubConfig {
  tag: string
  title: string
  desc: string
  color: string
  cards: Array<{ code: string; label: string; desc: string; flow: string[] }>
}

export interface AuditFlowNode {
  id: string
  label: string
  sublabel: string
  status: 'passed' | 'blocked' | 'pending' | 'idle' | 'warning'
  detail?: string
}

export const EVENT_COLORS: Record<string, string> = {
  chat: '#2563eb',
  blocked_injection: '#dc2626',
  chat_resume: '#7c3aed',
  workflow: '#0891b2',
  default: '#64748b',
}

export const TAB_HUB: Record<string, TabHubConfig> = {
  '': {
    tag: 'AUDIT-ALL',
    title: '全链路审计视图',
    desc: '聚合 Agent 对话、安全拦截、审批恢复与安全流程记录，支持 TraceId 回溯与执行回放',
    color: '#2563eb',
    cards: [
      { code: 'CHAT', label: 'Agent 对话', desc: '完整推理与工具调用链', flow: ['输入', '预检', '执行', '回复'] },
      { code: 'BLOCK', label: '安全拦截', desc: 'L5 注入与高危命令阻断', flow: ['输入', '检测', '阻断'] },
      { code: 'RESUME', label: '审批恢复', desc: 'L4 审批后用户确认执行', flow: ['审批', '确认', '执行'] },
    ],
  },
  chat: {
    tag: 'MOD-CHAT',
    title: 'Agent 对话审计',
    desc: '记录用户提问、意图识别、工具调用与 Agent 回复的全链路 telemetry',
    color: '#2563eb',
    cards: [
      { code: 'STEP-1', label: '安全预检', desc: '注入检测 + 角色校验', flow: ['预检', '意图', 'RAG'] },
      { code: 'STEP-2', label: 'ReAct 执行', desc: '工具调用与风险分级', flow: ['路由', '工具', '结论'] },
      { code: 'STEP-3', label: '审计归档', desc: 'TraceId 持久化', flow: ['写入', '回放'] },
    ],
  },
  blocked_injection: {
    tag: 'MOD-BLOCK',
    title: '安全拦截审计',
    desc: '提示词注入、诱导绕过等在入口安全闸门被阻断的请求（不含已进入 Agent 的 L5 审批命令）',
    color: '#dc2626',
    cards: [
      { code: 'L5', label: '注入检测', desc: '正则 + LLM 双层检测', flow: ['预检', '复核', '阻断'] },
      { code: 'CANARY', label: '上下文复核', desc: 'RAG / 诱导短语检测', flow: ['意图', '复核'] },
      { code: 'AUDIT', label: '拦截留痕', desc: '独立 event_type 归档', flow: ['记录', '告警'] },
    ],
  },
  chat_resume: {
    tag: 'MOD-RESUME',
    title: '审批恢复审计',
    desc: 'L4 高危操作经管理员审批后，由用户在对话页确认执行的恢复链路',
    color: '#7c3aed',
    cards: [
      { code: 'L4', label: '审批通过', desc: '管理员审批链', flow: ['申请', '审批'] },
      { code: 'USER', label: '用户确认', desc: '对话页二次确认', flow: ['确认', '执行'] },
      { code: 'DONE', label: '执行归档', desc: '工具结果写入审计', flow: ['工具', '结论'] },
    ],
  },
}

export function eventColor(type: string): string {
  return EVENT_COLORS[type] || EVENT_COLORS.default
}

export function sectionTitle(tab: string): string {
  if (tab === 'workflow') return '安全流程链路图'
  if (tab === 'chat') return 'Agent 对话时间线'
  if (tab === 'blocked_injection') return '安全拦截记录'
  if (tab === 'chat_resume') return '审批恢复记录'
  return '审计时间线'
}

export function sectionTip(tab: string, total: number): string {
  if (tab === 'workflow') return `共 ${total} 条流程记录 · 横向浏览各节点安全状态`
  if (tab === 'blocked_injection') return `共 ${total} 条拦截记录 · 查看阻断节点与原因`
  if (tab === 'chat_resume') return `共 ${total} 条恢复记录 · 追踪审批到执行全路径`
  if (tab === 'chat') return `共 ${total} 条对话记录 · 点击卡片查看详情或执行回放`
  return `共 ${total} 条记录 · 点击卡片查看详情或执行回放`
}

export function buildAuditFlowNodes(record: AuditRecordItem): AuditFlowNode[] {
  const type = record.eventType
  const hasTools = (record.toolCount || 0) > 0
  const risk = record.riskLevel || 'L1'
  const isHighRisk = ['L3', 'L4', 'L5'].includes(risk)

  if (type === 'blocked_injection') {
    return [
      { id: '1', label: '用户输入', sublabel: '入口预校验', status: 'passed' },
      { id: '2', label: '安全预检', sublabel: '正则 + LLM', status: 'passed' },
      { id: '3', label: '注入检测', sublabel: 'L5 硬阻断', status: 'blocked', detail: record.summary?.slice(0, 40) },
      { id: '4', label: '流程终止', sublabel: '未进入 Agent', status: 'blocked' },
    ]
  }

  if (type === 'chat_resume') {
    return [
      { id: '1', label: '审批通过', sublabel: 'L4 管理员', status: 'passed' },
      { id: '2', label: '用户确认', sublabel: '对话页确认执行', status: 'passed' },
      { id: '3', label: '工具执行', sublabel: hasTools ? `${record.toolCount} 个工具` : 'SSH 远程', status: hasTools ? 'passed' : 'idle' },
      { id: '4', label: '执行完成', sublabel: '结论归档', status: 'passed' },
    ]
  }

  if (type === 'workflow' && record.workflowStages?.length) {
    return record.workflowStages.slice(0, 6).map((s, i) => ({
      id: String(i + 1),
      label: s.stage,
      sublabel: s.detail?.slice(0, 20) || '安全阶段',
      status: s.status === 'blocked' ? 'blocked' : s.status === 'pending' ? 'pending' : s.status === 'failed' ? 'blocked' : 'passed',
      detail: s.detail,
    }))
  }

  // chat / default
  return [
    { id: '1', label: '用户输入', sublabel: '会话消息', status: 'passed' },
    { id: '2', label: '安全预检', sublabel: '注入 + 意图', status: 'passed' },
    { id: '3', label: 'Agent 推理', sublabel: record.intent ? '意图已识别' : 'ReAct / Handler', status: 'passed' },
    {
      id: '4',
      label: hasTools ? '工具执行' : '直接回复',
      sublabel: hasTools ? `${record.toolCount} 个工具 · ${risk}` : '无 SSH 调用',
      status: hasTools ? (isHighRisk ? 'warning' : 'passed') : 'passed',
    },
    { id: '5', label: '审计归档', sublabel: 'Trace 持久化', status: 'passed' },
  ]
}

export function recordTypeLabel(type: AuditEventType): string {
  return eventLabel(type)
}

export function flowStatusForRecord(record: AuditRecordItem): { text: string; tone: string } {
  if (record.eventType === 'blocked_injection') return { text: '已阻断', tone: 'danger' }
  if (record.flowStatus === 'pending_approval' || record.flowStatus === 'awaiting_plan_confirm') {
    return { text: '待处理', tone: 'warn' }
  }
  if (record.flowStatus === 'blocked') return { text: '已阻断', tone: 'danger' }
  return { text: '已完成', tone: 'ok' }
}
