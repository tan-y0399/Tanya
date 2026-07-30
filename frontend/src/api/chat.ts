import api from './index'
import type { Session, Message, ChatAttachment } from '@/stores/chat'

export async function getSessions(page = 1, size = 20) {
  const { data } = await api.get('/chat/sessions', { params: { page, size } })
  return data.data
}

export async function createSession(title = '新会话') {
  const { data } = await api.post('/chat/sessions', { title })
  return data.data
}

export async function deleteSession(sessionId: string) {
  const { data } = await api.delete(`/chat/sessions/${sessionId}`)
  return data
}

export async function clearSessionMessages(sessionId: string) {
  const { data } = await api.delete(`/chat/sessions/${sessionId}/messages`)
  return data
}

export async function deleteMessage(messageId: string) {
  const { data } = await api.delete(`/chat/messages/${messageId}`)
  return data
}

export async function getMessages(sessionId: string, page = 1, size = 50) {
  const { data } = await api.get(`/chat/sessions/${sessionId}/messages`, { params: { page, size } })
  return data.data
}

export async function getAwaitingRun(sessionId: string) {
  const { data } = await api.get(`/chat/sessions/${sessionId}/awaiting-run`)
  return data.data
}

export async function getPendingPlan(sessionId: string) {
  const { data } = await api.get(`/chat/sessions/${sessionId}/pending-plan`)
  return data.data
}

export async function cancelAwaitingRun(sessionId: string, payload: { approvalId?: string; pendingExecutionId?: string }) {
  const { data } = await api.post(`/chat/sessions/${sessionId}/cancel-run`, payload)
  return data
}

export async function synthesizeSpeech(payload: { text: string; voice?: string; speed?: number }) {
  const { data } = await api.post('/chat/tts', payload)
  return data.data
}

export interface RollbackToolStatus {
  logId: string
  reversible: boolean
  rolledBack: boolean
  rollbackHint: string
  toolName: string
}

/** 查询会话内工具可回滚状态 */
export async function getRollbackStatus(sessionId: string): Promise<{
  byToolCallId: Record<string, RollbackToolStatus>
  pendingRollbackCount: number
  hasFullRollback: boolean
}> {
  const { data } = await api.get(`/chat/sessions/${sessionId}/rollback-status`)
  return data.data
}

/** 单步/全量回滚（阶段3子步骤4） */
export async function rollbackSession(
  sessionId: string,
  mode: 'single_step' | 'full' = 'single_step',
  opts?: { logId?: string; toolCallId?: string },
) {
  const { data } = await api.post(`/chat/sessions/${sessionId}/rollback`, {
    mode,
    logId: opts?.logId,
    toolCallId: opts?.toolCallId,
  })
  return data.data
}

export interface SendMessageCallbacks {
  onToken: (token: string) => void
  onToolCall: (tool: any) => void
  onToolResult: (result: any) => void
  onApprovalRequired: (approval: any) => void
  onConfirmRequired: (confirm: any) => void
  onBlocked: (blocked: any) => void
  onError: (err: any) => void
  onDone: (result: any) => void
  // LangGraph 扩展事件
  onIntent?: (intent: any) => void
  onPromptInjection?: (injection: any) => void
  onErrorFallback?: (fallback: any) => void
  onRiskNotice?: (notice: any) => void
  onPermissionNotice?: (notice: any) => void
  onStageUpdate?: (stage: any) => void
  onReasoningStep?: (step: any) => void
  onSafetyDecision?: (safety: any) => void
  onReasoningChain?: (chain: any) => void
  onStateCards?: (cards: any) => void
  onExploringStep?: (step: any) => void
  onIntentResolved?: (payload: any) => void
  onResponsePhase?: (payload: { phase: string; message?: string; detail?: string }) => void
  onSummaryStart?: (payload: { title?: string }) => void
  onSummaryDone?: () => void
  onToolCallsUpdated?: (payload: { messageId?: string; toolCalls?: any[] }) => void
  onDiagnosticPlan?: (payload: any) => void
  onDiagnosticPlanStart?: (payload: any) => void
  onDiagnosticPlanDelta?: (payload: any) => void
  onEnvPrecheck?: (payload: any) => void
  onPlanProgress?: (payload: any) => void
  onRouteDispatch?: (payload: any) => void
  onTaskProgress?: (payload: any) => void
  onOpsReport?: (payload: any) => void
  onVisionResult?: (payload: any) => void
  onMultimodalRag?: (payload: any) => void
  onAgentHandoff?: (payload: any) => void
  onDeepIntentResolved?: (payload: any) => void
  onDeepPlan?: (payload: any) => void
  onWebResearch?: (payload: any) => void
  onIntentClarification?: (payload: any) => void
  onImageReview?: (payload: any) => void
  onImageGeneration?: (payload: any) => void
  onDiagramResult?: (payload: any) => void
  onAnswerMedia?: (payload: any) => void
}

function dispatchSseEvent(eventName: string, payload: any, cbs: SendMessageCallbacks) {
  switch (eventName) {
    case 'token': cbs.onToken(payload.token); break
    case 'tool_call': cbs.onToolCall(payload); break
    case 'tool_result': cbs.onToolResult(payload); break
    case 'need_approval': cbs.onApprovalRequired(payload); break
    case 'need_confirm': cbs.onConfirmRequired(payload); break
    case 'blocked': cbs.onBlocked(payload); break
    case 'message_start': break
    case 'message_done': cbs.onDone(payload); break
    case 'error': cbs.onError(payload); break
    case 'stage_update': cbs.onStageUpdate?.(payload); break
    case 'intent': cbs.onIntent?.(payload); cbs.onIntentResolved?.(payload); break
    case 'intent_resolved': cbs.onIntentResolved?.(payload); break
    case 'response_phase': cbs.onResponsePhase?.(payload); break
    case 'summary_start': cbs.onSummaryStart?.(payload); break
    case 'summary_done': cbs.onSummaryDone?.(); break
    case 'tool_calls_updated': cbs.onToolCallsUpdated?.(payload); break
    case 'prompt_injection_detected': cbs.onPromptInjection?.(payload); break
    case 'rag_context': break
    case 'reasoning_step': cbs.onReasoningStep?.(payload); break
    case 'safety_decision': cbs.onSafetyDecision?.(payload); break
    case 'reasoning_chain': cbs.onReasoningChain?.(payload); break
    case 'state_cards': cbs.onStateCards?.(payload); break
    case 'exploring_step': cbs.onExploringStep?.(payload); break
    case 'error_fallback': cbs.onErrorFallback?.(payload); break
    case 'risk_notice': cbs.onRiskNotice?.(payload); break
    case 'permission_notice': cbs.onPermissionNotice?.(payload); break
    case 'diagnostic_plan_start': cbs.onDiagnosticPlanStart?.(payload); break
    case 'diagnostic_plan_delta': cbs.onDiagnosticPlanDelta?.(payload); break
    case 'diagnostic_plan': cbs.onDiagnosticPlan?.(payload); break
    case 'env_precheck': cbs.onEnvPrecheck?.(payload); break
    case 'plan_progress': cbs.onPlanProgress?.(payload); break
    case 'route_dispatch': cbs.onRouteDispatch?.(payload); break
    case 'task_progress': cbs.onTaskProgress?.(payload); break
    case 'ops_report': cbs.onOpsReport?.(payload); break
    case 'vision_result': cbs.onVisionResult?.(payload); break
    case 'multimodal_rag': cbs.onMultimodalRag?.(payload); break
    case 'agent_handoff': cbs.onAgentHandoff?.(payload); break
    case 'deep_intent_resolved':
      cbs.onDeepIntentResolved?.(payload)
      cbs.onIntentResolved?.({
        intent: payload?.intent,
        label: payload?.label,
        confidence: payload?.confidence,
      })
      break
    case 'deep_plan': cbs.onDeepPlan?.(payload); break
    case 'web_research': cbs.onWebResearch?.(payload); break
    case 'intent_clarification': cbs.onIntentClarification?.(payload); break
    case 'image_review': cbs.onImageReview?.(payload); break
    case 'image_generation': cbs.onImageGeneration?.(payload); break
    case 'diagram_result': cbs.onDiagramResult?.(payload); break
    case 'answer_media': cbs.onAnswerMedia?.(payload); break
    default: break
  }
}

function safeDispatchSseEvent(eventName: string, payload: unknown, cbs: SendMessageCallbacks) {
  try {
    dispatchSseEvent(eventName, payload, cbs)
  } catch (e) {
    console.warn('[SSE] handler error:', eventName, e)
  }
}

/** 按行解析 SSE（空行分隔事件），兼容分块边界与流结束 */
class SseLineParser {
  private buffer = ''
  private eventName = ''
  private dataLines: string[] = []

  private dispatchEvent(cbs: SendMessageCallbacks) {
    if (!this.dataLines.length) {
      this.eventName = ''
      return
    }
    const dataStr = this.dataLines.join('\n')
    const name = this.eventName
    this.eventName = ''
    this.dataLines = []
    try {
      safeDispatchSseEvent(name, JSON.parse(dataStr), cbs)
    } catch (e) {
      console.warn('[SSE] JSON parse failed:', name, dataStr.slice(0, 120), e)
    }
  }

  feed(chunk: string, cbs: SendMessageCallbacks) {
    this.buffer += chunk.replace(/\r\n/g, '\n')
    for (;;) {
      const nl = this.buffer.indexOf('\n')
      if (nl === -1) break
      let line = this.buffer.slice(0, nl)
      this.buffer = this.buffer.slice(nl + 1)
      if (line.endsWith('\r')) line = line.slice(0, -1)
      if (line === '') {
        this.dispatchEvent(cbs)
        continue
      }
      if (line.startsWith('event: ')) this.eventName = line.slice(7).trim()
      else if (line.startsWith('data: ')) this.dataLines.push(line.slice(6))
    }
  }

  finish(cbs: SendMessageCallbacks) {
    if (this.buffer.trim()) {
      let line = this.buffer.replace(/\r$/, '')
      this.buffer = ''
      if (line.startsWith('event: ')) this.eventName = line.slice(7).trim()
      else if (line.startsWith('data: ')) this.dataLines.push(line.slice(6))
    }
    this.dispatchEvent(cbs)
  }
}

export function sendMessage(
  sessionId: string,
  content: string,
  callbacks: SendMessageCallbacks,
  pendingApprovalId?: string,
  pendingExecutionId?: string,
  serverId?: string,
  confirmPlanId?: string,
  thinkingMode: 'fast' | 'deep' = 'fast',
  attachments: ChatAttachment[] = [],
  deepIntentChoice?: 'professional_answer' | 'plan_execute',
): AbortController {
  const controller = new AbortController()
  const body: any = { sessionId, content }
  if (pendingApprovalId) body.pendingApprovalId = pendingApprovalId
  if (pendingExecutionId) body.pendingExecutionId = pendingExecutionId
  if (serverId) body.serverId = serverId
  if (confirmPlanId) body.confirmPlanId = confirmPlanId
  if (thinkingMode) body.thinkingMode = thinkingMode
  if (deepIntentChoice) body.deepIntentChoice = deepIntentChoice
  if (attachments.length) {
    body.attachments = attachments.map(a => ({
      id: a.id,
      kind: a.kind || 'image',
      name: a.name,
      contentType: a.contentType,
      size: a.size,
      dataUrl: a.dataUrl,
    }))
  }

  fetch('/api/v1/chat/send', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    },
    body: JSON.stringify(body),
    signal: controller.signal,
  }).then(async (res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    const parser = new SseLineParser()

    while (true) {
      const { done, value } = await reader.read()
      if (value) {
        parser.feed(decoder.decode(value, { stream: !done }), callbacks)
      }
      if (done) {
        parser.finish(callbacks)
        break
      }
    }
  }).catch((err: any) => {
    if (err?.name === 'AbortError') return
    callbacks.onError(err)
  })

  return controller
}

/** 方案卡壳时续跑下一步（SSE） */
export function continuePlanExecution(
  sessionId: string,
  callbacks: SendMessageCallbacks,
  serverId?: string,
): AbortController {
  const controller = new AbortController()
  const body: any = {}
  if (serverId) body.serverId = serverId

  fetch(`/api/v1/chat/sessions/${sessionId}/continue-plan`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    },
    body: JSON.stringify(body),
    signal: controller.signal,
  }).then(async (res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    const parser = new SseLineParser()

    while (true) {
      const { done, value } = await reader.read()
      if (value) {
        parser.feed(decoder.decode(value, { stream: !done }), callbacks)
      }
      if (done) {
        parser.finish(callbacks)
        break
      }
    }
  }).catch((err: any) => {
    if (err?.name === 'AbortError') return
    callbacks.onError?.(err)
  })

  return controller
}

/** 审批拒绝/超时后，补全 Agent 执行结论（SSE） */
export function finalizeApprovalRejection(
  sessionId: string,
  approvalId: string,
  callbacks: Pick<
    SendMessageCallbacks,
    'onToken' | 'onSummaryStart' | 'onSummaryDone' | 'onToolCallsUpdated' | 'onError' | 'onDone'
  >,
): Promise<void> {
  return fetch(`/api/v1/chat/sessions/${sessionId}/approval-rejected`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    },
    body: JSON.stringify({ approvalId }),
  }).then(async (res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    const parser = new SseLineParser()

    while (true) {
      const { done, value } = await reader.read()
      if (value) {
        parser.feed(decoder.decode(value, { stream: !done }), callbacks as SendMessageCallbacks)
      }
      if (done) {
        parser.finish(callbacks as SendMessageCallbacks)
        break
      }
    }
  }).catch((err: any) => {
    callbacks.onError?.(err)
    throw err
  })
}

export type { Session, Message, ChatAttachment }
