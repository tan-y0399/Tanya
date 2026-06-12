import api from './index'

export interface ProvisionStep {
  message: string
  status: 'info' | 'ok' | 'warn' | 'error'
}

export interface ServerInfo {
  id: string
  name: string
  host: string
  port: number
  username: string
  authConfigured?: boolean
  description: string
  tags: string[]
  isDefault: boolean
  status: 'online' | 'offline' | 'unknown'
  lastChecked: string | null
  createdAt: string
  updatedAt: string
}

export interface ServerFormPayload {
  name: string
  host: string
  port: number
  username: string
  hostPassword?: string
  description?: string
  tags?: string[]
  isDefault?: boolean
}

export async function getServerDefaults(): Promise<{ username: string; restrictedUsers: string[]; platformKeyPath?: string }> {
  const { data } = await api.get('/servers/defaults')
  return data.data
}

export async function getServers(): Promise<{ items: ServerInfo[] }> {
  const { data } = await api.get('/servers/list')
  return data.data
}

export interface ReachabilityDiagnosis {
  reachable: boolean
  message: string
  localIp?: string
  gateway?: string
  gatewayReachable?: boolean
  targetPing?: boolean
  sameSubnet?: boolean
  tcpPortOpen?: boolean
  suggestions?: string[]
}

export async function checkServerReachable(host: string, port = 22) {
  const { data } = await api.post('/servers/check-reachable', { host, port })
  return data.data as ReachabilityDiagnosis
}

export async function provisionServer(payload: ServerFormPayload) {
  const { data } = await api.post('/servers/provision', payload)
  return data.data as { success: boolean; error?: string; steps: ProvisionStep[] }
}

export async function addServer(server: ServerFormPayload) {
  const { data } = await api.post('/servers/add', server)
  return data
}

export async function updateServer(serverId: string, server: Partial<ServerFormPayload>) {
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
