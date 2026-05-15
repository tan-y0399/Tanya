<template>
  <div class="home-page">
    <el-container class="layout">
      <el-aside class="sidebar" width="280px">
        <div class="brand">
          <div class="brand__title">麒麟智能运维 Agent</div>
          <div class="brand__desc">安全 · 可解释 · 可审计</div>
        </div>
        <el-button type="primary" class="session-button" @click="drawerVisible = true">会话列表</el-button>
        <el-menu :default-active="activeMenu" class="menu" @select="handleMenuSelect">
          <el-menu-item index="chat">对话中心</el-menu-item>
          <el-menu-item index="dashboard">系统看板</el-menu-item>
          <el-menu-item index="approval">审批中心</el-menu-item>
          <el-menu-item index="audit">审计日志</el-menu-item>
        </el-menu>
      </el-aside>

      <el-container>
        <el-header class="header">
          <div>
            <div class="header__title">运维对话</div>
            <div class="header__subtitle">自然语言驱动的安全智能运维闭环</div>
          </div>
          <div class="header__status">TraceId: {{ traceId }}</div>
        </el-header>

        <el-main class="main">
          <el-row :gutter="16" class="overview-cards">
            <el-col :xs="24" :sm="12" :lg="6">
              <el-card shadow="hover">
                <div class="metric-label">会话状态</div>
                <div class="metric-value">{{ sessionStatus }}</div>
              </el-card>
            </el-col>
            <el-col :xs="24" :sm="12" :lg="6">
              <el-card shadow="hover">
                <div class="metric-label">风险等级</div>
                <div class="metric-value warning">{{ riskLevel }}</div>
              </el-card>
            </el-col>
            <el-col :xs="24" :sm="12" :lg="6">
              <el-card shadow="hover">
                <div class="metric-label">待审批</div>
                <div class="metric-value">{{ pendingApprovals }}</div>
              </el-card>
            </el-col>
            <el-col :xs="24" :sm="12" :lg="6">
              <el-card shadow="hover">
                <div class="metric-label">工具调用</div>
                <div class="metric-value success">{{ toolCalls }}</div>
              </el-card>
            </el-col>
          </el-row>

          <el-row :gutter="16" class="workspace">
            <el-col :xs="24" :lg="15">
              <component :is="currentMainComponent" v-bind="mainComponentProps" />
            </el-col>

            <el-col :xs="24" :lg="9">
              <el-space direction="vertical" fill size="16">
                <el-card shadow="never">
                  <template #header>
                    <div class="panel-header">
                      <span>执行摘要</span>
                      <el-tag type="warning">待确认</el-tag>
                    </div>
                  </template>

                  <el-descriptions :column="1" border>
                    <el-descriptions-item label="当前会话">{{ sessionId }}</el-descriptions-item>
                    <el-descriptions-item label="当前步骤">意图识别</el-descriptions-item>
                    <el-descriptions-item label="安全策略">白名单工具 + 风险分级</el-descriptions-item>
                    <el-descriptions-item label="审计状态">已开启</el-descriptions-item>
                  </el-descriptions>
                </el-card>

                <SystemDashboard v-if="activeMenu === 'dashboard'" />
                <ApprovalPanel
                  v-else-if="activeMenu === 'approval'"
                  action="重启 nginx 服务"
                  reason="检测到服务异常，建议在审批后执行"
                  @approve="openApprovalDialog"
                  @reject="openApprovalDialog"
                />
                <AuditPanel
                  v-else-if="activeMenu === 'audit'"
                  :items="auditItems"
                />
              </el-space>
            </el-col>
          </el-row>
        </el-main>
      </el-container>
    </el-container>

    <SessionDrawer
      v-model="drawerVisible"
      :sessions="sessions"
      :active-session-id="sessionId"
      @select="handleSessionSelect"
      @create="handleCreateSession"
    />
    <ApprovalDialog
      v-model="approvalDialogVisible"
      action="重启 nginx 服务"
      reason="检测到服务异常，建议在审批后执行"
      risk-level="L3"
      @approve="handleApproval(true)"
      @reject="handleApproval(false)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useAppStore } from '../stores/app'
import { createSession, fetchMessages, fetchSessions, type SessionItem } from '../api/session'
import ChatPanel from '../components/ChatPanel.vue'
import SystemDashboard from '../components/SystemDashboard.vue'
import ApprovalPanel from '../components/ApprovalPanel.vue'
import AuditPanel from '../components/AuditPanel.vue'
import SessionDrawer from '../components/SessionDrawer.vue'
import ApprovalDialog from '../components/ApprovalDialog.vue'

const store = useAppStore()
const activeMenu = ref('chat')
const drawerVisible = ref(false)
const approvalDialogVisible = ref(false)
const sessionId = computed(() => store.sessionId)
const traceId = computed(() => store.traceId)
const sessionStatus = ref('进行中')
const riskLevel = ref('L2')
const pendingApprovals = ref(1)
const toolCalls = ref(3)
const sessions = ref<SessionItem[]>([])
const auditItems = ref([
  { traceId: 'trace-demo-0001', event: 'tool_call', detail: '调用 get_system_info 成功', createdAt: '2026-05-15 10:05:00' },
  { traceId: 'trace-demo-0002', event: 'approval', detail: '高风险操作已进入审批流程', createdAt: '2026-05-15 10:06:30' },
])

const loadSessions = async () => {
  sessions.value = await fetchSessions()
}

onMounted(loadSessions)

const currentMainComponent = computed(() => {
  if (activeMenu.value === 'dashboard') return SystemDashboard
  if (activeMenu.value === 'approval') return ApprovalPanel
  if (activeMenu.value === 'audit') return AuditPanel
  return ChatPanel
})

const mainComponentProps = computed(() => {
  if (activeMenu.value === 'approval') {
    return {
      action: '重启 nginx 服务',
      reason: '检测到服务异常，建议在审批后执行',
    }
  }

  if (activeMenu.value === 'audit') {
    return { items: auditItems.value }
  }

  return { sessionId: sessionId.value, traceId: traceId.value }
})

const handleMenuSelect = (key: string) => {
  activeMenu.value = key
}

const handleSessionSelect = async (newSessionId: string) => {
  store.sessionId = newSessionId
  activeMenu.value = 'chat'
  drawerVisible.value = false
  await fetchMessages(newSessionId)
  ElMessage.success(`已切换到会话：${newSessionId}`)
}

const handleCreateSession = async () => {
  const created = await createSession('新会话')
  await loadSessions()
  store.sessionId = created.sessionId
  activeMenu.value = 'chat'
  drawerVisible.value = false
  ElMessage.success(`已创建会话：${created.sessionId}`)
}

const openApprovalDialog = () => {
  approvalDialogVisible.value = true
}

const handleApproval = (approved: boolean) => {
  approvalDialogVisible.value = false
  ElMessage.success(approved ? '审批已通过' : '审批已拒绝')
}

watch(sessionId, () => {
  loadSessions()
})
</script>
