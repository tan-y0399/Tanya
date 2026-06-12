import api from './index'

function getUserKey(): string {
  try {
    const info = localStorage.getItem('userInfo')
    if (info) {
      const u = JSON.parse(info)
      if (u?.id) return `user:${u.id}`
    }
  } catch { /* ignore */ }
  let clientId = localStorage.getItem('kb_client_id')
  if (!clientId) {
    clientId = 'anon:' + Math.random().toString(36).slice(2, 12)
    localStorage.setItem('kb_client_id', clientId)
  }
  return clientId
}

export { getUserKey }

export async function fetchArticles(params: Record<string, any>) {
  const { data } = await api.get('/knowledge/articles', {
    params: { ...params, userKey: getUserKey() },
  })
  return data.data
}

export async function fetchArticle(id: string) {
  const { data } = await api.get(`/knowledge/articles/${id}`, {
    params: { userKey: getUserKey() },
  })
  return data.data
}

export async function fetchEngagement() {
  const { data } = await api.get('/knowledge/engagement', {
    params: { userKey: getUserKey() },
  })
  return data.data || {}
}

export async function toggleLike(id: string) {
  const { data } = await api.post(`/knowledge/articles/${id}/like`, { userKey: getUserKey() })
  return data.data
}

export async function toggleFavorite(id: string) {
  const { data } = await api.post(`/knowledge/articles/${id}/favorite`, { userKey: getUserKey() })
  return data.data
}

export async function fetchCategories() {
  const { data } = await api.get('/knowledge/categories')
  return data.data
}

export async function resetKnowledge() {
  const { data } = await api.post('/knowledge/reset')
  return data
}
