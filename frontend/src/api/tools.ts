import api from './index'

export interface ToolInfo {
  id: string
  name: string
  description: string
  category: string
  riskLevel: number
  enabled: boolean
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
