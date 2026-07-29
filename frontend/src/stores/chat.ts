import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  isLightweightConclusion,
  splitConclusionAndReport,
  stripLightweightConclusion,
} from '@/utils/conclusionContent'

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'tool_call' | 'system'
  content: string
  attachments?: ChatAttachment[]
  toolCalls?: ToolCall[]
  traceId?: string
  createdAt: string
  answerMedia?: AnswerMedia[]
}

export interface AnswerMedia {
  id: string
  kind: 'image' | 'diagram'
  status: 'pending' | 'ready' | 'failed'
  title: string
  url?: string
  alt?: string
  caption?: string
  fallback?: string
}

export interface ChatAttachment {
  id?: string
  kind?: 'image'
  name: string
  contentType?: string
  size?: number
  url?: string
  dataUrl?: string
  meta?: Record<string, any>
}

export interface ToolCall {
  id: string
  toolName: string
  params: Record<string, any>
  riskLevel?: 'L1' | 'L2' | 'L3' | 'L4' | 'L5'
  status: 'executing' | 'completed' | 'failed' | 'rejected' | 'timeout' | 'blocked' | 'pending_approval' | 'pending_confirm'
  result?: any
  displaySummary?: string
}

export interface Session {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messageCount: number
}

export interface ReasoningStep {
  step: number
  thought?: string
  action?: string
  observation?: string
}

export interface ExploringStep {
  id: string
  title: string
  detail?: string
  status: 'running' | 'done' | 'error'
}

export interface StateCard {
  title: string
  content: string
  status: 'success' | 'warning' | 'error' | 'info'
}

export interface AgentStage {
  stage: string
  state: {
    current_stage: string
    intent: string | null
    intent_confidence: number
    is_injection: boolean
    has_rag: boolean
    risk_color: string
    round_count: number
    tool_calls_count: number
  }
}

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<Session[]>([])
  const currentSessionId = ref<string | null>(null)
  const messages = ref<Message[]>([])
  const isStreaming = ref(false)
  const currentTraceId = ref<string | null>(null)

  // 推理链
  const reasoningSteps = ref<ReasoningStep[]>([])
  // Exploring 思考过程
  const exploringSteps = ref<ExploringStep[]>([])
  // 状态卡片
  const stateCards = ref<StateCard[]>([])
  // 风险色标
  const riskColor = ref<string>('blue')
  // 当前阶段
  const currentStage = ref<string>('')

  function setSessions(list: Session[]) {
    sessions.value = list
  }

  function setCurrentSession(sessionId: string) {
    currentSessionId.value = sessionId
  }

  function setMessages(list: Message[]) {
    messages.value = list
  }

  function addMessage(msg: Message) {
    messages.value.push(msg)
  }

  function findLastAssistantMessage(): Message | null {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].role === 'assistant') return messages.value[i]
    }
    return null
  }

  function appendToLastMessage(token: string) {
    const m = findLastAssistantMessage()
    if (m) m.content += token
  }

  function upsertLastAnswerMedia(media: AnswerMedia) {
    const message = findLastAssistantMessage()
    if (!message) return
    const list = message.answerMedia || (message.answerMedia = [])
    const index = list.findIndex(item => item.id === media.id)
    if (index >= 0) list[index] = { ...list[index], ...media }
    else list.push(media)
  }

  /** 总结阶段流式写入：替换轻量模板结论，保留运维报告附录 */
  function appendSummaryToken(token: string) {
    const m = findLastAssistantMessage()
    if (!m) return

    const { head, conclusion, reportSuffix } = splitConclusionAndReport(m.content)
    let nextConclusion = conclusion

    if (token.includes('## 执行结论')) {
      if (isLightweightConclusion(nextConclusion) || nextConclusion.includes('## 执行结论')) {
        nextConclusion = ''
      }
    } else if (!nextConclusion.trim() && token.trim()) {
      nextConclusion = ''
    }

    nextConclusion += token
    m.content = head ? head + nextConclusion + reportSuffix : m.content + token
  }

  /** 总结开始前清除前端补全的轻量结论，为 LLM 流式输出腾出空间 */
  function prepareSummaryStream() {
    const m = findLastAssistantMessage()
    if (!m) return
    m.content = stripLightweightConclusion(m.content)
  }

  function setStreaming(val: boolean) {
    isStreaming.value = val
  }

  function setCurrentTraceId(traceId: string) {
    currentTraceId.value = traceId
  }

  const currentIntent = ref<string | null>(null)
  const intentLabel = ref<string>('')
  const intentConfidence = ref<number>(0)
  const responsePhase = ref<string>('')
  const responsePhaseMessage = ref<string>('')
  const injectionWarning = ref<string | null>(null)

  function setCurrentIntent(intent: string | null) {
    currentIntent.value = intent
  }

  function setIntentResolved(payload: {
    intent?: string
    label?: string
    confidence?: number
  }) {
    if (payload.intent) currentIntent.value = payload.intent
    intentLabel.value = payload.label || payload.intent || ''
    intentConfidence.value = payload.confidence ?? 0
  }

  function setResponsePhase(phase: string, message = '') {
    responsePhase.value = phase
    responsePhaseMessage.value = message
  }

  function setInjectionWarning(warning: string | null) {
    injectionWarning.value = warning
  }

  // 推理链操作
  function setReasoningSteps(steps: ReasoningStep[]) {
    reasoningSteps.value = steps
  }

  function addReasoningStep(step: ReasoningStep) {
    reasoningSteps.value.push(step)
  }

  function upsertExploringStep(step: ExploringStep) {
    const idx = exploringSteps.value.findIndex(s => s.id === step.id)
    if (idx >= 0) {
      exploringSteps.value[idx] = { ...exploringSteps.value[idx], ...step }
    } else {
      exploringSteps.value.push(step)
    }
  }

  function setExploringSteps(steps: ExploringStep[]) {
    exploringSteps.value = steps
  }

  // 状态卡片操作
  function setStateCards(cards: StateCard[]) {
    stateCards.value = cards
  }

  function setRiskColor(color: string) {
    riskColor.value = color
  }

  // 阶段更新
  function setCurrentStage(stage: string) {
    currentStage.value = stage
  }

  // 重置所有临时状态
  function resetAgentState() {
    reasoningSteps.value = []
    exploringSteps.value = []
    stateCards.value = []
    riskColor.value = 'blue'
    currentStage.value = ''
    currentIntent.value = null
    intentLabel.value = ''
    intentConfidence.value = 0
    responsePhase.value = ''
    responsePhaseMessage.value = ''
    injectionWarning.value = null
  }

  return {
    sessions, currentSessionId, messages, isStreaming, currentTraceId,
    setSessions, setCurrentSession, setMessages, addMessage, appendToLastMessage, upsertLastAnswerMedia,
    appendSummaryToken, prepareSummaryStream,
    setStreaming, setCurrentTraceId,
    currentIntent, intentLabel, intentConfidence, responsePhase, responsePhaseMessage,
    injectionWarning, setCurrentIntent, setIntentResolved, setResponsePhase, setInjectionWarning,
    reasoningSteps, exploringSteps, stateCards, riskColor, currentStage,
    setReasoningSteps, addReasoningStep, upsertExploringStep, setExploringSteps,
    setStateCards, setRiskColor, setCurrentStage, resetAgentState,
  }
})
