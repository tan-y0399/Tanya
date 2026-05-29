import api from './index'

export interface UserInfo {
  id: string
  username: string
  role: string
}

export async function getUsers(): Promise<{ items: UserInfo[] }> {
  const { data } = await api.get('/users/list')
  return data.data
}

export async function createUser(user: { username: string; password: string; role: string }) {
  const { data } = await api.post('/users/create', user)
  return data
}

export async function updateUser(userId: string, updates: { role?: string; password?: string }) {
  const { data } = await api.put(`/users/${userId}`, updates)
  return data
}

export async function deleteUser(userId: string) {
  const { data } = await api.delete(`/users/${userId}`)
  return data
}

export async function resetPassword(userId: string, password: string) {
  const { data } = await api.post(`/users/${userId}/reset-password`, { password })
  return data
}
