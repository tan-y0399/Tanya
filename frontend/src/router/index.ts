import { createRouter, createWebHashHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: '登录' },
    },
    {
      path: '/register',
      name: 'Register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { title: '注册' },
    },
    {
      path: '/',
      component: () => import('@/components/layout/AppLayout.vue'),
      redirect: '/chat',
      children: [
        // 管理员工作台
        {
          path: 'admin',
          name: 'Admin',
          component: () => import('@/views/admin/AdminPage.vue'),
          meta: { title: '管理员工作台', role: 'admin' },
        },
        // 管理员反馈管理
        {
          path: 'admin/feedback',
          name: 'AdminFeedback',
          component: () => import('@/views/admin/FeedbackPage.vue'),
          meta: { title: '反馈管理', role: 'admin' },
        },
        // 兼容旧路由 /user → /chat
        {
          path: 'user',
          redirect: '/chat',
        },
        // 用户反馈
        {
          path: 'user/feedback',
          name: 'UserFeedback',
          component: () => import('@/views/user/FeedbackPage.vue'),
          meta: { title: '反馈' },
        },
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('@/views/DashboardPage.vue'),
          meta: { title: '运维仪表盘' },
        },
        {
          path: 'chat',
          name: 'Chat',
          component: () => import('@/views/ChatPage.vue'),
          meta: { title: '智能对话' },
        },
        {
          path: 'chat/:id',
          name: 'ChatSession',
          component: () => import('@/views/ChatPage.vue'),
          meta: { title: '会话详情' },
        },
        {
          path: 'audit',
          name: 'Audit',
          component: () => import('@/views/AuditPage.vue'),
          meta: { title: '审计日志' },
        },
        {
          path: 'approval',
          name: 'Approval',
          component: () => import('@/views/ApprovalPage.vue'),
          meta: { title: '审批管理' },
        },
        {
          path: 'alerts',
          name: 'Alerts',
          component: () => import('@/views/AlertsPage.vue'),
          meta: { title: '告警中心' },
        },
        {
          path: 'knowledge',
          name: 'Knowledge',
          component: () => import('@/views/KnowledgePage.vue'),
          meta: { title: '知识库' },
        },
        {
          path: 'servers',
          name: 'Servers',
          component: () => import('@/views/ServersPage.vue'),
          meta: { title: '服务器管理' },
        },
        {
          path: 'settings',
          name: 'Settings',
          component: () => import('@/views/SettingsPage.vue'),
          meta: { title: '系统设置' },
        },
      ],
    },
  ],
})

// 鉴权守卫 + 角色守卫
router.beforeEach((to, _from, next) => {
  const userStore = useUserStore()
  const token = userStore.token

  if (to.name !== 'Login' && !token) {
    next({ name: 'Login' })
    return
  }

  if (to.name === 'Login' && token) {
    // 已登录用户根据角色跳转
    const role = userStore.userInfo?.role || 'user'
    next({ name: role === 'admin' ? 'Knowledge' : 'Chat' })
    return
  }

  // 角色路由守卫
  if (to.meta.role) {
    const role = userStore.userInfo?.role || 'user'
    if (to.meta.role !== role) {
      // 角色不匹配，跳转到对应角色的默认页面
      next({ name: role === 'admin' ? 'Knowledge' : 'Chat' })
      return
    }
  }

  next()
})

export default router
