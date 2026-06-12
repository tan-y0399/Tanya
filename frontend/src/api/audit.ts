import api from './index'
import type { AuditDetail, AuditReplayData, AuditStats } from '@/components/audit/auditEventMeta'

export async function getAuditStats(): Promise<AuditStats> {
  const { data } = await api.get('/audit/stats')
  return data.data
}

export async function getAuditRecords(params: {
  page?: number
  size?: number
  username?: string
  eventType?: string
  riskLevel?: string
  startTime?: string
  endTime?: string
  traceId?: string
  keyword?: string
}) {
  const { data } = await api.get('/audit/records', { params })
  return data.data
}

export async function getAuditDetail(refId: string): Promise<AuditDetail> {
  const { data } = await api.get(`/audit/records/${refId}`)
  return data.data
}

export async function getAuditReplay(traceId: string): Promise<AuditReplayData> {
  const { data } = await api.get(`/audit/replay/${traceId}`)
  return data.data
}
