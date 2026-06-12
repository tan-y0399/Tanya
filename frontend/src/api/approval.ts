import api from './index'

export async function getPendingApprovals() {
  const { data } = await api.get('/approval/pending')
  return data.data
}

export async function getApprovalById(id: string) {
  const { data } = await api.get(`/approval/${id}`)
  return data.data
}

export async function getApprovalStats() {
  const { data } = await api.get('/approval/stats')
  return data.data
}

export async function getApprovalHistory(page = 1, size = 20) {
  const { data } = await api.get('/approval/history', { params: { page, size } })
  return data.data
}

export async function approveApproval(id: string, comment?: string) {
  const { data } = await api.post(`/approval/${id}/approve`, { comment })
  return data
}

export async function rejectApproval(id: string, reason?: string) {
  const { data } = await api.post(`/approval/${id}/reject`, { reason })
  return data
}

export async function updateApproval(id: string, payload: {
  detail?: string
  comment?: string
  riskLevel?: string
}) {
  const { data } = await api.patch(`/approval/${id}`, payload)
  return data.data
}

export async function deleteApproval(id: string) {
  const { data } = await api.delete(`/approval/${id}`)
  return data
}
