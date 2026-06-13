export type AuditIconName =
  | 'stats-total'
  | 'stats-today'
  | 'stats-risk'
  | 'stats-blocked'
  | 'module-all'
  | 'module-chat'
  | 'module-blocked'
  | 'module-resume'
  | 'module-workflow'
  | 'meta-user'
  | 'meta-trace'
  | 'meta-time'
  | 'meta-tool'
  | 'empty-list'
  | 'action-replay'

export type AuditEventType =
  | 'chat'
  | 'chat_resume'
  | 'blocked_injection'
  | 'workflow'
  | string

export interface AuditRecordItem {
  id: string
  traceId: string
  sessionId?: string
  userId: string
  username?: string
  userDisplayName?: string
  userRoleLabel?: string
  eventType: AuditEventType
  summary: string
  riskLevel?: string
  timestamp: string
  startedAt?: string
  toolCount?: number
  totalMs?: number
  intent?: string
  turnCount?: number
  traceIds?: string[]
  workflowLink?: string
  flowStatus?: string
  blockReason?: string
  blockStage?: string
  blockSeverity?: string
  workflowStages?: Array<{
    stage: string
    status: string
    detail?: string
    duration_ms?: number
    risk_level?: string
  }>
  workflowQuestion?: string
}

export interface AuditStats {
  total: number
  today: number
  l3Plus: number
  blocked: number
  byEventType: Record<string, number>
}

export interface AuditDetail {
  id?: string
  traceId: string
  sessionId?: string
  userId?: string
  username?: string
  userDisplayName?: string
  userRoleLabel?: string
  eventType?: string
  summary?: string
  riskLevel?: string
  timestamp?: string
  startedAt?: string
  turnCount?: number
  question?: string
  answer?: string
  tools?: Array<{ name: string; status?: string; risk?: string }>
  telemetry?: {
    total_ms?: number
    steps?: Array<{ step: string; duration_ms?: number; status?: string; intent?: string }>
    slowest_step?: string
    slowest_ms?: number
  }
  intent?: string
  totalMs?: number
  turns?: Array<{
    sequence: number
    traceId: string
    timestamp: string
    question?: string
    answer?: string
    riskLevel?: string
    intent?: string
    tools?: Array<{ name: string; status?: string; risk?: string }>
  }>
  traceIds?: string[]
  events?: Array<{
    sequence: number
    timestamp: string
    eventType: string
    summary?: string
    riskLevel?: string
    data?: Record<string, unknown>
  }>
}

export interface AuditReplayStep {
  step: number
  eventType: string
  title: string
  detail: string
  status: 'success' | 'error' | 'warning' | 'info'
  time?: string
  duration?: number
  riskLevel?: string
}

export interface AuditReplayData {
  traceId: string
  sessionId?: string
  steps: AuditReplayStep[]
  riskLevel?: string
  intent?: string
  intentLabel?: string
  intentConfidence?: number
  toolCallCount?: number
  totalMs?: number
  question?: string
}

export const EVENT_META: Record<
  string,
  { label: string; icon: AuditIconName; band: string; tab?: string }
> = {
  chat: { label: 'Agent 对话', icon: 'module-chat', band: 'chat', tab: 'chat' },
  chat_resume: { label: '审批恢复', icon: 'module-resume', band: 'resume', tab: 'resume' },
  blocked_injection: { label: '安全拦截', icon: 'module-blocked', band: 'blocked', tab: 'blocked' },
  workflow: { label: '安全流程', icon: 'module-workflow', band: 'workflow', tab: 'workflow' },
}

export const INTENT_LABELS: Record<string, string> = {
  general_qa: '普通问答',
  knowledge_qa: '知识查询',
  ops_query: '运维查询',
  fault_analysis: '故障分析',
  high_risk: '高风险操作',
  prompt_injection: '注入拦截',
}

export const MODULE_TABS = [
  { key: '', label: '全部', icon: 'module-all' as AuditIconName },
  { key: 'chat', label: 'Agent 对话', icon: 'module-chat' as AuditIconName, statKey: 'chat' },
  { key: 'blocked_injection', label: '安全拦截', icon: 'module-blocked' as AuditIconName, statKey: 'blocked_injection' },
  { key: 'chat_resume', label: '审批恢复', icon: 'module-resume' as AuditIconName, statKey: 'chat_resume' },
  { key: 'workflow', label: '安全流程', icon: 'module-workflow' as AuditIconName, statKey: 'workflow' },
] as const

export const STAT_CARDS = [
  { key: 'total', icon: 'stats-total' as AuditIconName, label: '总审计记录', tone: 'blue' as const, hint: '全库累计' },
  { key: 'today', icon: 'stats-today' as AuditIconName, label: '今日操作', tone: 'cyan' as const, hint: 'UTC 当日' },
  { key: 'l3', icon: 'stats-risk' as AuditIconName, label: 'L3+ 高风险', tone: 'orange' as const, hint: '需重点关注' },
  { key: 'blocked', icon: 'stats-blocked' as AuditIconName, label: '安全拦截', tone: 'red' as const, hint: '入口注入阻断' },
] as const

export const HERO_MODULES = [
  { key: 'chat', icon: 'module-chat' as AuditIconName, label: 'Agent 对话', countFrom: 'byEventType.chat' as const },
  { key: 'blocked', icon: 'module-blocked' as AuditIconName, label: '安全拦截', countFrom: 'byEventType.blocked_injection' as const },
  { key: 'resume', icon: 'module-resume' as AuditIconName, label: '审批恢复', countFrom: 'byEventType.chat_resume' as const },
  { key: 'workflow', icon: 'module-workflow' as AuditIconName, label: '安全流程', countFrom: 'byEventType.workflow' as const },
] as const

export function securityBlockCount(stats: AuditStats | null | undefined): number {
  if (!stats) return 0
  return stats.byEventType?.blocked_injection ?? 0
}

export function resolveHeroCount(stats: AuditStats | null, countFrom: (typeof HERO_MODULES)[number]['countFrom']): number {
  if (!stats) return 0
  if (countFrom === 'byEventType.blocked_injection') return securityBlockCount(stats)
  if (countFrom === 'byEventType.chat') return stats.byEventType?.chat ?? 0
  if (countFrom === 'byEventType.chat_resume') return stats.byEventType?.chat_resume ?? 0
  if (countFrom === 'byEventType.workflow') return stats.byEventType?.workflow ?? 0
  return 0
}

export function eventLabel(type: string): string {
  return EVENT_META[type]?.label || type
}

export function eventBandClass(type: string): string {
  return EVENT_META[type]?.band || 'default'
}

export function intentLabel(intent?: string): string {
  if (!intent) return ''
  return INTENT_LABELS[intent] || intent
}

export function riskClass(level?: string): string {
  const lv = (level || 'L1').toLowerCase()
  return `l${lv.replace('l', '')}`
}

export function formatMs(ms?: number): string {
  if (ms == null || Number.isNaN(ms)) return '—'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
