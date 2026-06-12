/** 三条 Agent 安全执行链路的流程节点定义与状态映射 */

export type WorkflowLinkId = 'link_a' | 'link_b' | 'link_c'

export type FlowNodeStatus = 'passed' | 'blocked' | 'failed' | 'pending' | 'warning' | 'idle' | 'skipped'

export interface WorkflowStageSnapshot {
  stage: string
  status: string
  detail?: string
  duration_ms?: number
  risk_level?: string
}

export interface FlowNode {
  id: string
  stageKey?: string
  label: string
  sublabel: string
  kind: 'start' | 'security' | 'route' | 'decision' | 'plan' | 'execute' | 'end'
  status: FlowNodeStatus
  detail?: string
  durationMs?: number
  riskLevel?: string
}

export const LINK_CATALOG = {
  link_a: {
    id: 'link_a' as const,
    code: 'LINK-A',
    short: '链路 A',
    label: '普通问答链路',
    desc: '纯 LLM 应答 · 无 SSH 工具 · L1 安全预检',
    color: '#06b6d4',
    glow: 'rgba(6, 182, 212, 0.35)',
  },
  link_b: {
    id: 'link_b' as const,
    code: 'LINK-B',
    short: '链路 B',
    label: '轻量 ReAct 链路',
    desc: '只读运维查询 · 快速 ReAct · L1–L2 风险过滤',
    color: '#3b82f6',
    glow: 'rgba(59, 130, 246, 0.35)',
  },
  link_c: {
    id: 'link_c' as const,
    code: 'LINK-C',
    short: '链路 C',
    label: '深度 Plan-Execute 链路',
    desc: '诊断方案 → 环境预检 → 分步执行 · L1–L5 全分级',
    color: '#8b5cf6',
    glow: 'rgba(139, 92, 246, 0.35)',
  },
} as const

const STAGE_STATUS_MAP: Record<string, FlowNodeStatus> = {
  passed: 'passed',
  blocked: 'blocked',
  failed: 'failed',
  pending: 'pending',
  warning: 'warning',
  running: 'pending',
  skipped: 'skipped',
}

const FLOW_STATUS_LABELS: Record<string, string> = {
  completed: '已完成',
  blocked: '已阻断',
  failed: '失败',
  pending_approval: '待审批',
  awaiting_plan_confirm: '待确认方案',
  awaiting_user_action: '待用户确认',
  routing: '路由中',
}

export function flowStatusLabel(status?: string): string {
  if (!status) return '—'
  return FLOW_STATUS_LABELS[status] || status
}

export function resolveWorkflowLink(
  link?: string | null,
  intent?: string | null,
): WorkflowLinkId {
  if (link === 'link_a' || link === 'link_b' || link === 'link_c') return link
  if (intent === 'general_qa' || intent === 'knowledge_qa') return 'link_a'
  if (intent === 'fault_analysis' || intent === 'high_risk') return 'link_c'
  return 'link_b'
}

function stageMap(stages: WorkflowStageSnapshot[]): Map<string, WorkflowStageSnapshot> {
  const m = new Map<string, WorkflowStageSnapshot>()
  for (const s of stages || []) {
    if (s?.stage) m.set(s.stage, s)
  }
  return m
}

function nodeFromStage(
  id: string,
  label: string,
  sublabel: string,
  kind: FlowNode['kind'],
  stageKey: string,
  sm: Map<string, WorkflowStageSnapshot>,
  fallback: FlowNodeStatus = 'idle',
): FlowNode {
  const s = sm.get(stageKey)
  const status = s ? (STAGE_STATUS_MAP[s.status] || fallback) : fallback
  return {
    id,
    stageKey,
    label,
    sublabel,
    kind,
    status,
    detail: s?.detail,
    durationMs: s?.duration_ms,
    riskLevel: s?.risk_level,
  }
}

function endNode(flowStatus?: string, detail?: string): FlowNode {
  const blocked = flowStatus === 'blocked'
  const pending = flowStatus === 'pending_approval' || flowStatus === 'awaiting_plan_confirm' || flowStatus === 'awaiting_user_action'
  let status: FlowNodeStatus = 'passed'
  if (blocked) status = 'blocked'
  else if (pending) status = 'pending'
  else if (flowStatus === 'failed') status = 'failed'
  else if (flowStatus && flowStatus !== 'completed' && flowStatus !== 'routing') status = 'warning'

  return {
    id: 'end',
    label: flowStatusLabel(flowStatus),
    sublabel: blocked ? '安全闸门终止' : pending ? '等待人工介入' : '流程结束',
    kind: 'end',
    status,
    detail,
  }
}

/** 按链路生成完整流程节点（合并实际 stages 状态） */
export function buildFlowNodes(
  linkId: WorkflowLinkId,
  stages: WorkflowStageSnapshot[] = [],
  flowStatus?: string,
  toolCount = 0,
): FlowNode[] {
  const sm = stageMap(stages)
  const shared: FlowNode[] = [
    {
      id: 'input',
      label: '用户输入',
      sublabel: '入口预校验',
      kind: 'start',
      status: 'passed',
    },
    nodeFromStage('inj', '安全预检', '注入检测 · LLM', 'security', 'prompt_injection', sm, 'passed'),
    nodeFromStage('intent', '意图识别', '分类 + 知识库', 'security', 'intent_parsing', sm, 'passed'),
    nodeFromStage('recheck', '二次复核', '上下文注入检测', 'security', 'context_recheck', sm, 'passed'),
    {
      ...nodeFromStage('route', '路由分发', LINK_CATALOG[linkId].short, 'decision', 'route_dispatch', sm, 'passed'),
      label: '路由分发',
      sublabel: LINK_CATALOG[linkId].label,
    },
  ]

  if (linkId === 'link_a') {
    return [
      ...shared,
      {
        id: 'answer',
        label: 'LLM 直接应答',
        sublabel: '无远程工具调用',
        kind: 'execute',
        status: flowStatus === 'blocked' ? 'blocked' : 'passed',
        detail: 'Handler / 知识库回答',
      },
      endNode(flowStatus),
    ]
  }

  if (linkId === 'link_b') {
    const risk = nodeFromStage('risk', '风险过滤', 'L1–L2 命令分级', 'security', 'risk_filter', sm, toolCount ? 'passed' : 'idle')
    const exec = nodeFromStage('exec', 'ReAct 执行', '只读工具 · SSH', 'execute', 'execution', sm, toolCount ? 'passed' : 'idle')
    if (toolCount && exec.status === 'idle') exec.status = 'passed'
    return [...shared, risk, exec, endNode(flowStatus)]
  }

  // link_c
  const planStatus: FlowNodeStatus =
    flowStatus === 'awaiting_plan_confirm' ? 'pending'
      : sm.has('route_dispatch') ? 'passed' : 'idle'
  const plan: FlowNode = {
    id: 'plan',
    label: '诊断方案',
    sublabel: '生成步骤 · 用户确认',
    kind: 'plan',
    status: planStatus,
    detail: flowStatus === 'awaiting_plan_confirm' ? '等待用户确认方案' : undefined,
  }
  const env: FlowNode = {
    id: 'env',
    label: '环境预检',
    sublabel: 'SSH · 磁盘 · 连通性',
    kind: 'security',
    status: sm.has('execution') || flowStatus === 'completed' ? 'passed' : planStatus === 'passed' ? 'warning' : 'idle',
  }
  const risk = nodeFromStage('risk', '风险过滤', 'L1–L5 全分级', 'security', 'risk_filter', sm, 'idle')
  const perm = nodeFromStage('perm', '权限/审批', 'L4 审批链', 'security', 'permission_check', sm,
    flowStatus === 'pending_approval' ? 'pending' : 'idle')
  const exec = nodeFromStage('exec', '分步执行', '动态调整 · 可回滚', 'execute', 'execution', sm, 'idle')
  if (toolCount && exec.status === 'idle') exec.status = 'passed'

  return [...shared, plan, env, risk, perm, exec, endNode(flowStatus)]
}

export function statusTone(status: FlowNodeStatus): string {
  const map: Record<FlowNodeStatus, string> = {
    passed: 'ok',
    blocked: 'danger',
    failed: 'danger',
    pending: 'warn',
    warning: 'warn',
    idle: 'muted',
    skipped: 'muted',
  }
  return map[status] || 'muted'
}
