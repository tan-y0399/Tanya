import axios from 'axios'
import router from '@/router'
import { useUserStore } from '@/stores/user'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  config.headers['X-Trace-Id'] = `trace-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      const userStore = useUserStore()
      userStore.logout()
      router.push('/login')
    }
    if (!err.response && err.code !== 'ERR_CANCELED') {
      document.dispatchEvent(new CustomEvent('api:disconnected'))
    } else {
      document.dispatchEvent(new CustomEvent('api:connected'))
    }
    return Promise.reject(err)
  },
)

export default api
