import api from './index'

export interface ToolInfo {
  id: string
  name: string
  description: string
  category: string
  riskLevel: number
  enabled: boolean
  builtin?: boolean
  config: Record<string, any>
  createdAt: string
  updatedAt: string
}

export async function getTools(): Promise<{ items: ToolInfo[] }> {
  const { data } = await api.get('/tools/list')
  return data.data
}

export async function addTool(tool: Partial<ToolInfo>) {
  const { data } = await api.post('/tools/add', tool)
  return data
}

export async function updateTool(toolId: string, updates: Partial<ToolInfo>) {
  const { data } = await api.put(`/tools/${toolId}`, updates)
  return data
}

export async function deleteTool(toolId: string) {
  const { data } = await api.delete(`/tools/${toolId}`)
  return data
}

export async function toggleTool(toolId: string, enabled: boolean) {
  const { data } = await api.post(`/tools/${toolId}/toggle`, { enabled })
  return data
}

export async function batchUpdateTools(updates: { id: string; enabled: boolean }[]) {
  const { data } = await api.put('/tools/batch', { updates })
  return data
}

export interface ToolFileValidation {
  ok: boolean
  stage: string
  name: string
  description?: string
  category?: string
  riskLevel?: number
  config?: Record<string, any>
  diagnose?: { ok: boolean; messages: string[]; errors: string[] }
  trial?: { ok: boolean; error?: string; result?: Record<string, any> }
}

export async function validateToolFile(filename: string, content: string): Promise<ToolFileValidation> {
  const { data } = await api.post('/tools/validate-file', { filename, content })
  return data.data
}
