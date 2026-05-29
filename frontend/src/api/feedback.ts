import api from './index'

export interface FeedbackInfo {
  id: string
  userId: string
  username: string
  title: string
  content: string
  status: 'pending' | 'replied' | 'closed'
  adminReply: string
  createdAt: string
  updatedAt: string
}

export async function getFeedbackList(): Promise<{ items: FeedbackInfo[] }> {
  const { data } = await api.get('/feedback/list')
  return data.data
}

export async function createFeedback(fb: { title: string; content: string }) {
  const { data } = await api.post('/feedback/create', fb)
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
