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
          <!-- 意图标签 -->
          <span v-if="chatStore.currentIntent" class="intent-tag" :class="'intent-' + chatStore.currentIntent">
            {{ intentLabel(chatStore.currentIntent) }}
          </span>
          <!-- 当前阶段指示器 -->
          <span v-if="chatStore.currentStage && chatStore.isStreaming" class="stage-indicator">
            <span class="stage-dot" :style="{ background: stageColor }"></span>
            {{ stageLabel(chatStore.currentStage) }}
          </span>
          <!-- 注入警告 -->
          <span v-if="chatStore.injectionWarning" class="injection-warning-tag">安全警告</span>
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
          <p class="welcome-desc">基于 LangGraph ReAct 架构，通过自然语言完成运维巡检、故障排查与资源管理</p>
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

          <!-- Agent消息 + 推理链 + 状态卡片 + 工具结果 -->
          <div v-else-if="group.type === 'agent'" class="msg-wrapper msg-assistant">
            <button class="msg-delete-btn" @click="handleDeleteMessage(group.id)" title="删除">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 2l6 6M8 2l-6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
            <!-- 推理链（可折叠） -->
            <ReasoningChain
              v-if="chatStore.reasoningSteps.length && group === lastAgentGroup"
              :steps="chatStore.reasoningSteps"
            />
            <!-- 状态卡片 -->
            <StateCards
              v-if="chatStore.stateCards.length && group === lastAgentGroup"
              :cards="chatStore.stateCards"
              :riskColor="chatStore.riskColor"
            />
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
              <template v-if="isAdmin">
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
              <div v-else class="awaiting-admin">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="7" stroke="#d97706" stroke-width="1.3"/>
                  <path d="M8 4.5v4M8 11.5v.5" stroke="#d97706" stroke-width="1.3" stroke-linecap="round"/>
                </svg>
                <span>此操作需管理员审批，正在自动检查审批状态...</span>
              </div>
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
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { useUserStore } from '@/stores/user'
import type { ToolCall, Message } from '@/stores/chat'
import {
  getSessions, createSession, deleteSession, getMessages, sendMessage,
  clearSessionMessages, deleteMessage,
} from '@/api/chat'
import { approveApproval, rejectApproval, getPendingApprovals } from '@/api/approval'
import { getServers, type ServerInfo } from '@/api/servers'
import SessionList from '@/components/chat/SessionList.vue'
import UserMessage from '@/components/chat/UserMessage.vue'
import AgentMessage from '@/components/chat/AgentMessage.vue'
import ToolCallCard from '@/components/chat/ToolCallCard.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import DetailPanel from '@/components/chat/DetailPanel.vue'
import ReasoningChain from '@/components/chat/ReasoningChain.vue'
import StateCards from '@/components/chat/StateCards.vue'

const route = useRoute()
const chatStore = useChatStore()
const userStore = useUserStore()
const msgContainer = ref<HTMLElement>()

const isAdmin = computed(() => userStore.userInfo?.role === 'admin')
const abortController = ref<AbortController | null>(null)

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
    if (serverList.value.length > 0) {
      const defaultServer = serverList.value.find(s => s.isDefault)
      selectedServerId.value = defaultServer ? defaultServer.id : serverList.value[0].id
    }
  } catch {}
}

function handleServerChange() {}

// 阶段指示器
const stageLabels: Record<string, string> = {
  intent_filter: '意图分析', parallel_process: '知识检索', fusion: '上下文融合',
  dialog_manage: '对话管理', reasoning: '推理决策', safety_check: '安全校验',
  tool_execution: '工具执行', response_assembly: '响应组装',
}

function stageLabel(stage: string): string {
  return stageLabels[stage] || stage
}

const stageColor = computed(() => {
  const stage = chatStore.currentStage
  if (stage === 'safety_check') return '#f59e0b'
  if (stage === 'tool_execution') return '#3b82f6'
  if (stage === 'reasoning') return '#8b5cf6'
  if (stage === 'response_assembly') return '#10b981'
  return '#2563eb'
})

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
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null)

function startApprovalPolling(approvalId: string) {
  stopApprovalPolling()
  pollTimer.value = setInterval(async () => {
    try {
      const data = await getPendingApprovals()
      const items = data?.items || []
      const stillPending = items.find((item: any) => item.id === approvalId)
      if (!stillPending) {
        // 审批已处理（通过或拒绝），检查状态并恢复
        stopApprovalPolling()
        if (!pendingAction.value || pendingAction.value.resolved) return
        pendingAction.value.resolved = true
        handleSend('', { approvalId })
      }
    } catch {}
  }, 3000)
}

function stopApprovalPolling() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

// 消息分组
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
      const tc = (msg.toolCalls || []) as ToolCall[]
      groups.push({ id: msg.id, type: 'agent', msg: { ...msg, content: '' }, tools: tc })
      i++
    }
  }
  return groups
})

// 最后一个 Agent 消息组（用于显示推理链和状态卡片）
const lastAgentGroup = computed(() => {
  const groups = groupedMessages.value
  for (let i = groups.length - 1; i >= 0; i--) {
    if (groups[i].type === 'agent') return groups[i]
  }
  return null
})

const quickActions = [
  '查看磁盘使用情况',
  '检查系统内存状态',
  '列出占用CPU最高的进程',
  '查看网络连接状态',
]

const intentLabels: Record<string, string> = {
  general_qa: '普通问答', knowledge_qa: '知识查询',
  ops_query: '运维查询', fault_analysis: '故障分析',
  high_risk: '高风险操作', prompt_injection: '注入拦截',
}

function intentLabel(intent: string): string {
  return intentLabels[intent] || intent
}

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
  abortController.value?.abort()
  chatStore.setStreaming(false)
  try {
    const data = await createSession()
    chatStore.setCurrentSession(data.id)
    chatStore.setMessages([])
    chatStore.resetAgentState()
    await loadSessions()
  } catch {}
}

async function handleSelectSession(id: string) {
  abortController.value?.abort()
  chatStore.setStreaming(false)
  chatStore.setCurrentSession(id)
  chatStore.resetAgentState()
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
    const msgId = Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10)
    const userMsg: Message = {
      id: msgId, role: 'user', content: text, createdAt: new Date().toISOString(),
    }
    chatStore.addMessage(userMsg)
    chatStore.resetAgentState()
  }

  pendingAction.value = null
  chatStore.setStreaming(true)

  const assistantMsgId = Date.now().toString(36) + '-a-' + Math.random().toString(36).slice(2, 10)
  if (!isResume) {
    const assistantMsg: Message = {
      id: assistantMsgId, role: 'assistant', content: '', createdAt: new Date().toISOString(),
    }
    chatStore.addMessage(assistantMsg)
  }
  scrollToBottom()

  abortController.value = sendMessage(
    chatStore.currentSessionId!,
    isResume ? '(resume)' : text,
    {
      onToken: (token: string) => {
        chatStore.appendToLastMessage(token)
        scrollToBottom()
      },
      onToolCall: (tool: any) => {
        const tc: ToolCall = {
          id: tool.id || Date.now().toString(36),
          toolName: tool.toolName,
          params: tool.params || {},
          riskLevel: tool.riskLevel || 'L1',
          status: (tool.status || 'executing') as ToolCall['status'],
        }
        chatStore.addMessage({
          id: Date.now().toString(36) + '-tc-' + Math.random().toString(36).slice(2, 10),
          role: 'tool_call', content: '', toolCalls: [tc],
          createdAt: new Date().toISOString(),
        })
        scrollToBottom()
      },
      onToolResult: (result: any) => {
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
      onApprovalRequired: (approval: any) => {
        pendingAction.value = {
          type: 'approval', approvalId: approval.approvalId,
          toolName: approval.toolName, params: approval.params || {},
          riskLevel: approval.riskLevel, message: approval.message,
          expiresAt: approval.expiresAt, resolved: false,
        }
        chatStore.addMessage({
          id: Date.now().toString(36) + '-apv-' + Math.random().toString(36).slice(2, 10),
          role: 'system', content: approval.message, createdAt: new Date().toISOString(),
        })
        chatStore.setStreaming(false)
        // 非管理员自动轮询审批状态
        if (!isAdmin.value) {
          startApprovalPolling(approval.approvalId)
        }
      },
      onConfirmRequired: (confirm: any) => {
        pendingAction.value = {
          type: 'confirm', pendingExecutionId: confirm.pendingExecutionId,
          toolName: confirm.toolName, params: confirm.params || {},
          riskLevel: confirm.riskLevel, message: confirm.message, resolved: false,
        }
        chatStore.addMessage({
          id: Date.now().toString(36) + '-cfm-' + Math.random().toString(36).slice(2, 10),
          role: 'system', content: confirm.message, createdAt: new Date().toISOString(),
        })
        chatStore.setStreaming(false)
      },
      onBlocked: (blocked: any) => {
        chatStore.addMessage({
          id: Date.now().toString(36) + '-blk-' + Math.random().toString(36).slice(2, 10),
          role: 'system', content: `已阻止: ${blocked.message}`, createdAt: new Date().toISOString(),
        })
      },
      onIntent: (intent: any) => {
        chatStore.setCurrentIntent(intent.intent)
      },
      onPromptInjection: (injection: any) => {
        chatStore.setInjectionWarning(injection.message)
        if (injection.blocked) {
          chatStore.addMessage({
            id: Date.now().toString(36) + '-inj-' + Math.random().toString(36).slice(2, 10),
            role: 'system', content: `安全拦截: ${injection.message}`, createdAt: new Date().toISOString(),
          })
          chatStore.setStreaming(false)
        }
      },
      onRiskNotice: (notice: any) => {
        chatStore.addMessage({
          id: Date.now().toString(36) + '-risk-' + Math.random().toString(36).slice(2, 10),
          role: 'system', content: notice.message, createdAt: new Date().toISOString(),
        })
      },
      onPermissionNotice: (permNotice: any) => {
        console.warn('Permission restriction:', permNotice)
      },
      // LangGraph 新事件
      onStageUpdate: (stage: any) => {
        if (stage.state?.current_stage) {
          chatStore.setCurrentStage(stage.state.current_stage)
        }
      },
      onReasoningStep: (step: any) => {
        if (step.steps) {
          chatStore.setReasoningSteps(step.steps)
        }
      },
      onReasoningChain: (chain: any) => {
        if (chain.steps) {
          chatStore.setReasoningSteps(chain.steps)
        }
      },
      onStateCards: (cards: any) => {
        if (cards.cards) {
          chatStore.setStateCards(cards.cards)
        }
        if (cards.risk_color) {
          chatStore.setRiskColor(cards.risk_color)
        }
      },
      onError: (err: any) => {
        chatStore.addMessage({
          id: Date.now().toString(36) + '-err-' + Math.random().toString(36).slice(2, 10),
          role: 'system', content: `操作失败: ${err?.message || '未知错误'}`,
          createdAt: new Date().toISOString(),
        })
        chatStore.setStreaming(false)
        stopApprovalPolling()
        pendingAction.value = null
      },
      onDone: (result: any) => {
        if (result.traceId) chatStore.setCurrentTraceId(result.traceId)
        chatStore.setStreaming(false)
        stopApprovalPolling()
        pendingAction.value = null
        loadSessions()
        scrollToBottom()
      },
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
  stopApprovalPolling()
}

async function handleApprove() {
  if (!pendingAction.value || pendingAction.value.type !== 'approval') return
  const approvalId = pendingAction.value.approvalId
  if (!approvalId) return
  try {
    await approveApproval(approvalId, '通过')
    stopApprovalPolling()
    pendingAction.value.resolved = true
    handleSend('', { approvalId })
  } catch (e: any) {
    chatStore.addMessage({
      id: Date.now().toString(36) + '-err-' + Math.random().toString(36).slice(2, 10),
      role: 'system',
      content: '审批操作失败: ' + (e?.response?.data?.detail || e?.message || '请重试'),
      createdAt: new Date().toISOString(),
    })
  }
}

async function handleReject() {
  if (!pendingAction.value || pendingAction.value.type !== 'approval') return
  const approvalId = pendingAction.value.approvalId
  if (!approvalId) return
  try {
    await rejectApproval(approvalId, '拒绝')
    stopApprovalPolling()
    pendingAction.value.resolved = true
    pendingAction.value = null
    chatStore.addMessage({
      id: Date.now().toString(36) + '-rej-' + Math.random().toString(36).slice(2, 10),
      role: 'system', content: '操作已被拒绝', createdAt: new Date().toISOString(),
    })
  } catch (e: any) {
    chatStore.addMessage({
      id: Date.now().toString(36) + '-err-' + Math.random().toString(36).slice(2, 10),
      role: 'system', content: '审批操作失败: ' + (e?.response?.data?.detail || e?.message || '请重试'),
      createdAt: new Date().toISOString(),
    })
  }
}

async function handleConfirm() {
  if (!pendingAction.value || pendingAction.value.type !== 'confirm') return
  const peId = pendingAction.value.pendingExecutionId
  if (!peId) return
  pendingAction.value.resolved = true
  handleSend('', { pendingExecutionId: peId })
}

function handleCancel() {
  if (!pendingAction.value) return
  stopApprovalPolling()
  pendingAction.value.resolved = true
  pendingAction.value = null
  chatStore.addMessage({
    id: Date.now().toString(36) + '-ccl-' + Math.random().toString(36).slice(2, 10),
    role: 'system', content: '操作已取消', createdAt: new Date().toISOString(),
  })
}

async function handleClearMessages() {
  if (!chatStore.currentSessionId) return
  try {
    await clearSessionMessages(chatStore.currentSessionId)
    chatStore.setMessages([])
    chatStore.resetAgentState()
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
  // 用真实的推理步骤构建时间线
  const events: any[] = []
  if (chatStore.currentIntent) {
    events.push({ type: 'user', label: '意图识别', time: '', detail: chatStore.currentIntent })
  }
  for (const step of chatStore.reasoningSteps) {
    events.push({
      type: 'llm', label: `推理步骤 ${step.step}`,
      time: '', detail: step.thought || step.action || '',
    })
  }
  if (chatStore.currentStage) {
    events.push({ type: 'security', label: '安全校验', time: '', detail: chatStore.currentStage })
  }
  traceEvents.value = events.length ? events : [
    { type: 'user', label: '用户消息', time: '', detail: '' },
    { type: 'llm', label: 'LLM 推理', time: '', detail: '模型分析意图...' },
    { type: 'security', label: '安全校验', time: '', detail: '静态规则: PASSED' },
  ]
  panelVisible.value = true
}

function openToolDetail(tool: ToolCall) {
  panelTitle.value = tool.toolName
  panelMode.value = 'tool'
  selectedTool.value = tool
  panelVisible.value = true
}

onUnmounted(() => {
  stopApprovalPolling()
})

async function restorePendingApproval(sessionId: string) {
  try {
    const data = await getPendingApprovals()
    const items = data?.items || []
    const match = items.find((item: any) => item.sessionId === sessionId)
    if (match) {
      pendingAction.value = {
        type: 'approval',
        approvalId: match.id,
        toolName: match.toolName,
        params: match.toolParams || {},
        riskLevel: match.riskLevel,
        message: match.detail || '此操作需要管理员审批',
        expiresAt: match.expiresAt,
        resolved: false,
      }
      if (!isAdmin.value) {
        startApprovalPolling(match.id)
      }
    }
  } catch {}
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
    await restorePendingApproval(route.params.id as string)
  }
})

watch(() => route.params.id, async (id) => {
  if (id) {
    chatStore.setCurrentSession(id as string)
    try {
      const data = await getMessages(id as string)
      chatStore.setMessages(data.items || [])
    } catch {}
    await restorePendingApproval(id as string)
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

.stage-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 12px;
  background: #f1f5f9;
  font-size: 12px;
  color: #475569;
  margin-left: 8px;

  .stage-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    animation: pulse-dot 1.5s infinite;
  }
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
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
  &:hover .msg-delete-btn { opacity: 1; }
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

.awaiting-admin {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  font-size: 13px;
  color: #92400e;
  svg { flex-shrink: 0; }
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

// 意图标签
.intent-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  margin-left: 12px;

  &.intent-general_qa { background: #f1f5f9; color: #64748b; }
  &.intent-knowledge_qa { background: #eff6ff; color: #2563eb; }
  &.intent-ops_query { background: #ecfdf5; color: #059669; }
  &.intent-fault_analysis { background: #fffbeb; color: #b45309; }
  &.intent-high_risk { background: #fef2f2; color: #dc2626; }
  &.intent-prompt_injection { background: #fef2f2; color: #991b1b; }
}

.injection-warning-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
  margin-left: 8px;
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
  animation: pulse-warning 2s infinite;
}

@keyframes pulse-warning {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
</style>
