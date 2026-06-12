import api from './index'

export interface FeedbackInfo {
  id: string
  userId: string
  username: string
  title: string
  sessionTitle?: string
  content: string
  source?: 'manual' | 'agent_chat' | 'session_chat' | string
  sourceLabel?: string
  typeLabel?: string
  category?: string
  traceId?: string
  sessionId?: string
  outcome?: string
  status: 'pending' | 'replied' | 'closed'
  adminReply: string
  attachments?: { url: string; name?: string }[]
  createdAt: string
  updatedAt: string
}

export async function getFeedbackList(): Promise<{ items: FeedbackInfo[] }> {
  const { data } = await api.get('/feedback/list')
  return data.data
}

export async function createFeedback(fb: {
  title: string
  content: string
  category?: string
  sessionId?: string
  traceId?: string
  source?: string
  images?: string[]
}) {
  const { data } = await api.post('/feedback/create', fb)
  return data
}

export interface SessionFeedbackPayload {
  sessionId: string
  content: string
  category?: string
  outcome?: string
  traceId?: string
  sessionTitle?: string
  starRating?: number
  starLabel?: string
  images?: string[]
}

export async function uploadFeedbackImage(file: File): Promise<{ url: string; name: string }> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/feedback/upload-image', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data.data
}

export async function getSessionFeedback(sessionId: string): Promise<{ item: FeedbackInfo | null }> {
  const { data } = await api.get(`/feedback/session/${sessionId}`)
  return data.data
}

export async function submitSessionFeedback(payload: SessionFeedbackPayload) {
  const { data } = await api.post('/feedback/session', payload)
  return data
}

export async function replyFeedback(feedbackId: string, reply: string) {
  const { data } = await api.post(`/feedback/${feedbackId}/reply`, { reply })
  return data
}

export async function updateFeedbackStatus(feedbackId: string, status: string) {
  const { data } = await api.put(`/feedback/${feedbackId}/status`, { status })
  return data
}
