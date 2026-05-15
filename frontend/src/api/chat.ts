import { http } from './http'

export interface ChatRequest {
  sessionId: string
  message: string
}

export interface ChatResponse {
  reply: string
  traceId: string
  toolCalls: Array<{ name: string; status: string }>
}

export async function sendChatMessage(payload: ChatRequest) {
  const { data } = await http.post<ChatResponse>('/api/chat', payload)
  return data
}
