<template>
  <div class="chat-page">
    <!-- 左侧会话列表 -->
    <div class="sidebar-wrapper" :class="{ collapsed: sidebarCollapsed }">
      <SessionList
        v-if="!sidebarCollapsed"
        :sessions="chatStore.sessions"
        :activeId="chatStore.currentSessionId"
        @newSession="handleNewSession"
        @selectSession="handleSelectSession"
        @deleteSession="handleDeleteSession"
      />
      <!-- 收起时只保留展开按钮 -->
      <div v-else class="sidebar-collapsed-handle">
        <button class="expand-btn" @click="toggleSidebar" title="展开会话列表">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M9 4l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 中间对话区 -->
    <div class="chat-main">
      <!-- 顶部操作栏 -->
      <div class="chat-topbar">
        <div class="topbar-left">
          <button v-if="!sidebarCollapsed" class="collapse-btn" @click="toggleSidebar" title="收起会话列表">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M11 3L5 8l6 5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
          <span class="topbar-title" v-if="chatStore.messages.length">{{ chatStore.currentSessionId?.slice(0,12) || '' }}</span>
          <!-- 服务器选择器 -->
          <div class="server-selector">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" class="server-icon">
              <rect x="1" y="1" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.2"/>
              <rect x="8" y="1" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.2"/>
              <rect x="1" y="8" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.2"/>
              <rect x="8" y="8" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.2"/>
            </svg>
            <select v-model="selectedServerId" @change="handleServerChange">
              <option value="all">全部服务器</option>
              <option v-for="srv in serverList" :key="srv.id" :value="srv.id">
                {{ srv.name }} ({{ srv.host }})
              </option>
            </select>
            <span class="server-status-dot" :class="selectedServerStatus"></span>
          </div>
        </div>
        <button class="clear-btn" @click="handleClearMessages" title="清空当前对话">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 4h10M5 4V3a1 1 0 011-1h2a1 1 0 011 1v1M11 4v7a1 1 0 01-1 1H4a1 1 0 01-1-1V4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
          </svg>
          清空对话
        </button>
      </div>
      <div class="chat-messages" ref="msgContainer">
        <div class="welcome-area" v-if="!chatStore.messages.length">
          <div class="welcome-icon">
            <svg viewBox="0 0 64 64" width="64" height="64">
              <defs>
                <linearGradient id="wGrad2" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" style="stop-color:#2563eb"/>
                  <stop offset="100%" style="stop-color:#6366f1"/>
                </linearGradient>
              </defs>
              <rect x="7" y="32" width="14" height="25" rx="3" fill="url(#wGrad2)" opacity="0.35"/>
              <rect x="25" y="18" width="14" height="39" rx="3" fill="url(#wGrad2)" opacity="0.55"/>
              <rect x="43" y="7" width="14" height="50" rx="3" fill="url(#wGrad2)" opacity="0.85"/>
            </svg>
          </div>
          <h1 class="welcome-title">KylinOps 智能运维 Agent</h1>
          <p class="welcome-desc">基于 ReAct / Plan-Execute 混合推理架构，通过自然语言完成运维巡检、故障排查与资源管理</p>
          <div class="quick-actions">
            <button v-for="qa in quickActions" :key="qa" class="quick-btn" @click="handleQuickAction(qa)">
              {{ qa }}
            </button>
          </div>
        </div>

        <div v-for="group in groupedMessages" :key="group.id">
        <!-- 用户消息 -->
        <div v-if="group.type === 'user'" class="msg-wrapper msg-user">
          <button class="msg-delete-btn" @click="handleDeleteMessage(group.id)" title="删除">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M2 2l6 6M8 2l-6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
          <UserMessage :content="group.msg.content" :createdAt="group.msg.createdAt" />
        </div>

        <!-- Agent消息 + 工具结果嵌入在同一个气泡内 -->
        <div v-else-if="group.type === 'agent'" class="msg-wrapper msg-assistant">
          <button class="msg-delete-btn" @click="handleDeleteMessage(group.id)" title="删除">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M2 2l6 6M8 2l-6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
          <AgentMessage
            :content="group.msg.content"
            :traceId="group.msg.traceId"
            :createdAt="group.msg.createdAt"
            @viewTrace="openTraceTimeline"
          />
          <!-- 工具结果嵌入在Agent回答下方 -->
          <ToolCallCard
            v-for="tc in group.tools"
            :key="tc.id"
            :tool="tc"
            @viewDetail="openToolDetail"
          />
        </div>

        <!-- 系统消息 -->
        <div v-else-if="group.type === 'system'" class="msg-wrapper msg-system">
          <div class="system-msg">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" class="sys-icon">
              <path d="M7 5v3M7 10.5v.5" stroke="#b45309" stroke-width="1.2" stroke-linecap="round"/>
              <circle cx="7" cy="7" r="6" stroke="#b45309" stroke-width="1.2"/>
            </svg>
            <span>{{ group.msg.content }}</span>
          </div>
        </div>
      </div>

        <!-- 流式输出指示器 -->
        <div v-if="chatStore.isStreaming" class="streaming-bar">
          <span class="typing-dots"><i></i><i></i><i></i></span>
          <span>Agent 思考中...</span>
        </div>
      </div>

      <!-- 审批/确认 操作栏 -->
      <div v-if="pendingAction && !pendingAction.resolved" class="approval-bar">
        <div class="approval-bar-inner">
          <div class="approval-bar-header">
            <span class="approval-risk-tag" :class="'risk-' + pendingAction.riskLevel">
              {{ pendingAction.riskLevel }}
            </span>
            <span class="approval-bar-title">
              {{ pendingAction.type === 'approval' ? '需审批操作' : '需确认操作' }}
            </span>
          </div>
          <div class="approval-bar-body">
            <code class="approval-bar-tool">{{ pendingAction.toolName }}</code>
            <span class="approval-bar-detail">{{ JSON.stringify(pendingAction.params) }}</span>
          </div>
          <div class="approval-bar-actions">
            <template v-if="pendingAction.type === 'approval'">
              <button class="apv-btn apv-btn-approve" @click="handleApprove">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M3 7l3 3 5-6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                审批通过
              </button>
              <button class="apv-btn apv-btn-reject" @click="handleReject">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                拒绝
              </button>
            </template>
            <template v-else>
              <button class="apv-btn apv-btn-approve" @click="handleConfirm">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M3 7l3 3 5-6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                确认执行
              </button>
              <button class="apv-btn apv-btn-reject" @click="handleCancel">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                取消
              </button>
            </template>
          </div>
        </div>
      </div>

      <ChatInput
        :isStreaming="chatStore.isStreaming"
        @send="handleSend"
        @stop="handleStop"
      />
    </div>

    <!-- 右侧详情面板 -->
    <DetailPanel
      :visible="panelVisible"
      :title="panelTitle"
      :mode="panelMode"
      :traceEvents="traceEvents"
      :toolDetail="selectedTool"
      @close="panelVisible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import type { ToolCall, Message } from '@/stores/chat'
import {
  getSessions, createSession, deleteSession, getMessages, sendMessage,
  clearSessionMessages, deleteMessage,
} from '@/api/chat'
import { approveApproval, rejectApproval } from '@/api/approval'
import { getServers, type ServerInfo } from '@/api/servers'
import SessionList from '@/components/chat/SessionList.vue'
import UserMessage from '@/components/chat/UserMessage.vue'
import AgentMessage from '@/components/chat/AgentMessage.vue'
import ToolCallCard from '@/components/chat/ToolCallCard.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import DetailPanel from '@/components/chat/DetailPanel.vue'

const route = useRoute()
const chatStore = useChatStore()
const msgContainer = ref<HTMLElement>()
const abortController = ref<AbortController | null>(null)

// 侧边栏状态
const sidebarCollapsed = ref(false)

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

// 服务器选择器
const serverList = ref<ServerInfo[]>([])
const selectedServerId = ref('')

const selectedServerStatus = computed(() => {
  if (!selectedServerId.value) return 'online'
  if (selectedServerId.value === 'all') return 'online'
  const srv = serverList.value.find(s => s.id === selectedServerId.value)
  return srv?.status || 'unknown'
})

async function loadServerList() {
  try {
    const data = await getServers()
    serverList.value = data?.items || []
    // 默认选中标记为 isDefault=true 的服务器，没有的话选第一个
    if (serverList.value.length > 0) {
      const defaultServer = serverList.value.find(s => s.isDefault)
      if (defaultServer) {
        selectedServerId.value = defaultServer.id
      } else {
        selectedServerId.value = serverList.value[0].id
      }
    }
  } catch {}
}

function handleServerChange() {
  // 切换目标服务器
}

// 右侧面板
const panelVisible = ref(false)
const panelTitle = ref('')
const panelMode = ref<'trace' | 'tool'>('trace')
const traceEvents = ref<any[]>([])
const selectedTool = ref<ToolCall | null>(null)

// 审批/确认 状态
interface PendingAction {
  type: 'approval' | 'confirm'
  approvalId?: string
  pendingExecutionId?: string
  toolName: string
  params: Record<string, any>
  riskLevel: string
  message: string
  expiresAt?: string
  resolved: boolean
}
const pendingAction = ref<PendingAction | null>(null)

// 消息分组：将 assistant + 后续 tool_call 合并为一个 agent 组
const groupedMessages = computed(() => {
  const raw = chatStore.messages
  const groups: { id: string; type: string; msg: Message; tools: ToolCall[] }[] = []
  let i = 0
  while (i < raw.length) {
    const msg = raw[i]
    if (msg.role === 'assistant') {
      const tools: ToolCall[] = []
      let j = i + 1
      while (j < raw.length && raw[j].role === 'tool_call' && raw[j].toolCalls) {
        tools.push(...raw[j].toolCalls!)
        j++
      }
      groups.push({ id: msg.id, type: 'agent', msg, tools })
      i = j
    } else if (msg.role === 'user') {
      groups.push({ id: msg.id, type: 'user', msg, tools: [] })
      i++
    } else if (msg.role === 'system') {
      groups.push({ id: msg.id, type: 'system', msg, tools: [] })
      i++
    } else {
      // 孤立的 tool_call（没有前面的 assistant），单独展示
      const tc = (msg.toolCalls || []) as ToolCall[]
      groups.push({ id: msg.id, type: 'agent', msg: { ...msg, content: '' }, tools: tc })
      i++
    }
  }
  return groups
})

const quickActions = [
  '查看磁盘使用情况',
  '检查系统内存状态',
  '列出占用CPU最高的进程',
  '查看网络连接状态',
]

function scrollToBottom() {
  nextTick(() => {
    const el = msgContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function loadSessions() {
  try {
    const data = await getSessions()
    chatStore.setSessions(data.items || data || [])
  } catch {}
}

async function handleNewSession() {
  // 如果有正在进行的对话，先取消
  abortController.value?.abort()
  chatStore.setStreaming(false)
  try {
    const data = await createSession()
    chatStore.setCurrentSession(data.id)
    chatStore.setMessages([])
    await loadSessions()
  } catch {}
}

async function handleSelectSession(id: string) {
  // 切换会话时取消当前流式输出
  abortController.value?.abort()
  chatStore.setStreaming(false)
  chatStore.setCurrentSession(id)
  try {
    const data = await getMessages(id)
    chatStore.setMessages(data.items || [])
    scrollToBottom()
  } catch {}
}

async function handleDeleteSession(id: string) {
  try {
    await deleteSession(id)
    if (chatStore.currentSessionId === id) {
      chatStore.setCurrentSession(null as any)
      chatStore.setMessages([])
    }
    await loadSessions()
  } catch {}
}

async function handleSend(text: string, pendingData?: { approvalId?: string; pendingExecutionId?: string }) {
  if (!chatStore.currentSessionId) {
    await handleNewSession()
    return handleSend(text, pendingData)
  }
  if (chatStore.isStreaming) return

  const isResume = !!(pendingData?.approvalId || pendingData?.pendingExecutionId)

  if (!isResume) {
    // 正常消息：添加用户消息气泡
    const msgId = Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10)
    const userMsg: Message = {
      id: msgId,
      role: 'user',
      content: text,
      createdAt: new Date().toISOString(),
    }
    chatStore.addMessage(userMsg)
  }

  // 清除待处理操作
  pendingAction.value = null
  chatStore.setStreaming(true)

  const assistantMsgId = Date.now().toString(36) + '-a-' + Math.random().toString(36).slice(2, 10)
  if (!isResume) {
    const assistantMsg: Message = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      createdAt: new Date().toISOString(),
    }
    chatStore.addMessage(assistantMsg)
  }
  scrollToBottom()

  abortController.value = sendMessage(
    chatStore.currentSessionId!,
    isResume ? '(resume)' : text,
    (token: string) => {
      chatStore.appendToLastMessage(token)
      scrollToBottom()
    },
    (tool: any) => {
      const status = tool.status || 'executing'
      const tc: ToolCall = {
        id: tool.id || Date.now().toString(36),
        toolName: tool.toolName,
        params: tool.params || {},
        riskLevel: tool.riskLevel || 'L1',
        status: status as ToolCall['status'],
      }
      const toolMsg: Message = {
        id: Date.now().toString(36) + '-tc-' + Math.random().toString(36).slice(2, 10),
        role: 'tool_call',
        content: '',
        toolCalls: [tc],
        createdAt: new Date().toISOString(),
      }
      chatStore.addMessage(toolMsg)
      scrollToBottom()
    },
    (result: any) => {
      const msgs = chatStore.messages
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'tool_call' && msgs[i].toolCalls?.length) {
          const tc = msgs[i].toolCalls![0]
          tc.status = result.status || 'completed'
          tc.result = result.result
          openToolDetail(tc)
          break
        }
      }
    },
    // need_approval 事件
    (approval: any) => {
      pendingAction.value = {
        type: 'approval',
        approvalId: approval.approvalId,
        toolName: approval.toolName,
        params: approval.params || {},
        riskLevel: approval.riskLevel,
        message: approval.message,
        expiresAt: approval.expiresAt,
        resolved: false,
      }
      // 也添加系统消息
      const appMsg: Message = {
        id: Date.now().toString(36) + '-apv-' + Math.random().toString(36).slice(2, 10),
        role: 'system',
        content: approval.message,
        createdAt: new Date().toISOString(),
      }
      chatStore.addMessage(appMsg)
      chatStore.setStreaming(false)
    },
    // need_confirm 事件
    (confirm: any) => {
      pendingAction.value = {
        type: 'confirm',
        pendingExecutionId: confirm.pendingExecutionId,
        toolName: confirm.toolName,
        params: confirm.params || {},
        riskLevel: confirm.riskLevel,
        message: confirm.message,
        resolved: false,
      }
      const appMsg: Message = {
        id: Date.now().toString(36) + '-cfm-' + Math.random().toString(36).slice(2, 10),
        role: 'system',
        content: confirm.message,
        createdAt: new Date().toISOString(),
      }
      chatStore.addMessage(appMsg)
      chatStore.setStreaming(false)
    },
    // blocked 事件
    (blocked: any) => {
      const appMsg: Message = {
        id: Date.now().toString(36) + '-blk-' + Math.random().toString(36).slice(2, 10),
        role: 'system',
        content: `已阻止: ${blocked.message}`,
        createdAt: new Date().toISOString(),
      }
      chatStore.addMessage(appMsg)
    },
    (err: any) => {
      const errMsg: Message = {
        id: Date.now().toString(36) + '-err-' + Math.random().toString(36).slice(2, 10),
        role: 'system',
        content: `操作失败: ${err?.message || '未知错误'}`,
        createdAt: new Date().toISOString(),
      }
      chatStore.addMessage(errMsg)
      chatStore.setStreaming(false)
      pendingAction.value = null
    },
    (result: any) => {
      if (result.traceId) chatStore.setCurrentTraceId(result.traceId)
      chatStore.setStreaming(false)
      loadSessions()
      scrollToBottom()

      // 如果又产生了 pending action (审批恢复后再次遇到需审批的操作)，流已经停了
      if (pendingAction.value && !pendingAction.value.resolved) {
        // pending action 会通过 need_approval/need_confirm 事件设置
      }
    },
    pendingData?.approvalId,
    pendingData?.pendingExecutionId,
    selectedServerId.value,
  )
}

function handleStop() {
  abortController.value?.abort()
  chatStore.setStreaming(false)
  pendingAction.value = null
}

// 审批/确认 处理
async function handleApprove() {
  if (!pendingAction.value || pendingAction.value.type !== 'approval') return
  const approvalId = pendingAction.value.approvalId
  if (!approvalId) return

  try {
    await approveApproval(approvalId, '通过')
    pendingAction.value.resolved = true
    // 恢复执行
    handleSend('', { approvalId })
  } catch {
    const errMsg: Message = {
      id: Date.now().toString(36) + '-err-' + Math.random().toString(36).slice(2, 10),
      role: 'system',
      content: '审批操作失败，请重试',
      createdAt: new Date().toISOString(),
    }
    chatStore.addMessage(errMsg)
  }
}

async function handleReject() {
  if (!pendingAction.value || pendingAction.value.type !== 'approval') return
  const approvalId = pendingAction.value.approvalId
  if (!approvalId) return

  try {
    await rejectApproval(approvalId, '拒绝')
    pendingAction.value.resolved = true
    pendingAction.value = null
    const appMsg: Message = {
      id: Date.now().toString(36) + '-rej-' + Math.random().toString(36).slice(2, 10),
      role: 'system',
      content: '操作已被拒绝',
      createdAt: new Date().toISOString(),
    }
    chatStore.addMessage(appMsg)
  } catch {
    const errMsg: Message = {
      id: Date.now().toString(36) + '-err-' + Math.random().toString(36).slice(2, 10),
      role: 'system',
      content: '审批操作失败，请重试',
      createdAt: new Date().toISOString(),
    }
    chatStore.addMessage(errMsg)
  }
}

async function handleConfirm() {
  if (!pendingAction.value || pendingAction.value.type !== 'confirm') return
  const peId = pendingAction.value.pendingExecutionId
  if (!peId) return

  pendingAction.value.resolved = true
  // 恢复执行（确认操作不需要额外审批）
  handleSend('', { pendingExecutionId: peId })
}

function handleCancel() {
  if (!pendingAction.value) return
  pendingAction.value.resolved = true
  pendingAction.value = null
  const appMsg: Message = {
    id: Date.now().toString(36) + '-ccl-' + Math.random().toString(36).slice(2, 10),
    role: 'system',
    content: '操作已取消',
    createdAt: new Date().toISOString(),
  }
  chatStore.addMessage(appMsg)
}

async function handleClearMessages() {
  if (!chatStore.currentSessionId) return
  try {
    await clearSessionMessages(chatStore.currentSessionId)
    chatStore.setMessages([])
  } catch {}
}

async function handleDeleteMessage(msgId: string) {
  try {
    await deleteMessage(msgId)
    chatStore.setMessages(chatStore.messages.filter((m: any) => m.id !== msgId))
  } catch {}
}

function handleQuickAction(action: string) {
  handleSend(action)
}

function openTraceTimeline(traceId: string) {
  panelTitle.value = '推理链路 · ' + traceId.slice(0, 16) + '...'
  panelMode.value = 'trace'
  traceEvents.value = [
    { type: 'user', label: '用户消息', time: '', detail: '' },
    { type: 'llm', label: 'LLM 推理', time: '', detail: '模型分析意图...' },
    { type: 'security', label: '安全校验', time: '', detail: '静态规则: PASSED' },
    { type: 'tool', label: '工具执行', time: '', detail: '工具调用完成' },
    { type: 'llm', label: '生成回复', time: '', detail: '汇总结果' },
  ]
  panelVisible.value = true
}

function openToolDetail(tool: ToolCall) {
  panelTitle.value = tool.toolName
  panelMode.value = 'tool'
  selectedTool.value = tool
  panelVisible.value = true
}

onMounted(async () => {
  await loadServerList()
  await loadSessions()
  if (route.params.id) {
    chatStore.setCurrentSession(route.params.id as string)
    try {
      const data = await getMessages(route.params.id as string)
      chatStore.setMessages(data.items || [])
    } catch {}
  }
})

watch(() => route.params.id, async (id) => {
  if (id) {
    chatStore.setCurrentSession(id as string)
    try {
      const data = await getMessages(id as string)
      chatStore.setMessages(data.items || [])
    } catch {}
    scrollToBottom()
  }
})
</script>

<style lang="scss" scoped>
.chat-page {
  display: flex;
  height: 100%;
  overflow: hidden;
}

.sidebar-wrapper {
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  &.collapsed {
    width: 60px;
    min-width: 60px;
  }
}

.sidebar-collapsed-handle {
  width: 60px;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding-top: 16px;
  border-right: 1px solid #e2e8f0;
  background: #fafbfc;
}

.expand-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s ease;
  &:hover {
    border-color: #2563eb;
    color: #2563eb;
    background: #eff6ff;
    transform: translateX(2px);
  }
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #ffffff;
}

.chat-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  border-bottom: 1px solid #e2e8f0;
  background: #fafbfc;
  .topbar-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .topbar-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: #94a3b8;
  }
}

.server-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 16px;
  padding: 4px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  .server-icon { color: #94a3b8; flex-shrink: 0; }
  select {
    border: none; outline: none; background: none;
    font-size: 13px; color: #1e293b; cursor: pointer;
    font-family: inherit;
  }
  .server-status-dot {
    width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
    &.online { background: #10b981; }
    &.offline { background: #ef4444; }
    &.unknown { background: #cbd5e1; }
  }
}

.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.15s;
  &:hover {
    color: #2563eb;
    border-color: #2563eb;
    background: #eff6ff;
  }
}

.clear-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #94a3b8;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
  &:hover {
    color: #ef4444;
    border-color: #fecaca;
    background: #fef2f2;
  }
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.msg-wrapper {
  position: relative;
  &:hover .msg-delete-btn {
    opacity: 1;
  }
}

.msg-delete-btn {
  opacity: 0;
  position: absolute;
  top: 6px;
  right: 0;
  z-index: 2;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #94a3b8;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  &:hover { color: #ef4444; border-color: #fecaca; background: #fef2f2; }
}

.welcome-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding-top: 80px;
  text-align: center;
  .welcome-title {
    font-size: 24px;
    font-weight: 700;
    color: #2563eb;
    margin-top: 20px;
  }
  .welcome-desc {
    font-size: 14px;
    color: #94a3b8;
    margin-top: 10px;
    max-width: 420px;
    line-height: 1.6;
  }
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 28px;
  justify-content: center;
}

.quick-btn {
  padding: 8px 18px;
  border-radius: 20px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  color: #64748b;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
  &:hover {
    border-color: #2563eb;
    color: #2563eb;
    background: #eff6ff;
  }
}

.system-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  margin: 8px 0;
  border-radius: 8px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  font-size: 13px;
  color: #92400e;
  .sys-icon { flex-shrink: 0; }
}

.streaming-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  font-size: 13px;
  color: #94a3b8;
}

.typing-dots {
  display: flex;
  gap: 4px;
  i {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #2563eb;
    animation: typingBounce 1.2s infinite;
    &:nth-child(2) { animation-delay: 0.2s; }
    &:nth-child(3) { animation-delay: 0.4s; }
  }
}

@keyframes typingBounce {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1); }
}

.approval-bar {
  padding: 0 24px 12px;
  .approval-bar-inner {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px 16px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  }
}

.approval-bar-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.approval-risk-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
  &.risk-L2 { background: #fef9c3; color: #a16207; }
  &.risk-L3 { background: #ffedd5; color: #c2410c; }
  &.risk-L4 { background: #fee2e2; color: #b91c1c; }
  &.risk-L5 { background: #fecaca; color: #7f1d1d; }
}

.approval-bar-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.approval-bar-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 8px;
}

.approval-bar-tool {
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  color: #2563eb;
  font-weight: 600;
}

.approval-bar-detail {
  font-size: 11px;
  color: #94a3b8;
  word-break: break-all;
  font-family: 'JetBrains Mono', monospace;
}

.approval-bar-actions {
  display: flex;
  gap: 10px;
}

.apv-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid;

  &.apv-btn-approve {
    background: #2563eb;
    color: #fff;
    border-color: #2563eb;
    &:hover { background: #1d4ed8; }
  }

  &.apv-btn-reject {
    background: #fff;
    color: #ef4444;
    border-color: #fecaca;
    &:hover { background: #fef2f2; }
  }
}
</style>
