import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'tool_call' | 'system'
  content: string
  toolCalls?: ToolCall[]
  traceId?: string
  createdAt: string
}

export interface ToolCall {
  id: string
  toolName: string
  params: Record<string, any>
  riskLevel?: 'L1' | 'L2' | 'L3' | 'L4' | 'L5'
  status: 'executing' | 'completed' | 'rejected' | 'timeout' | 'blocked' | 'pending_approval' | 'pending_confirm'
  result?: any
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

  function appendToLastMessage(token: string) {
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant') {
      last.content += token
    }
  }

  function setStreaming(val: boolean) {
    isStreaming.value = val
  }

  function setCurrentTraceId(traceId: string) {
    currentTraceId.value = traceId
  }

  const currentIntent = ref<string | null>(null)
  const injectionWarning = ref<string | null>(null)

  function setCurrentIntent(intent: string | null) {
    currentIntent.value = intent
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
    stateCards.value = []
    riskColor.value = 'blue'
    currentStage.value = ''
    currentIntent.value = null
    injectionWarning.value = null
  }

  return {
    sessions, currentSessionId, messages, isStreaming, currentTraceId,
    setSessions, setCurrentSession, setMessages, addMessage, appendToLastMessage,
    setStreaming, setCurrentTraceId,
    currentIntent, injectionWarning, setCurrentIntent, setInjectionWarning,
    reasoningSteps, stateCards, riskColor, currentStage,
    setReasoningSteps, addReasoningStep, setStateCards, setRiskColor,
    setCurrentStage, resetAgentState,
  }
})
