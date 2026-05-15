import { http } from './http'

export interface ApprovalRequest {
  action: string
  reason: string
}

export interface ApprovalResponse {
  approved: boolean
  message: string
}

export async function submitApproval(payload: ApprovalRequest) {
  const { data } = await http.post<ApprovalResponse>('/api/approval', payload)
  return data
}
