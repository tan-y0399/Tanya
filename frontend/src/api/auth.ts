import api from './index'

// 账号密码登录
export async function login(username: string, password: string) {
  const { data } = await api.post('/auth/login', { username, password })
  return data
}

export async function logout() {
  const { data } = await api.post('/auth/logout')
  return data
}

export async function getCurrentUser() {
  const { data } = await api.get('/auth/me')
  return data.data
}

// 短信验证码
export async function sendSms(phone: string) {
  const { data } = await api.post('/auth/send-sms', { phone })
  return data
}

// 手机号+验证码登录
export async function loginByPhone(phone: string, code: string) {
  const { data } = await api.post('/auth/login-by-phone', { phone, code })
  return data
}

// 微信扫码
export async function getWechatQrcode() {
  const { data } = await api.get('/auth/wechat/qrcode')
  return data.data
}

export async function checkWechatStatus(ticket: string) {
  const { data } = await api.get(`/auth/wechat/status/${ticket}`)
  return data.data
}

// 邮箱验证码
export async function sendEmailCode(email: string, purpose: string = 'register') {
  const { data } = await api.post('/auth/send-email-code', { email, purpose })
  return data
}

// 邮箱注册
export async function registerByEmail(email: string, code: string, password: string) {
  const { data } = await api.post('/auth/register-by-email', { email, code, password })
  return data
}

// 邮箱+密码登录
export async function loginByEmail(email: string, password: string) {
  const { data } = await api.post('/auth/login-by-email', { email, password })
  return data
}
