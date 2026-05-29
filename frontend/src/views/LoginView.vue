<template>
  <div class="login-page">
    <div class="bg-shapes">
      <div class="shape shape-1"></div>
      <div class="shape shape-2"></div>
    </div>

    <div class="login-card">
      <div class="login-header">
        <div class="brand">
          <svg viewBox="0 0 40 40" width="36" height="36">
            <defs>
              <linearGradient id="brandGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#2563eb"/>
                <stop offset="100%" style="stop-color:#6366f1"/>
              </linearGradient>
            </defs>
            <rect x="4" y="20" width="10" height="16" rx="2" fill="url(#brandGrad)" opacity="0.5"/>
            <rect x="16" y="12" width="10" height="24" rx="2" fill="url(#brandGrad)" opacity="0.75"/>
            <rect x="28" y="4" width="8" height="32" rx="2" fill="url(#brandGrad)"/>
          </svg>
        </div>
        <h2 class="brand-title">KylinOps</h2>
        <p class="brand-sub">麒麟智能运维 Agent</p>
      </div>

      <div class="role-tabs" role="tablist" aria-label="登录角色切换">
        <button
          class="role-tab"
          :class="{ active: activeRole === 'admin' }"
          type="button"
          @click="activeRole = 'admin'"
        >
          管理员登录
        </button>
        <button
          class="role-tab"
          :class="{ active: activeRole === 'user' }"
          type="button"
          @click="activeRole = 'user'"
        >
          用户登录
        </button>
      </div>

      <div class="form-area">
        <div class="field">
          <label>用户名</label>
          <input
            v-model="username"
            type="text"
            class="text-input"
            :placeholder="activeRole === 'admin' ? '请输入管理员用户名' : '请输入用户名'"
            @keyup.enter="handleLogin"
          />
        </div>
        <div class="field">
          <label>密码</label>
          <input
            v-model="password"
            type="password"
            class="text-input"
            :placeholder="activeRole === 'admin' ? '请输入管理员密码' : '请输入密码'"
            @keyup.enter="handleLogin"
          />
        </div>
        <div class="hint">
          {{ activeRole === 'admin' ? '默认管理员 admin / admin123' : '默认用户 lk / lk666' }}
        </div>
        <button class="login-btn" :disabled="loading" @click="handleLogin">
          {{ loading ? '验证中...' : activeRoleLabel }}
        </button>
        <router-link class="register-link" to="/register">没有账号？去注册 →</router-link>
      </div>

      <div class="error-msg" v-if="errorMsg">{{ errorMsg }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { login } from '@/api/auth'

const router = useRouter()
const userStore = useUserStore()

const username = ref('admin')
const password = ref('')
const activeRole = ref<'admin' | 'user'>('admin')
const activeRoleLabel = computed(() => (activeRole.value === 'admin' ? '管理员登录' : '用户登录'))
const loading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  errorMsg.value = ''
  if (!username.value || !password.value) {
    errorMsg.value = '请输入用户名和密码'
    return
  }
  loading.value = true

  // 安全超时：10 秒后自动重置，防止一直转圈
  const safetyTimer = setTimeout(() => {
    if (loading.value) {
      loading.value = false
      errorMsg.value = '登录超时，请检查网络连接后重试'
    }
  }, 10000)

  try {
    const res = await login(username.value, password.value, activeRole.value)
    clearTimeout(safetyTimer)
    if (res.code === 0) {
      const userRole = res.data.user?.role
      userStore.setToken(res.data.accessToken)
      userStore.setUserInfo(res.data.user)
      router.push(userRole === 'admin' ? '/knowledge' : '/chat')
    } else {
      errorMsg.value = res.message || '登录失败'
    }
  } catch (e: any) {
    clearTimeout(safetyTimer)
    if (e?.code === 'ERR_NETWORK' || e?.code === 'ECONNABORTED' || !e?.response) {
      errorMsg.value = '无法连接服务器，请确认后端已启动'
    } else {
      errorMsg.value = e?.response?.data?.detail || '登录失败，请检查用户名和密码'
    }
  } finally {
    clearTimeout(safetyTimer)
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f0f4ff 0%, #e8f0fe 50%, #f0f4ff 100%);
  position: relative;
  overflow: hidden;
}

.bg-shapes {
  position: absolute; inset: 0; pointer-events: none;
  .shape { position: absolute; border-radius: 50%; opacity: 0.05; }
  .shape-1 { width: 600px; height: 600px; background: #2563eb; top: -200px; right: -150px; }
  .shape-2 { width: 400px; height: 400px; background: #6366f1; bottom: -100px; left: -80px; }
}

.login-card {
  position: relative; z-index: 10;
  background: #fff; border-radius: 20px;
  box-shadow: 0 8px 40px rgba(0,0,0,0.06), 0 2px 8px rgba(0,0,0,0.03);
  width: 400px; padding: 48px 40px 36px;
}

.login-header {
  text-align: center; margin-bottom: 24px;
  .brand { margin-bottom: 8px; }
  .brand-title { font-size: 22px; font-weight: 700; color: #1e293b; letter-spacing: 2px; margin: 0; }
  .brand-sub { font-size: 12px; color: #94a3b8; margin: 4px 0 0; }
}

.role-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 20px;
  padding: 6px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
}

.role-tab {
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 14px;
  font-weight: 600;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  &.active {
    background: linear-gradient(135deg, #2563eb, #4f46e5);
    color: #fff;
    box-shadow: 0 4px 14px rgba(37,99,235,0.18);
  }
}

.form-area {
  display: flex; flex-direction: column; gap: 16px;
}

.field {
  label { display: block; font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; }
}

.text-input {
  width: 100%; border: 1.5px solid #e2e8f0; border-radius: 10px; padding: 12px 14px;
  font-size: 14px; color: #1e293b; outline: none; background: #fff;
  transition: border-color 0.2s;
  &::placeholder { color: #cbd5e1; }
  &:focus { border-color: #2563eb; }
}

.hint { font-size: 12px; color: #94a3b8; text-align: center; }

.login-btn {
  width: 100%; padding: 13px; border: none; border-radius: 10px;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff; font-size: 16px; font-weight: 600; letter-spacing: 4px;
  cursor: pointer; transition: all 0.2s;
  &:hover:not(:disabled) { box-shadow: 0 4px 16px rgba(37,99,235,0.3); transform: translateY(-1px); }
  &:disabled { opacity: 0.5; cursor: not-allowed; }
}

.register-link {
  text-align: center;
  color: #2563eb;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transition: color 0.2s;
  &:hover { color: #6366f1; }
}

.error-msg {
  margin-top: 16px; padding: 10px 16px; border-radius: 8px;
  background: #fef2f2; border: 1px solid #fecaca;
  color: #991b1b; font-size: 13px; text-align: center;
}
</style>
