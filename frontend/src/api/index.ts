import axios from 'axios'
import router from '@/router'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截：注入 token + traceId
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  config.headers['X-Trace-Id'] = `trace-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
  return config
})

// 故障转移备用服务器
const FALLBACK_SERVERS = [
  { label: '麒麟服务器 1', url: 'http://192.168.163.15' },
  { label: '麒麟服务器 2', url: 'http://192.168.163.16' },
]

// 响应拦截：401 → 跳登录，网络错误 → 显示备用入口提示
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      router.push('/login')
    }
    // 网络错误 → 触发故障转移提示（不自动跳转）
    if (!err.response && err.code !== 'ERR_CANCELED') {
      const detail = { servers: FALLBACK_SERVERS }
      document.dispatchEvent(new CustomEvent('api:disconnected', { detail }))
    } else {
      document.dispatchEvent(new CustomEvent('api:connected'))
    }
    return Promise.reject(err)
  },
)

export { FALLBACK_SERVERS }

export default api
