import { createRouter, createWebHashHistory } from 'vue-router'

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
      path: '/',
      component: () => import('@/components/layout/AppLayout.vue'),
      redirect: '/dashboard',
      children: [
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

// 简单鉴权守卫
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (to.name !== 'Login' && !token) {
    next({ name: 'Login' })
  } else if (to.name === 'Login' && token) {
    next({ name: 'Dashboard' })
  } else {
    next()
  }
})

export default router
