import api from './index'

export async function getTraceOutcomeStatus(sessionId: string, traceId: string) {
  const { data } = await api.get(`/chat/sessions/${sessionId}/trace-outcome`, {
    params: { traceId },
  })
  return data.data as {
    submitted: boolean
    outcome?: string
    comment?: string
    needsExpert?: boolean
  }
}

export async function submitTraceOutcome(payload: {
  traceId: string
  sessionId: string
  outcome: 'solved' | 'partial' | 'unsolved'
  comment?: string
}) {
  const { data } = await api.post('/chat/trace-outcome', payload)
  return data
}
