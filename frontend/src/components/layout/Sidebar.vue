<template>
  <aside class="sidebar">
    <!-- Logo -->
    <div class="sidebar-logo" @click="$router.push(isAdmin ? '/knowledge' : '/chat')">
      <div class="logo-icon">
        <svg viewBox="0 0 40 40" width="36" height="36">
          <defs>
            <linearGradient id="lg2" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style="stop-color:#2563eb"/>
              <stop offset="100%" style="stop-color:#6366f1"/>
            </linearGradient>
          </defs>
          <rect x="4" y="20" width="10" height="16" rx="2" fill="url(#lg2)" opacity="0.5"/>
          <rect x="16" y="12" width="10" height="24" rx="2" fill="url(#lg2)" opacity="0.75"/>
          <rect x="28" y="4" width="8" height="32" rx="2" fill="url(#lg2)"/>
        </svg>
      </div>
      <div class="logo-text">
        <span class="logo-title">KylinOps</span>
        <span class="logo-subtitle">智能运维 Agent</span>
      </div>
    </div>

    <div class="sidebar-divider"></div>

    <!-- 导航菜单 -->
    <nav class="sidebar-nav">
      <!-- ===== 管理员菜单 ===== -->
      <template v-if="isAdmin">
        <router-link to="/admin" class="nav-item" :class="{ active: $route.path === '/admin' }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <rect x="2" y="2" width="14" height="14" rx="2" stroke="currentColor" stroke-width="1.5"/>
            <path d="M5 7h8M5 11h4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
          <span>管理员工作台</span>
        </router-link>
        <router-link to="/knowledge" class="nav-item" :class="{ active: $route.path === '/knowledge' }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M3 4h12v11a2 2 0 01-2 2H5a2 2 0 01-2-2V4z" stroke="currentColor" stroke-width="1.5"/>
            <path d="M6 7h6M6 10h4M6 13h3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
          <span>知识库</span>
        </router-link>
        <router-link to="/settings" class="nav-item" :class="{ active: $route.path === '/settings' }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <circle cx="9" cy="9" r="2.5" stroke="currentColor" stroke-width="1.5"/>
            <path d="M9 1.5v2M9 14.5v2M1.5 9h2M14.5 9h2M3.4 3.4l1.4 1.4M13.2 13.2l1.4 1.4M3.4 14.6l1.4-1.4M13.2 4.8l1.4-1.4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
          <span>系统设置</span>
        </router-link>
        <router-link to="/admin/feedback" class="nav-item" :class="{ active: $route.path === '/admin/feedback' }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M2 4h14v10a1 1 0 01-1 1H3a1 1 0 01-1-1V4z" stroke="currentColor" stroke-width="1.5"/>
            <path d="M5 7h8M5 10h6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
          <span>反馈</span>
        </router-link>
        <router-link to="/approval" class="nav-item" :class="{ active: $route.path === '/approval' }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M3 10l3 3 5-6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <span>审批管理</span>
          <span class="nav-badge danger" v-if="pendingCount">{{ pendingCount }}</span>
        </router-link>
        <router-link to="/audit" class="nav-item" :class="{ active: $route.path === '/audit' }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M3 4h12M3 8h8M3 12h5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <circle cx="14" cy="13" r="3" stroke="currentColor" stroke-width="1.5"/>
          </svg>
          <span>审计日志</span>
        </router-link>
        <router-link to="/alerts" class="nav-item" :class="{ active: $route.path === '/alerts' }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M9 2.5a4.5 4.5 0 00-4.5 4.5v2.1l-.9 1.8a1 1 0 00.9 1.5h9a1 1 0 00.9-1.5l-.9-1.8V7A4.5 4.5 0 009 2.5z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
            <path d="M7.5 14a1.5 1.5 0 003 0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <span>告警中心</span>
        </router-link>
      </template>

      <!-- ===== 用户菜单 ===== -->
      <template v-else>
        <router-link to="/chat" class="nav-item" :class="{ active: $route.path.startsWith('/chat') }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <rect x="2" y="3" width="14" height="11" rx="2" stroke="currentColor" stroke-width="1.5"/>
            <path d="M5 7h4M5 10h2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
          <span>智能对话</span>
          <span class="nav-badge" v-if="activeChatCount">{{ activeChatCount }}</span>
        </router-link>
        <router-link to="/audit" class="nav-item" :class="{ active: $route.path === '/audit' }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M3 4h12M3 8h8M3 12h5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <circle cx="14" cy="13" r="3" stroke="currentColor" stroke-width="1.5"/>
          </svg>
          <span>审计日志</span>
        </router-link>
        <router-link to="/approval" class="nav-item" :class="{ active: $route.path === '/approval' }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M3 10l3 3 5-6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <span>审批管理</span>
          <span class="nav-badge danger" v-if="pendingCount">{{ pendingCount }}</span>
        </router-link>
        <router-link to="/knowledge" class="nav-item" :class="{ active: $route.path === '/knowledge' }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M3 4h12v11a2 2 0 01-2 2H5a2 2 0 01-2-2V4z" stroke="currentColor" stroke-width="1.5"/>
            <path d="M6 7h6M6 10h4M6 13h3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
          <span>知识库</span>
        </router-link>
        <router-link to="/servers" class="nav-item" :class="{ active: $route.path === '/servers' }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <rect x="3" y="3" width="12" height="12" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
            <line x1="3" y1="7" x2="15" y2="7" stroke="currentColor" stroke-width="1.5"/>
            <line x1="3" y1="11" x2="15" y2="11" stroke="currentColor" stroke-width="1.5"/>
            <circle cx="6" cy="5" r="1" fill="currentColor"/>
            <circle cx="9" cy="5" r="1" fill="currentColor"/>
            <circle cx="12" cy="5" r="1" fill="currentColor"/>
          </svg>
          <span>服务器</span>
        </router-link>
        <router-link to="/alerts" class="nav-item" :class="{ active: $route.path === '/alerts' }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M9 2.5a4.5 4.5 0 00-4.5 4.5v2.1l-.9 1.8a1 1 0 00.9 1.5h9a1 1 0 00.9-1.5l-.9-1.8V7A4.5 4.5 0 009 2.5z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
            <path d="M7.5 14a1.5 1.5 0 003 0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <span>告警中心</span>
        </router-link>
        <router-link to="/dashboard" class="nav-item" :class="{ active: $route.path === '/dashboard' }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <rect x="2" y="2" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.5"/>
            <rect x="10" y="2" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.5"/>
            <rect x="2" y="10" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.5"/>
            <rect x="10" y="10" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.5"/>
          </svg>
          <span>仪表盘</span>
        </router-link>
        <router-link to="/settings" class="nav-item" :class="{ active: $route.path === '/settings' }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <circle cx="9" cy="9" r="2.5" stroke="currentColor" stroke-width="1.5"/>
            <path d="M9 1.5v2M9 14.5v2M1.5 9h2M14.5 9h2M3.4 3.4l1.4 1.4M13.2 13.2l1.4 1.4M3.4 14.6l1.4-1.4M13.2 4.8l1.4-1.4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
          <span>系统设置</span>
        </router-link>
        <router-link to="/user/feedback" class="nav-item" :class="{ active: $route.path === '/user/feedback' }">
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M2 4h14v10a1 1 0 01-1 1H3a1 1 0 01-1-1V4z" stroke="currentColor" stroke-width="1.5"/>
            <path d="M5 7h8M5 10h6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
          <span>反馈</span>
        </router-link>
      </template>
    </nav>

    <div class="sidebar-spacer"></div>

    <!-- 用户区 -->
    <div class="sidebar-user">
      <div class="user-avatar">{{ userInitial }}</div>
      <div class="user-info">
        <div class="user-name">{{ username }}</div>
        <div class="user-role">{{ roleLabel }}</div>
      </div>
      <svg class="logout-icon" @click="doLogout" width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M6 3H3v10h3M11 11l3-3-3-3M14 8H6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { logout } from '@/api/auth'
import { getPendingApprovals } from '@/api/approval'
import { getSessions } from '@/api/chat'

const router = useRouter()
const userStore = useUserStore()

const isAdmin = computed(() => userStore.userInfo?.role === 'admin')
const username = computed(() => userStore.userInfo?.username || '用户')
const userInitial = computed(() => username.value.charAt(0).toUpperCase())
const roleLabel = computed(() => {
  const m: Record<string, string> = { admin: '运维管理员', auditor: '审计员', deployer: '部署员', user: '普通用户' }
  return m[userStore.userInfo?.role || ''] || '普通用户'
})

const activeChatCount = ref(0)
const pendingCount = ref(0)
let statusTimer: ReturnType<typeof setInterval> | null = null

async function doLogout() {
  try { await logout() } catch {}
  userStore.logout()
  router.push('/login')
}

async function refreshStatus() {
  try {
    const sessions = await getSessions(1, 1)
    activeChatCount.value = sessions?.total || 0
  } catch {}
  try {
    const pending = await getPendingApprovals()
    pendingCount.value = pending?.total || 0
  } catch {}
}

onMounted(() => {
  refreshStatus()
  statusTimer = setInterval(refreshStatus, 15000)
})

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer)
})
</script>

<style lang="scss" scoped>
.sidebar {
  width: 260px;
  min-width: 260px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border-right: 1px solid #e2e8f0;
  padding: 16px;
  z-index: 100;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 4px 16px;
  cursor: pointer;
  .logo-text {
    display: flex;
    flex-direction: column;
  }
  .logo-title {
    font-size: 18px;
    font-weight: 700;
    color: #2563eb;
    letter-spacing: 1px;
  }
  .logo-subtitle {
    font-size: 11px;
    color: #94a3b8;
  }
}

.sidebar-divider {
  height: 1px;
  background: #f1f5f9;
  margin: 0 0 8px;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: all 0.15s ease;
  position: relative;
  .nav-icon { flex-shrink: 0; }
  &:hover {
    background: #f8fafc;
    color: #1e293b;
  }
  &.active {
    background: #eff6ff;
    color: #2563eb;
    font-weight: 600;
  }
}

.nav-badge {
  margin-left: auto;
  background: #eff6ff;
  color: #2563eb;
  padding: 1px 7px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  &.danger {
    background: #fef2f2;
    color: #ef4444;
  }
}

.sidebar-spacer {
  flex: 1;
}

.sidebar-user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 8px;
  border-top: 1px solid #f1f5f9;
  .user-avatar {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background: linear-gradient(135deg, #2563eb, #6366f1);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 14px;
    color: #fff;
    flex-shrink: 0;
  }
  .user-info {
    flex: 1;
    min-width: 0;
    .user-name { font-size: 13px; color: #1e293b; font-weight: 500; }
    .user-role { font-size: 11px; color: #94a3b8; }
  }
  .logout-icon {
    color: #94a3b8;
    cursor: pointer;
    flex-shrink: 0;
    &:hover { color: #ef4444; }
  }
}
</style>
