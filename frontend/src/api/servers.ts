import api from './index'

export interface ServerInfo {
  id: string
  name: string
  host: string
  port: number
  username: string
  keyPath: string
  description: string
  tags: string[]
  isDefault: boolean
  status: 'online' | 'offline' | 'unknown'
  lastChecked: string | null
  createdAt: string
  updatedAt: string
}

export async function getServers(): Promise<{ items: ServerInfo[] }> {
  const { data } = await api.get('/servers/list')
  return data.data
}

export async function addServer(server: Partial<ServerInfo>) {
  const { data } = await api.post('/servers/add', server)
  return data
}

export async function updateServer(serverId: string, server: Partial<ServerInfo>) {
  const { data } = await api.put(`/servers/${serverId}`, server)
  return data
}

export async function deleteServer(serverId: string) {
  const { data } = await api.delete(`/servers/${serverId}`)
  return data
}

export async function testServerConnection(serverId: string) {
  const { data } = await api.post(`/servers/${serverId}/test`)
  return data
}
