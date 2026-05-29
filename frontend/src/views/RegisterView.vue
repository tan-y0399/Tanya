<template>
  <div class="register-page">
    <div class="bg-shapes">
      <div class="shape shape-1"></div>
      <div class="shape shape-2"></div>
    </div>

    <div class="register-card">
      <div class="register-header">
        <div class="brand">
          <svg viewBox="0 0 40 40" width="36" height="36">
            <defs>
              <linearGradient id="brandGradReg" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#2563eb"/>
                <stop offset="100%" style="stop-color:#6366f1"/>
              </linearGradient>
            </defs>
            <rect x="4" y="20" width="10" height="16" rx="2" fill="url(#brandGradReg)" opacity="0.5"/>
            <rect x="16" y="12" width="10" height="24" rx="2" fill="url(#brandGradReg)" opacity="0.75"/>
            <rect x="28" y="4" width="8" height="32" rx="2" fill="url(#brandGradReg)"/>
          </svg>
        </div>
        <h2 class="brand-title">KylinOps</h2>
        <p class="brand-sub">创建普通用户账号</p>
      </div>

      <!-- 注册方式切换 -->
      <div class="register-tabs">
        <button :class="{ active: regMode === 'username' }" type="button" @click="regMode = 'username'">用户名注册</button>
        <button :class="{ active: regMode === 'email' }" type="button" @click="regMode = 'email'">邮箱注册</button>
      </div>

      <div class="form-area">
        <!-- 用户名注册 -->
        <template v-if="regMode === 'username'">
          <div class="field">
            <label>用户名</label>
            <input v-model="regUsername" type="text" class="text-input" placeholder="设置用户名" @keyup.enter="handleUsernameRegister" />
          </div>
          <div class="field">
            <label>密码</label>
            <input v-model="regPassword" type="password" class="text-input" placeholder="设置密码（至少6位）" @keyup.enter="handleUsernameRegister" />
          </div>
          <div class="field">
            <label>确认密码</label>
            <input v-model="regConfirmPwd" type="password" class="text-input" placeholder="再次输入密码" @keyup.enter="handleUsernameRegister" />
          </div>
          <button class="register-btn" :disabled="loading" @click="handleUsernameRegister">
            {{ loading ? '注册中...' : '创建账号' }}
          </button>
        </template>

        <!-- 邮箱注册 -->
        <template v-else>
          <div class="field">
            <label>邮箱</label>
            <div class="inline-row">
              <input v-model="email" type="email" class="text-input" placeholder="请输入邮箱地址" @keyup.enter="handleSendCode" />
              <button class="secondary-btn" :disabled="sendingCode || !email" @click="handleSendCode">
                {{ sendingCode ? '发送中...' : codeSent ? '重新发送' : '发送验证码' }}
              </button>
            </div>
          </div>
          <div class="field">
            <label>验证码</label>
            <input v-model="code" type="text" class="text-input" placeholder="请输入邮箱验证码" @keyup.enter="handleEmailRegister" />
          </div>
          <div class="field">
            <label>密码</label>
            <input v-model="emailPassword" type="password" class="text-input" placeholder="请设置密码" @keyup.enter="handleEmailRegister" />
          </div>
          <button class="register-btn" :disabled="loadingEmail" @click="handleEmailRegister">
            {{ loadingEmail ? '注册中...' : '创建账号' }}
          </button>
        </template>

        <div class="hint">注册账号默认角色为「普通用户」</div>

        <router-link class="back-link" to="/login">返回登录</router-link>
      </div>

      <div class="error-msg" v-if="errorMsg">{{ errorMsg }}</div>
      <div class="success-msg" v-if="successMsg">{{ successMsg }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { registerByEmail, sendEmailCode } from '@/api/auth'
import api from '@/api/index'

const router = useRouter()

const regMode = ref<'username' | 'email'>('username')

// 用户名注册
const regUsername = ref('')
const regPassword = ref('')
const regConfirmPwd = ref('')
const loading = ref(false)

// 邮箱注册
const email = ref('')
const code = ref('')
const emailPassword = ref('')
const loadingEmail = ref(false)
const sendingCode = ref(false)
const codeSent = ref(false)

const errorMsg = ref('')
const successMsg = ref('')

// ========== 用户名注册 ==========
async function handleUsernameRegister() {
  errorMsg.value = ''
  successMsg.value = ''
  if (!regUsername.value.trim() || !regPassword.value || !regConfirmPwd.value) {
    errorMsg.value = '请完整填写注册信息'
    return
  }
  if (regUsername.value.trim().length < 2) {
    errorMsg.value = '用户名至少2个字符'
    return
  }
  if (regPassword.value.length < 6) {
    errorMsg.value = '密码至少6位'
    return
  }
  if (regPassword.value !== regConfirmPwd.value) {
    errorMsg.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    const { data } = await api.post('/auth/register', {
      username: regUsername.value.trim(),
      password: regPassword.value,
    })
    if (data.code === 0) {
      successMsg.value = '注册成功，正在跳转到登录页...'
      setTimeout(() => router.push('/login'), 1200)
    } else {
      errorMsg.value = data.message || '注册失败'
    }
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail || '注册失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

// ========== 邮箱注册 ==========
async function handleSendCode() {
  errorMsg.value = ''
  successMsg.value = ''
  if (!email.value) { errorMsg.value = '请输入邮箱地址'; return }
  sendingCode.value = true
  try {
    const res = await sendEmailCode(email.value, 'register')
    if (res.code === 0) { codeSent.value = true; successMsg.value = '验证码已发送，请查收邮箱' }
    else { errorMsg.value = res.message || '发送验证码失败' }
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail || '发送验证码失败'
  } finally { sendingCode.value = false }
}

async function handleEmailRegister() {
  errorMsg.value = ''
  successMsg.value = ''
  if (!email.value || !code.value || !emailPassword.value) {
    errorMsg.value = '请完整填写注册信息'; return
  }
  loadingEmail.value = true
  try {
    const res = await registerByEmail(email.value, code.value, emailPassword.value)
    if (res.code === 0) {
      successMsg.value = '注册成功，正在跳转到登录页...'
      setTimeout(() => router.push('/login'), 1200)
    } else {
      errorMsg.value = res.message || '注册失败'
    }
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail || '注册失败，请稍后重试'
  } finally { loadingEmail.value = false }
}
</script>

<style lang="scss" scoped>
.register-page {
  height: 100vh; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #f0f4ff 0%, #e8f0fe 50%, #f0f4ff 100%);
  position: relative; overflow: hidden;
}

.bg-shapes {
  position: absolute; inset: 0; pointer-events: none;
  .shape { position: absolute; border-radius: 50%; opacity: 0.05; }
  .shape-1 { width: 600px; height: 600px; background: #2563eb; top: -200px; right: -150px; }
  .shape-2 { width: 400px; height: 400px; background: #6366f1; bottom: -100px; left: -80px; }
}

.register-card {
  position: relative; z-index: 10;
  background: #fff; border-radius: 20px;
  box-shadow: 0 8px 40px rgba(0,0,0,0.06), 0 2px 8px rgba(0,0,0,0.03);
  width: 420px; padding: 40px;
}

.register-header {
  text-align: center; margin-bottom: 20px;
  .brand { margin-bottom: 8px; }
  .brand-title { font-size: 22px; font-weight: 700; color: #1e293b; letter-spacing: 2px; margin: 0; }
  .brand-sub { font-size: 12px; color: #94a3b8; margin: 4px 0 0; }
}

.register-tabs {
  display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
  margin-bottom: 20px; padding: 5px;
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;
  button {
    border: none; background: transparent; color: #64748b;
    font-size: 13px; font-weight: 600; padding: 9px 12px; border-radius: 9px;
    cursor: pointer; transition: all 0.2s;
    &.active { background: linear-gradient(135deg, #2563eb, #4f46e5); color: #fff; box-shadow: 0 4px 14px rgba(37,99,235,0.18); }
  }
}

.form-area {
  display: flex; flex-direction: column; gap: 14px;
}

.field {
  label { display: block; font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; }
}

.inline-row {
  display: flex; gap: 10px;
}

.text-input {
  width: 100%; border: 1.5px solid #e2e8f0; border-radius: 10px; padding: 12px 14px;
  font-size: 14px; color: #1e293b; outline: none; background: #fff;
  transition: border-color 0.2s;
  &::placeholder { color: #cbd5e1; }
  &:focus { border-color: #2563eb; }
}

.secondary-btn {
  flex: 0 0 auto; min-width: 100px;
  border: 1px solid #dbe4f3; background: #f8fafc; color: #334155;
  border-radius: 10px; padding: 0 14px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all 0.2s;
  &:hover:not(:disabled) { border-color: #93c5fd; background: #eff6ff; }
  &:disabled { opacity: 0.6; cursor: not-allowed; }
}

.hint { font-size: 12px; color: #94a3b8; text-align: center; }

.register-btn {
  width: 100%; padding: 13px; border: none; border-radius: 10px;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff; font-size: 16px; font-weight: 600; letter-spacing: 4px;
  cursor: pointer; transition: all 0.2s;
  &:hover:not(:disabled) { box-shadow: 0 4px 16px rgba(37,99,235,0.3); transform: translateY(-1px); }
  &:disabled { opacity: 0.5; cursor: not-allowed; }
}

.back-link { text-align: center; color: #2563eb; font-size: 13px; font-weight: 600; text-decoration: none; margin-top: 4px; }

.error-msg, .success-msg { margin-top: 16px; padding: 10px 16px; border-radius: 8px; font-size: 13px; text-align: center; }
.error-msg { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
.success-msg { background: #ecfdf5; border: 1px solid #a7f3d0; color: #047857; }
</style>
