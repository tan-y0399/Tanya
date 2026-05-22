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
  riskLevel?: 'L1' | 'L2' | 'L3' | 'L4'
  status: 'executing' | 'completed' | 'rejected' | 'timeout'
  result?: any
}

export interface Session {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messageCount: number
}

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<Session[]>([])
  const currentSessionId = ref<string | null>(null)
  const messages = ref<Message[]>([])
  const isStreaming = ref(false)
  const currentTraceId = ref<string | null>(null)

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

  return {
    sessions, currentSessionId, messages, isStreaming, currentTraceId,
    setSessions, setCurrentSession, setMessages, addMessage, appendToLastMessage,
    setStreaming, setCurrentTraceId,
  }
})
