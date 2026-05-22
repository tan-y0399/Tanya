import api from './index'

export async function getHealth() {
  const { data } = await api.get('/system/health')
  return data.data
}

export async function getConfig() {
  const { data } = await api.get('/system/config')
  return data.data
}

export async function updateConfig(config: Record<string, any>) {
  const { data } = await api.put('/system/config', config)
  return data
}
