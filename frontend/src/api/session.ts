import { http } from './http'

export interface SessionItem {
  sessionId: string
  title: string
  updatedAt: string
}

export interface MessageItem {
  id: string
  role: 'user' | 'agent' | 'tool'
  content: string
  createdAt: string
}

export async function fetchSessions() {
  const { data } = await http.get<{ items: SessionItem[] }>('/api/sessions')
  return data.items
}

export async function fetchMessages(sessionId: string) {
  const { data } = await http.get<{ items: MessageItem[] }>(`/api/sessions/${sessionId}/messages`)
  return data.items
}

export async function createSession(title: string) {
  const { data } = await http.post<SessionItem>('/api/sessions', { title })
  return data
}
