import api from './index'
import type { Session, Message } from '@/stores/chat'

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
}

export function sendMessage(
  sessionId: string,
  content: string,
  callbacks: SendMessageCallbacks,
  pendingApprovalId?: string,
  pendingExecutionId?: string,
  serverId?: string,
): AbortController {
  const controller = new AbortController()
  const {
    onToken, onToolCall, onToolResult,
    onApprovalRequired, onConfirmRequired, onBlocked,
    onError, onDone,
    onIntent, onPromptInjection, onErrorFallback,
    onRiskNotice, onPermissionNotice,
    onStageUpdate, onReasoningStep, onSafetyDecision,
    onReasoningChain, onStateCards,
  } = callbacks

  const body: any = { sessionId, content }
  if (pendingApprovalId) body.pendingApprovalId = pendingApprovalId
  if (pendingExecutionId) body.pendingExecutionId = pendingExecutionId
  if (serverId) body.serverId = serverId

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
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      let currentEvent = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
          continue
        }
        if (line.startsWith('data: ')) {
          try {
            const payload = JSON.parse(line.slice(6))
            switch (currentEvent) {
              // 基础事件
              case 'token': onToken(payload.token); break
              case 'tool_call': onToolCall(payload); break
              case 'tool_result': onToolResult(payload); break
              case 'need_approval': onApprovalRequired(payload); break
              case 'need_confirm': onConfirmRequired(payload); break
              case 'blocked': onBlocked(payload); break
              case 'message_start': break
              case 'message_done': onDone(payload); break
              case 'error': onError(payload); break

              // LangGraph 阶段事件
              case 'stage_update': onStageUpdate?.(payload); break
              case 'intent': onIntent?.(payload); break
              case 'prompt_injection_detected': onPromptInjection?.(payload); break
              case 'rag_context': break
              case 'reasoning_step': onReasoningStep?.(payload); break
              case 'safety_decision': onSafetyDecision?.(payload); break
              case 'reasoning_chain': onReasoningChain?.(payload); break
              case 'state_cards': onStateCards?.(payload); break

              // 其他事件
              case 'error_fallback': onErrorFallback?.(payload); break
              case 'risk_notice': onRiskNotice?.(payload); break
              case 'permission_notice': onPermissionNotice?.(payload); break
            }
          } catch { /* skip parse errors */ }
        }
      }
    }
  }).catch((err: any) => {
    if (err?.name === 'AbortError') return
    onError(err)
  })

  return controller
}
