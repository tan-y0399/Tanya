/** 审批管理模块 — 流程说明与节点构建 */

export interface ApprovalFlowNode {
  id: string
  label: string
  sublabel: string
  status: 'passed' | 'blocked' | 'pending' | 'idle' | 'warning'
  detail?: string
}

export const APPROVAL_HUB = {
  tag: 'MOD-APPROVAL',
  title: 'L4/L5 高危操作审批闸门',
  desc: 'Agent 触发高危工具时自动进入审批队列，管理员 120 秒内决策，通过后用户需在对话页二次确认执行',
  color: '#7c3aed',
  cards: [
    {
      code: 'STEP-1',
      label: 'Agent 发起',
      desc: '对话中触发 L4/L5 高危工具',
      flow: ['检测', '入队', '通知'],
    },
    {
      code: 'STEP-2',
      label: '管理员审批',
      desc: '120 秒内通过或拒绝',
      flow: ['审核', '决策', '归档'],
    },
    {
      code: 'STEP-3',
      label: '用户确认',
      desc: '通过后对话页二次确认',
      flow: ['确认', '执行', '留痕'],
    },
  ],
}

export const STAT_ACCENTS: Record<string, string> = {
  'tone-warn': '#d97706',
  'tone-ok': '#059669',
  'tone-fail': '#dc2626',
  'tone-muted': '#64748b',
  'tone-blue': '#2563eb',
}

export function buildApprovalFlowNodes(
  status: string,
  remainingSeconds?: number | null,
): ApprovalFlowNode[] {
  const isPending = status === 'pending'
  const isApproved = status === 'approved'
  const isRejected = status === 'rejected'
  const isTimeout = status === 'timeout'

  const step2Status = isPending
    ? 'pending'
    : isApproved
      ? 'passed'
      : isRejected || isTimeout
        ? 'blocked'
        : 'idle'

  const step2Detail = isPending && remainingSeconds != null
    ? `${remainingSeconds}s 后超时`
    : isRejected
      ? '已拒绝'
      : isTimeout
        ? '已超时'
        : isApproved
          ? '已通过'
          : undefined

  const step3Status = isApproved ? 'pending' : isPending ? 'idle' : isRejected || isTimeout ? 'blocked' : 'idle'

  return [
    { id: '1', label: 'Agent 发起', sublabel: '高危工具触发', status: 'passed' },
    {
      id: '2',
      label: '管理员审批',
      sublabel: isPending ? '等待决策' : '审批完成',
      status: step2Status,
      detail: step2Detail,
    },
    {
      id: '3',
      label: '用户确认',
      sublabel: isApproved ? '待用户确认执行' : '二次确认执行',
      status: step3Status,
    },
  ]
}

export function nodeStatusLabel(s: ApprovalFlowNode['status']): string {
  const m: Record<ApprovalFlowNode['status'], string> = {
    passed: '通过',
    blocked: '阻断',
    pending: '等待',
    idle: '—',
    warning: '注意',
  }
  return m[s] || s
}

export function nodeStatusTone(s: ApprovalFlowNode['status']): string {
  if (s === 'passed') return 'ok'
  if (s === 'blocked') return 'danger'
  if (s === 'warning' || s === 'pending') return 'warn'
  return 'muted'
}

export function approvalResultLabel(status: string): string {
  const m: Record<string, string> = {
    approved: '已通过',
    rejected: '已拒绝',
    timeout: '已超时',
    pending: '待审批',
  }
  return m[status] || status || '未知'
}

export function approvalResultClass(status: string): string {
  if (status === 'approved') return 'ok'
  if (status === 'timeout') return 'warn'
  if (status === 'pending') return 'pending'
  return 'fail'
}

export function riskClass(level?: string): string {
  const lv = (level || 'L3').toLowerCase().replace('l', '')
  return `l${lv}`
}

export function riskAccentColor(level?: string): string {
  const lv = (level || 'L3').toUpperCase()
  if (lv === 'L5' || lv === 'L4') return '#dc2626'
  if (lv === 'L3') return '#d97706'
  return '#2563eb'
}
