import api from './index'

export async function getAuditRecords(params: {
  page?: number
  size?: number
  userId?: string
  eventType?: string
  riskLevel?: string
  startTime?: string
  endTime?: string
  traceId?: string
}) {
  const { data } = await api.get('/audit/records', { params })
  return data.data
}

export async function getAuditDetail(traceId: string) {
  const { data } = await api.get(`/audit/records/${traceId}`)
  return data.data
}
