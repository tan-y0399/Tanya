import { http } from './http'

export interface AuditItem {
  traceId: string
  event: string
  detail: string
  createdAt: string
}

export async function fetchAudits() {
  const { data } = await http.get<{ items: AuditItem[] }>('/api/audits')
  return data.items
}
