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
            {{ chatStore.intentLabel || intentLabel(chatStore.currentIntent) }}
            <template v-if="chatStore.intentConfidence"> {{ Math.round(chatStore.intentConfidence * 100) }}%</template>
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
        <div class="topbar-actions">
          <button
            class="feedback-btn"
            :disabled="!chatStore.currentSessionId"
            title="对本会话 Agent 对话提交会话反馈"
            @click="showSessionFeedback = true"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 1.5l1.2 2.4 2.7.4-2 1.9.5 2.7L7 7.6 4.6 8.9l.5-2.7-2-1.9 2.7-.4L7 1.5z" stroke="currentColor" stroke-width="1.1" stroke-linejoin="round"/>
              <path d="M2 11.5h10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
            </svg>
            会话反馈
          </button>
          <button class="clear-btn" @click="handleClearMessages" title="清空当前对话">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 4h10M5 4V3a1 1 0 011-1h2a1 1 0 011 1v1M11 4v7a1 1 0 01-1 1H4a1 1 0 01-1-1V4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
            </svg>
            清空对话
          </button>
        </div>
      </div>

      <div class="chat-body" :class="{ 'chat-body--welcome': !chatStore.messages.length }">
        <ShieldRippleBackground v-if="!chatStore.messages.length" />
        <div class="chat-messages" :class="{ 'chat-messages--welcome': !chatStore.messages.length }" ref="msgContainer">
        <div class="welcome-area" v-if="!chatStore.messages.length">
          <h1 class="welcome-title">KylinOps 智能运维 Agent</h1>
          <p class="welcome-desc">基于 LangGraph ReAct 架构，通过自然语言完成运维巡检、故障排查与资源管理</p>
          <div class="quick-actions">
            <button v-for="qa in quickActions" :key="qa" class="quick-btn" @click="handleQuickAction(qa)">
              {{ qa }}
            </button>
          </div>
          <KnowledgeDanmakuStream @send="handleQuickAction" />
        </div>

        <div v-for="group in groupedMessages" :key="group.id">
          <!-- 用户消息 -->
          <div
            v-if="group.type === 'user'"
            class="msg-wrapper msg-user"
            :data-trace-id="group.msg.traceId || undefined"
            :class="{ 'trace-highlight': highlightTraceId && group.msg.traceId === highlightTraceId }"
          >
            <button class="msg-delete-btn" @click="handleDeleteMessage(group.id)" title="删除">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 2l6 6M8 2l-6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
            <UserMessage :content="group.msg.content" :createdAt="group.msg.createdAt" />
          </div>

          <!-- Agent消息 + 推理链 + 状态卡片 + 工具结果 -->
          <div
            v-else-if="group.type === 'agent'"
            class="msg-wrapper msg-assistant"
            :data-trace-id="group.msg.traceId || undefined"
            :class="{ 'trace-highlight': highlightTraceId && group.msg.traceId === highlightTraceId }"
          >
            <button class="msg-delete-btn" @click="handleDeleteMessage(group.id)" title="删除">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 2l6 6M8 2l-6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
            <!-- Agent 头部（图标 + 元信息 + 可选开场白） -->
            <AgentMessage
              v-if="showAgentHeader(group)"
              :content="agentHeaderContent(group)"
              :traceId="agentMainContent(group) ? undefined : group.msg.traceId"
              :hideTrace="!!agentMainContent(group)"
              :createdAt="group.msg.createdAt"
              @viewTrace="openTraceTimeline"
            />
            <!-- 知识问答：流式时思考栏内联 sticky 轻遮罩，结束后自然贴合正文上方（图2） -->
            <div
              v-if="useKbComposeLayout(group)"
              class="kb-answer-compose"
              :class="{ 'kb-answer-compose--streaming': isKbStreamMask(group) }"
            >
              <div
                v-if="showThinkingForGroup(group)"
                class="agent-aligned-blocks thinking-stack"
              >
                <ExploringPanel
                  v-if="chatStore.exploringSteps.length"
                  :steps="chatStore.exploringSteps"
                  :content-streaming="isKbContentStreaming(group)"
                />
                <ReasoningChain v-if="chatStore.reasoningSteps.length" :steps="chatStore.reasoningSteps" />
              </div>
              <div v-if="agentMainContent(group)" class="kb-answer-body">
                <AgentMessage
                  :content="agentMainContent(group)"
                  :traceId="group.msg.traceId"
                  :createdAt="group.msg.createdAt"
                  continuation
                />
              </div>
            </div>
            <template v-else>
              <div
                v-if="showThinkingForGroup(group)"
                class="agent-aligned-blocks thinking-stack"
              >
                <ExploringPanel
                  v-if="chatStore.exploringSteps.length"
                  :steps="chatStore.exploringSteps"
                  :content-streaming="isKbContentStreaming(group)"
                />
                <ReasoningChain v-if="chatStore.reasoningSteps.length" :steps="chatStore.reasoningSteps" />
              </div>
              <AgentMessage
                v-if="agentMainContent(group)"
                :content="agentMainContent(group)"
                :traceId="group.msg.traceId"
                :createdAt="group.msg.createdAt"
                continuation
              />
            </template>
            <div
              v-if="planUiForGroup(group)"
              class="agent-aligned-blocks plan-flow-stack"
            >
              <RiskNoticeBanner
                v-if="planUiForGroup(group)?.riskMessage"
                :message="planUiForGroup(group)!.riskMessage!"
              />
              <DiagnosticPlanCard
                v-if="planUiForGroup(group)?.plan"
                :plan="planUiForGroup(group)!.plan"
                :mode="planUiForGroup(group)!.mode"
                :stream-reveal="planUiForGroup(group)!.stream"
                :generating="planUiForGroup(group)!.generating"
                :confirmable="planUiForGroup(group)!.confirmable"
                :trace-id="planUiForGroup(group)!.traceId"
                :user-question="planUiForGroup(group)!.userQuestion"
                @confirm="handlePlanConfirm"
                @cancel="handlePlanCancel"
              />
            </div>
            <div
              v-if="hasAgentBlocks(group)"
              class="agent-aligned-blocks"
            >
              <StateCards
                v-if="chatStore.stateCards.length && group === lastAgentGroup"
                :cards="chatStore.stateCards"
                :riskColor="chatStore.riskColor"
              />
              <template v-for="tc in group.tools" :key="tc.id">
                <CommandConfirmCard
                  v-if="needsInlineApprovedRun(tc)"
                  mode="post-approval"
                  :toolName="pendingAction!.toolName"
                  :params="pendingAction!.params"
                  :riskLevel="pendingAction!.riskLevel"
                  :message="(tc as any).planStepAction ? `步骤 ${(tc as any).planStepOrder} · ${(tc as any).planStepAction}` : pendingAction!.message"
                  :commandPreview="pendingAction!.commandPreview"
                  @skip="handleApprovedCancel"
                  @cancel="handleApprovedCancel"
                  @run="handleApprovedRun"
                />
                <CommandConfirmCard
                  v-else-if="needsInlineConfirm(tc)"
                  mode="l2"
                  :toolName="tc.toolName"
                  :params="tc.params || {}"
                  :riskLevel="tc.riskLevel"
                  :message="(tc as any).planStepAction ? `步骤 ${(tc as any).planStepOrder} · ${(tc as any).planStepAction}` : '请在确认后执行本步骤命令。'"
                  :commandPreview="buildCommandPreviewFromTool(tc as PendingConfirmTool)"
                  @skip="() => handleSkipForTool(tc)"
                  @cancel="() => handleCancelForTool(tc)"
                  @run="() => handleConfirmForTool(tc)"
                />
                <div v-else-if="needsInlineApprovalNotice(tc)" class="step-approval-notice">
                  <span class="notice-badge">L3 待审批</span>
                  <span>步骤 {{ (tc as any).planStepOrder }} · {{ (tc as any).planStepAction || tc.toolName }} 需管理员审批，批准后将在此步骤上方出现执行确认。</span>
                </div>
                <ToolCallCard
                  :tool="tc"
                  :rollback-enabled="!!rollbackByTool[tc.id]?.reversible"
                  :rollback-hint="rollbackByTool[tc.id]?.rollbackHint"
                  :rolled-back="!!rollbackByTool[tc.id]?.rolledBack"
                  :rollback-busy="rollbackBusyId === tc.id"
                  @viewDetail="openToolDetail"
                  @rollback="handleToolRollback"
                />
              </template>
              <PlanStepProgressCard
                v-if="group === lastAgentGroup && planExecutionActive && planProgressState && !hasInlinePlanConfirm"
                :progress="planProgressState"
                :stuck="isPlanStuck()"
                :continuing="continuePlanBusy"
                @continue="tryContinueStuckPlan"
              />
              <ResponseSummary
                v-if="showPlanConclusion(group)"
                :content="group.conclusion"
                :trace-id="group.msg.traceId"
                :intent="chatStore.currentIntent"
                :user-question="userQuestionForGroup(group)"
                :tools="group.tools"
                :streaming="group === lastAgentGroup && chatStore.responsePhase === 'summary'"
                :show-full-rollback="group === lastAgentGroup && !!group.conclusion && hasFullRollback"
                :rollback-busy="fullRollbackBusy"
                @full-rollback="handleRollback('full')"
              />
            </div>
          </div>

          <!-- 系统消息（与工具卡左对齐） -->
          <div v-else-if="group.type === 'system'" class="msg-wrapper msg-system agent-aligned-blocks">
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
        <div v-if="showStreamingBar" class="streaming-bar">
          <span class="typing-dots"><i></i><i></i><i></i></span>
          <span>{{ streamingStatusText }}</span>
        </div>

        <!-- 待确认命令 / 审批（与工具卡左对齐） -->
        <div v-if="showActionDock" class="agent-aligned-blocks action-dock">
          <CommandConfirmCard
            v-if="pendingAction && !pendingAction.resolved && pendingAction.type === 'confirm'"
            mode="l2"
            :toolName="pendingAction.toolName"
            :params="pendingAction.params"
            :riskLevel="pendingAction.riskLevel"
            :message="pendingAction.message"
            :commandPreview="pendingAction.commandPreview"
            @skip="handleSkip"
            @cancel="handleCancel"
            @run="handleConfirm"
          />
          <CommandConfirmCard
            v-if="pendingAction && !pendingAction.resolved && pendingAction.type === 'approved_run'"
            mode="post-approval"
            :toolName="pendingAction.toolName"
            :params="pendingAction.params"
            :riskLevel="pendingAction.riskLevel"
            :message="pendingAction.message"
            :commandPreview="pendingAction.commandPreview"
            @skip="handleApprovedCancel"
            @cancel="handleApprovedCancel"
            @run="handleApprovedRun"
          />
          <div
            v-if="pendingAction && !pendingAction.resolved && pendingAction.type === 'approval'"
            class="approval-bar-inner"
          >
            <div class="approval-bar-header">
              <span class="approval-risk-tag" :class="'risk-' + pendingAction.riskLevel">
                {{ pendingAction.riskLevel }}
              </span>
              <span class="approval-bar-title">需管理员审批（L3 及以上）</span>
            </div>
            <div class="approval-bar-body">
              <code class="approval-bar-tool">{{ pendingAction.toolName }}</code>
              <span class="approval-bar-detail">{{ JSON.stringify(pendingAction.params) }}</span>
              <p class="approval-hint">{{ pendingAction.message }}</p>
            </div>
            <div class="approval-bar-actions">
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
            </div>
          </div>
        </div>

        </div>
      </div>

      <TraceFeedbackBar
        v-if="showTraceFeedback && activeFeedbackTraceId && chatStore.currentSessionId"
        :visible="showTraceFeedback"
        :trace-id="activeFeedbackTraceId"
        :session-id="chatStore.currentSessionId!"
        @close="closeFeedbackBar"
        @submitted="onFeedbackSubmitted"
      />

      <ChatInput
        :isStreaming="chatStore.isStreaming"
        @send="handleSend"
        @stop="handleStop"
      />

      <SessionFeedbackDialog
        v-model="showSessionFeedback"
        :session-id="chatStore.currentSessionId || ''"
        :session-title="currentSessionTitle"
        :trace-id="sessionFeedbackTraceId || undefined"
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { useChatStore } from '@/stores/chat'
import { useUserStore } from '@/stores/user'
import { useApprovalStore } from '@/stores/approval'
import type { ToolCall, Message } from '@/stores/chat'
import type { RollbackToolStatus } from '@/api/chat'
import {
  getSessions, createSession, deleteSession, getMessages, sendMessage,
  clearSessionMessages, deleteMessage, getAwaitingRun, getPendingPlan, cancelAwaitingRun,
  rollbackSession, getRollbackStatus,
  finalizeApprovalRejection, continuePlanExecution,
} from '@/api/chat'
import { approveApproval, rejectApproval, getPendingApprovals, getApprovalById, getApprovalHistory } from '@/api/approval'
import { getServers, type ServerInfo } from '@/api/servers'
import SessionList from '@/components/chat/SessionList.vue'
import ShieldRippleBackground from '@/components/chat/ShieldRippleBackground.vue'
import KnowledgeDanmakuStream from '@/components/chat/KnowledgeDanmakuStream.vue'
import UserMessage from '@/components/chat/UserMessage.vue'
import AgentMessage from '@/components/chat/AgentMessage.vue'
import ToolCallCard from '@/components/chat/ToolCallCard.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import DetailPanel from '@/components/chat/DetailPanel.vue'
import ReasoningChain from '@/components/chat/ReasoningChain.vue'
import ExploringPanel from '@/components/chat/ExploringPanel.vue'
import CommandConfirmCard from '@/components/chat/CommandConfirmCard.vue'
import DiagnosticPlanCard from '@/components/chat/DiagnosticPlanCard.vue'
import PlanStepProgressCard, { type PlanProgressPayload } from '@/components/chat/PlanStepProgressCard.vue'
import RiskNoticeBanner from '@/components/chat/RiskNoticeBanner.vue'
import TraceFeedbackBar from '@/components/chat/TraceFeedbackBar.vue'
import SessionFeedbackDialog from '@/components/chat/SessionFeedbackDialog.vue'
import { validateChatInput } from '@/utils/chatValidate'
import {
  isTraceFeedbackClosed,
  markTraceFeedbackClosed,
  setPendingFeedbackTrace,
  clearPendingFeedbackTrace,
  getPendingFeedbackTrace,
} from '@/utils/traceFeedbackStorage'
import { getTraceOutcomeStatus } from '@/api/traceOutcome'
import ResponseSummary from '@/components/chat/ResponseSummary.vue'
import StateCards from '@/components/chat/StateCards.vue'
import { splitAgentContent, TOOLS_CONTENT_MARKER, hasKnowledgeOpener } from '@/utils/splitAgentMessageContent'
import { mergeConclusionPreservingReport, isLightweightConclusion, extractLastConclusionBlock } from '@/utils/conclusionContent'
import { toolDisplayName } from '@/utils/toolDisplay'

const route = useRoute()
const chatStore = useChatStore()
const userStore = useUserStore()
const approvalStore = useApprovalStore()
const msgContainer = ref<HTMLElement>()
const highlightTraceId = ref<string | null>(null)
let highlightTraceTimer: ReturnType<typeof setTimeout> | null = null

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
  type: 'approval' | 'confirm' | 'approved_run'
  approvalId?: string
  pendingExecutionId?: string
  toolName: string
  params: Record<string, any>
  riskLevel: string
  message: string
  commandPreview?: string
  expiresAt?: string
  resolved: boolean
}
const pendingAction = ref<PendingAction | null>(null)
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null)
const awaitingRunTimer = ref<ReturnType<typeof setInterval> | null>(null)
const waitingApprovalId = ref<string | null>(null)
const planFallbackTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const planPollTimer = ref<ReturnType<typeof setInterval> | null>(null)
const diagnosticPlan = ref<{
  planId: string
  plan: Record<string, any>
  resolved: boolean
  traceId?: string
  generating?: boolean
} | null>(null)
const planRiskMessage = ref<string | null>(null)
/** 方案确认后挂在原 Agent 消息组下展示（警告框 + 只读方案） */
const confirmedPlanArchive = ref<{
  anchorGroupId: string
  planId: string
  plan: Record<string, any>
  riskMessage: string | null
} | null>(null)
/** 方案执行中的轻量进度（非最终结论） */
const planProgress = ref<PlanProgressPayload | null>(null)
const continuePlanBusy = ref(false)
const showTraceFeedback = ref(false)
const showSessionFeedback = ref(false)
/** 当前会话待反馈的 trace（与会话绑定，切换会话时不串台） */
const activeFeedbackTraceId = ref<string | null>(null)

const currentSessionTitle = computed(() => {
  const sid = chatStore.currentSessionId
  if (!sid) return ''
  const s = chatStore.sessions.find(x => x.id === sid)
  if (s?.title) return s.title
  const firstUser = chatStore.messages.find(m => m.role === 'user')
  return firstUser?.content?.slice(0, 40) || sid.slice(0, 12)
})

const sessionFeedbackTraceId = computed(() => {
  for (let i = chatStore.messages.length - 1; i >= 0; i--) {
    const tid = chatStore.messages[i].traceId
    if (tid) return tid
  }
  return chatStore.currentTraceId || null
})

function getLastTraceWithTools(messages: Message[]): string | null {
  if (!messages.some(m => m.role === 'tool_call')) return null
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].traceId) return messages[i].traceId!
  }
  return null
}

async function syncFeedbackBarForSession(sessionId: string | null) {
  activeFeedbackTraceId.value = null
  showTraceFeedback.value = false
  if (!sessionId) return
  ensurePlanArchiveFromTools()
  if (isPlanIncomplete()) return

  let traceId = getPendingFeedbackTrace(sessionId) || getLastTraceWithTools(chatStore.messages)
  if (!traceId) return
  if (isTraceFeedbackClosed(sessionId, traceId)) {
    clearPendingFeedbackTrace(sessionId)
    return
  }

  try {
    const status = await getTraceOutcomeStatus(sessionId, traceId)
    if (status?.submitted) {
      markTraceFeedbackClosed(sessionId, traceId, 'submitted')
      clearPendingFeedbackTrace(sessionId)
      return
    }
  } catch { /* ignore */ }

  activeFeedbackTraceId.value = traceId
  chatStore.setCurrentTraceId(traceId)
  showTraceFeedback.value = true
}

function closeFeedbackBar() {
  const sid = chatStore.currentSessionId
  const tid = activeFeedbackTraceId.value
  if (sid && tid) {
    markTraceFeedbackClosed(sid, tid, 'dismissed')
    clearPendingFeedbackTrace(sid)
  }
  showTraceFeedback.value = false
  activeFeedbackTraceId.value = null
}

function onFeedbackSubmitted() {
  const sid = chatStore.currentSessionId
  const tid = activeFeedbackTraceId.value
  if (sid && tid) {
    markTraceFeedbackClosed(sid, tid, 'submitted')
    clearPendingFeedbackTrace(sid)
  }
  showTraceFeedback.value = false
  activeFeedbackTraceId.value = null
}

const rollbackByTool = ref<Record<string, RollbackToolStatus>>({})
const hasFullRollback = ref(false)
const rollbackBusyId = ref<string | null>(null)
const fullRollbackBusy = ref(false)

async function loadRollbackStatus() {
  const sid = chatStore.currentSessionId
  if (!sid) {
    rollbackByTool.value = {}
    hasFullRollback.value = false
    return
  }
  try {
    const data = await getRollbackStatus(sid)
    rollbackByTool.value = data.byToolCallId || {}
    hasFullRollback.value = !!data.hasFullRollback
  } catch {
    rollbackByTool.value = {}
    hasFullRollback.value = false
  }
}

function computePlanProgressFromTools(): PlanProgressPayload | null {
  const arch = confirmedPlanArchive.value
  if (!arch?.plan?.steps?.length) return null
  const steps = arch.plan.steps as { order: number; action: string }[]
  const merged = getAllToolCallsMerged()
  const doneOrders = new Set<number>()
  for (const step of steps) {
    if (isStepOrderDone(merged, step.order)) doneOrders.add(step.order)
  }
  const pending = merged.filter(t => {
    if (t.status !== 'pending_confirm' && t.status !== 'pending_approval') return false
    const order = (t as PendingConfirmTool).planStepOrder
    if (t.status === 'pending_approval') return true
    return order == null || !doneOrders.has(order)
  })
  const current = pending[0] as PendingConfirmTool | undefined
  const total = steps.length
  const briefParts = [`方案进度 ${doneOrders.size}/${total}`]
  if (current) {
    const action = current.planStepAction || previewCmdFromTool(current)
    if (current.status === 'pending_approval') {
      briefParts.push(`步骤 ${current.planStepOrder}「${action}」待管理员审批`)
    } else {
      briefParts.push(`步骤 ${current.planStepOrder}「${action}」待您确认执行`)
    }
  } else if (doneOrders.size >= total) {
    const failedOrders = steps.filter(s => {
      const matches = merged.filter(t => (t as PendingConfirmTool).planStepOrder === s.order)
      return resolvePlanStepStatus(matches) === 'failed'
    })
    briefParts.push(
      failedOrders.length
        ? `方案已执行完毕，${failedOrders.length} 步未成功`
        : '方案已全部执行完毕',
    )
  }
  return {
    phenomenon: arch.plan.phenomenon || findLastUserQuestion().slice(0, 80),
    totalSteps: total,
    completedSteps: doneOrders.size,
    currentStepOrder: current?.planStepOrder ?? null,
    currentStepAction: current?.planStepAction ?? null,
    currentStatus: current?.status || (doneOrders.size >= total ? 'completed' : 'executing'),
    brief: briefParts.join('，'),
    steps: steps.map(s => {
      const matches = merged.filter(t => (t as PendingConfirmTool).planStepOrder === s.order)
      return { order: s.order, action: s.action, status: resolvePlanStepStatus(matches) }
    }),
  }
}

/** 以工具卡合并结果为准；SSE plan_progress 仅作归档未就绪时的兜底 */
const planProgressState = computed(() => computePlanProgressFromTools() || planProgress.value)

function countTerminalPlanSteps(merged: PendingConfirmTool[], total: number): number {
  const terminal = new Set(['completed', 'failed', 'blocked', 'rejected'])
  let count = 0
  for (let o = 1; o <= total; o++) {
    const matches = merged.filter(t => t.planStepOrder === o)
    if (!matches.length) continue
    const best = matches.reduce((a, b) =>
      toolStatusPriority(b.status) >= toolStatusPriority(a.status) ? b : a,
    )
    if (terminal.has(best.status)) count++
  }
  return count
}

const planAllCompleted = computed(() => {
  if (hasEffectivePendingAction()) return false
  const p = planProgressState.value
  if (!p?.totalSteps) return false
  if ((p.completedSteps ?? 0) >= p.totalSteps) return true
  if (p.steps?.length) {
    const terminal = new Set(['completed', 'failed', 'blocked', 'rejected', 'skipped'])
    return p.steps.every(s => terminal.has(s.status))
  }
  return p.currentStatus === 'completed'
})

const planExecutionActive = computed(() => {
  if (planAllCompleted.value) return false
  if (confirmedPlanArchive.value) return true
  const merged = getAllToolCallsMerged()
  return merged.some(t => !!(t as PendingConfirmTool).planStepTotal)
})

const hasInlinePlanConfirm = computed(() => {
  if (!confirmedPlanArchive.value) return false
  return getAllToolCallsMerged().some(
    t => t.status === 'pending_confirm' && !!(t as PendingConfirmTool).planStepOrder,
  )
})

const showActionDock = computed(() => {
  if (hasInlinePlanConfirm.value) return false
  return !!(pendingAction.value && !pendingAction.value.resolved)
    || !!findPendingConfirmTool()
})

function needsInlineConfirm(tc: ToolCall) {
  return tc.status === 'pending_confirm'
    && !!(tc as PendingConfirmTool).planStepOrder
}

function needsInlineApprovalNotice(tc: ToolCall) {
  if (needsInlineApprovedRun(tc)) return false
  return confirmedPlanArchive.value
    && tc.status === 'pending_approval'
    && !!(tc as PendingConfirmTool).planStepOrder
}

function needsInlineApprovedRun(tc: ToolCall): boolean {
  if (!confirmedPlanArchive.value || !pendingAction.value) return false
  if (pendingAction.value.type !== 'approved_run') return false
  const apvId = (tc as PendingConfirmTool & { approvalId?: string }).approvalId
  return apvId === pendingAction.value.approvalId
    || pendingAction.value.toolName === tc.toolName
}

function showPlanConclusion(group: (typeof groupedMessages.value)[number]) {
  if (isKnowledgeQaGroup(group)) return false
  if (planExecutionActive.value && group === lastAgentGroup.value && !planAllCompleted.value) return false
  // 总结流式阶段：有工具即展示结论卡（流动式逐段填充）
  if (
    group === lastAgentGroup.value
    && chatStore.responsePhase === 'summary'
    && group.tools.length
  ) {
    return true
  }
  if (!group.conclusion) return false
  if (!group.tools.length && (isProgressOnlyConclusion(group.conclusion) || isOpsToolConclusion(group.conclusion))) {
    return false
  }
  return true
}

function userQuestionForGroup(group: (typeof groupedMessages.value)[number]): string {
  const groups = groupedMessages.value
  const idx = groups.findIndex(g => g.id === group.id)
  for (let i = idx; i >= 0; i--) {
    if (groups[i].type === 'user') return groups[i].msg.content || ''
  }
  return findLastUserQuestion()
}

function isPlanIncomplete(): boolean {
  if (!shouldAllowPlanContinue()) return false
  const traceId = lastAgentGroup.value?.msg.traceId
  const merged = traceId ? getToolCallsForTrace(traceId) : getAllToolCallsMerged()
  const withPlan = merged.filter(t => (t as PendingConfirmTool).planStepTotal)
  const terminal = new Set(['completed', 'failed', 'blocked', 'rejected'])
  if (withPlan.length) {
    const total = Math.max(...withPlan.map(t => (t as PendingConfirmTool).planStepTotal || 0))
    if (countTerminalPlanSteps(merged, total) < total) return true
    return false
  }
  const p = planProgressState.value
  return !!(p?.totalSteps && (p.completedSteps ?? 0) < p.totalSteps)
}

function ensurePlanArchiveFromTools() {
  if (!shouldAllowPlanContinue()) return
  if (confirmedPlanArchive.value) return
  const merged = getAllToolCallsMerged()
  const sample = merged.find(t => (t as PendingConfirmTool).planStepTotal) as PendingConfirmTool | undefined
  if (!sample?.planStepTotal) return
  const anchor = lastAgentGroup.value?.id
  if (!anchor) return
  const steps = []
  for (let o = 1; o <= sample.planStepTotal; o++) {
    const tc = merged.find(t => (t as PendingConfirmTool).planStepOrder === o) as PendingConfirmTool | undefined
    steps.push({
      order: o,
      action: tc?.planStepAction || previewCmdFromTool(tc || sample),
    })
  }
  confirmedPlanArchive.value = {
    anchorGroupId: anchor,
    planId: 'restored-from-tools',
    plan: { phenomenon: findLastUserQuestion(), steps },
    riskMessage: null,
  }
}

function hasEffectivePendingAction(): boolean {
  const merged = getAllToolCallsMerged()
  for (const tc of merged) {
    if (tc.status === 'executing') return true
    if (tc.status === 'pending_approval') return true
    if (tc.status !== 'pending_confirm') continue
    const order = (tc as PendingConfirmTool).planStepOrder
    if (order != null && isStepOrderDone(merged, order)) continue
    return true
  }
  return false
}

function isPlanStuck(): boolean {
  if (!shouldAllowPlanContinue()) return false
  if (continuePlanBusy.value || chatStore.isStreaming) return false
  if (hasInlinePlanConfirm.value || findPendingConfirmTool()) return false
  if (hasEffectivePendingAction()) return false
  ensurePlanArchiveFromTools()
  if (!isPlanIncomplete()) return false
  return true
}

function tryContinueStuckPlan() {
  const sid = chatStore.currentSessionId
  if (!sid || !shouldAllowPlanContinue() || !isPlanStuck() || chatStore.isStreaming) return
  if (hasInlinePlanConfirm.value || findPendingConfirmTool()) return
  continuePlanBusy.value = true
  chatStore.setStreaming(true)
  abortController.value = continuePlanExecution(sid, {
    onToken: (token: string) => {
      const isSummaryToken = chatStore.responsePhase === 'summary'
        || token.includes('## 执行结论')
        || token.includes('**总览**')
      if (isSummaryToken) {
        if (token.includes('## 执行结论')) chatStore.prepareSummaryStream()
        chatStore.appendSummaryToken(token)
      } else {
        chatStore.appendToLastMessage(token)
      }
      scrollToBottom()
    },
    onSummaryStart: () => {
      chatStore.prepareSummaryStream()
      chatStore.setResponsePhase('summary', '正在生成执行结论…')
    },
    onSummaryDone: () => {
      chatStore.setResponsePhase('', '')
      planProgress.value = computePlanProgressFromTools()
    },
    onToolCall: (tool: any) => {
      upsertToolCall(tool)
      scrollToBottom()
    },
    onToolResult: (result: any) => applyToolResult(result),
    onPlanProgress: (payload: any) => {
      if (payload) planProgress.value = payload
      scrollToBottom()
    },
    onConfirmRequired: (confirm: any) => {
      upsertToolCall({
        id: confirm.id,
        toolName: confirm.toolName,
        params: confirm.params || {},
        riskLevel: confirm.riskLevel,
        status: 'pending_confirm',
        pendingExecutionId: confirm.pendingExecutionId,
        planStepOrder: confirm.planStepOrder,
        planStepTotal: confirm.planStepTotal,
        planStepAction: confirm.planStepAction,
        commandPreview: confirm.commandPreview,
      })
      showPendingConfirmAction({
        pendingExecutionId: confirm.pendingExecutionId,
        toolName: confirm.toolName,
        params: confirm.params || {},
        riskLevel: confirm.riskLevel,
        commandPreview: confirm.commandPreview,
        message: confirm.message,
      })
      chatStore.setStreaming(false)
      scrollToPendingConfirm()
    },
    onApprovalRequired: (approval: any) => {
      upsertToolCall({
        id: approval.id,
        toolName: approval.toolName,
        params: approval.params || {},
        riskLevel: approval.riskLevel,
        status: 'pending_approval',
        approvalId: approval.approvalId,
        planStepOrder: approval.planStepOrder,
        planStepTotal: approval.planStepTotal,
        planStepAction: approval.planStepAction,
        commandPreview: approval.commandPreview,
      })
      planProgress.value = computePlanProgressFromTools()
      waitingApprovalId.value = approval.approvalId
      void approvalStore.refreshPending()
      startApprovalPolling()
      startAwaitingRunPolling(sid)
      chatStore.setStreaming(false)
    },
    onBlocked: () => {},
    onDone: async (result: any) => {
      continuePlanBusy.value = false
      chatStore.setStreaming(false)
      await syncMessagesFallback(sid)
      syncPlanProgressConclusion()
      ensurePlanArchiveFromTools()
      if (result.pendingConfirm) await restorePendingConfirmFromMessages()
      if (result.planCompleted) {
        planProgress.value = computePlanProgressFromTools()
        finishExploringSteps()
        chatStore.setResponsePhase('', '')
        syncPlanFinalConclusion()
      } else if (isPlanIncomplete() && shouldAllowPlanContinue()) {
        setTimeout(() => tryContinueStuckPlan(), 200)
      }
      if (result.pendingConfirm) scrollToPendingConfirm()
      else scrollToBottom()
    },
    onError: (err: any) => {
      continuePlanBusy.value = false
      chatStore.setStreaming(false)
      if (!shouldAllowPlanContinue()) return
      const msg = err?.message || ''
      if (msg.includes('未找到已确认的方案')) return
      chatStore.addMessage({
        id: Date.now().toString(36) + '-plan-err',
        role: 'system',
        content: `续跑方案失败: ${err?.message || '未知错误'}。请稍后重试或点击进度卡中的「继续执行方案」。`,
        createdAt: new Date().toISOString(),
      })
    },
  }, selectedServerId.value)
}

type PendingConfirmTool = ToolCall & {
  pendingExecutionId?: string
  commandPreview?: string
  planStepOrder?: number
  planStepTotal?: number
  planStepAction?: string
}

function buildCommandPreviewFromTool(tool: PendingConfirmTool) {
  if (tool.commandPreview) return tool.commandPreview
  const p = tool.params || {}
  if (p.command) return String(p.command)
  if (tool.toolName === 'manage_service') {
    return `systemctl ${p.action || '?'} ${p.service_name || p.service || '?'}`
  }
  if (tool.toolName === 'kill_process') {
    return `kill -${p.signal || 'TERM'} ${p.pid}`
  }
  return ''
}

function toolStatusPriority(status: string) {
  if (['completed', 'failed', 'rejected', 'blocked', 'timeout'].includes(status)) return 3
  if (status === 'executing') return 2
  if (status === 'pending_confirm' || status === 'pending_approval') return 1
  return 0
}

function resolvePlanStepStatus(matches: ToolCall[]): string {
  if (!matches.length) return 'pending'
  if (matches.some(t => t.status === 'pending_approval')) return 'pending_approval'
  if (matches.some(t => t.status === 'pending_confirm')) return 'pending_confirm'
  if (matches.some(t => t.status === 'executing')) return 'executing'
  const terminal = new Set(['completed', 'failed', 'blocked', 'rejected', 'skipped'])
  const best = matches.reduce((a, b) =>
    toolStatusPriority(b.status) >= toolStatusPriority(a.status) ? b : a,
  )
  return terminal.has(best.status) ? best.status : 'pending'
}

function isStepOrderDone(merged: ToolCall[], order: number): boolean {
  const matches = merged.filter(t => (t as PendingConfirmTool).planStepOrder === order)
  if (!matches.length) return false
  const status = resolvePlanStepStatus(matches)
  return ['completed', 'failed', 'blocked', 'rejected', 'skipped'].includes(status)
}

function toolMergeKey(tc: ToolCall, linkedPeIds: Set<string>): string {
  const pe = (tc as PendingConfirmTool).pendingExecutionId
  const apv = (tc as PendingConfirmTool & { approvalId?: string }).approvalId
  if (pe) return `pe:${pe}`
  if (apv) return `apv:${apv}`
  if (tc.id && linkedPeIds.has(tc.id)) return `pe:${tc.id}`
  const step = (tc as PendingConfirmTool).planStepOrder
  if (step) return `step:${step}:${previewCmdFromTool(tc)}`
  return `id:${tc.id || `${tc.toolName}-${JSON.stringify(tc.params || {})}`}`
}

function mergeToolCallsById(tools: ToolCall[]): ToolCall[] {
  const linkedPeIds = new Set<string>()
  for (const tc of tools) {
    const pe = (tc as PendingConfirmTool).pendingExecutionId
    if (pe) linkedPeIds.add(pe)
  }
  const byKey = new Map<string, ToolCall>()
  const order: string[] = []
  for (const tc of tools) {
    const key = toolMergeKey(tc, linkedPeIds)
    if (!byKey.has(key)) order.push(key)
    const existing = byKey.get(key)
    if (!existing || toolStatusPriority(tc.status) >= toolStatusPriority(existing.status)) {
      byKey.set(key, {
        ...existing,
        ...tc,
        id: existing?.id || tc.id,
        ...((tc as PendingConfirmTool).pendingExecutionId || existing
          ? { pendingExecutionId: (tc as PendingConfirmTool).pendingExecutionId
              || (existing as PendingConfirmTool)?.pendingExecutionId
              || (linkedPeIds.has(tc.id) ? tc.id : undefined) }
          : {}),
      } as ToolCall)
    }
  }
  return order.map(k => byKey.get(k)!)
}

function getAllToolCallsMerged(): PendingConfirmTool[] {
  const raw: ToolCall[] = []
  for (const m of chatStore.messages) {
    if (m.role === 'tool_call' && m.toolCalls?.length) {
      raw.push(...m.toolCalls)
    }
  }
  return mergeToolCallsById(raw) as PendingConfirmTool[]
}

function findPendingConfirmTool(): PendingConfirmTool | null {
  const merged = getAllToolCallsMerged()
  for (let i = merged.length - 1; i >= 0; i--) {
    if (merged[i].status === 'pending_confirm') return merged[i]
  }
  return null
}

function findLastUserQuestion() {
  for (let i = chatStore.messages.length - 1; i >= 0; i--) {
    const m = chatStore.messages[i]
    if (m.role === 'user' && m.content && !['(resume)', '[确认执行方案]'].includes(m.content)) {
      return m.content
    }
  }
  return ''
}

function previewCmdFromTool(tool: ToolCall) {
  const p = tool.params || {}
  if (p.command) return String(p.command)
  if (tool.toolName === 'manage_service') {
    return `systemctl ${p.action || '?'} ${p.service_name || p.service || '?'}`
  }
  return tool.toolName
}

function isQaIntent(intent?: string | null): boolean {
  const i = intent ?? chatStore.currentIntent
  return i === 'knowledge_qa' || i === 'general_qa'
}

function getToolCallsForTrace(traceId?: string | null): PendingConfirmTool[] {
  if (!traceId) return []
  const raw: ToolCall[] = []
  for (const m of chatStore.messages) {
    if (m.role === 'tool_call' && m.traceId === traceId && m.toolCalls?.length) {
      raw.push(...m.toolCalls)
    }
  }
  return mergeToolCallsById(raw) as PendingConfirmTool[]
}

function isKnowledgeQaGroup(group: (typeof groupedMessages.value)[number] | null): boolean {
  if (!group || group.type !== 'agent') return false
  if (group.tools.length > 0) return false
  if (isQaIntent()) return true
  const text = [group.intro, group.body, group.msg.content, group.conclusion].join('\n')
  return text.includes('参考来源')
    || text.includes('知识库条目')
    || text.includes('总结建议')
    || /\*\*[^*]+说明\*\*/.test(text)
}

function kbStandaloneBody(group: (typeof groupedMessages.value)[number]): string {
  if (group.tools.length || group.body) return ''
  const raw = (group.msg.content || '').trim()
  if (!raw || group.conclusion) return ''
  return raw
}

function agentHeaderContent(group: (typeof groupedMessages.value)[number]): string {
  if (group.tools.length && group.intro && !group.body) return group.intro
  if (group.body && group.intro && hasKnowledgeOpener(group.intro)) return group.intro
  return ''
}

function agentMainContent(group: (typeof groupedMessages.value)[number]): string {
  if (group.tools.length) return ''
  if (group.body && group.intro && hasKnowledgeOpener(group.intro)) return group.body
  const full = [group.intro, group.body].filter(Boolean).join('\n\n').trim()
  return full || kbStandaloneBody(group)
}

function isKbContentStreaming(group: (typeof groupedMessages.value)[number]): boolean {
  if (group !== lastAgentGroup.value) return false
  if (!chatStore.isStreaming) return false
  if (!isQaIntent() && !isKnowledgeQaGroup(group)) return false
  if (chatStore.exploringSteps.some(s => s.status === 'running')) return false
  return chatStore.exploringSteps.length > 0 || !!agentMainContent(group)
}

/** 知识问答流式：思考栏叠在正文之上，正文从栏下穿过 */
function isKbStreamMask(group: (typeof groupedMessages.value)[number]): boolean {
  if (group !== lastAgentGroup.value) return false
  if (!chatStore.isStreaming) return false
  if (!showThinkingForGroup(group)) return false
  if (!isQaIntent() && !isKnowledgeQaGroup(group)) return false
  return true
}

function useKbComposeLayout(group: (typeof groupedMessages.value)[number]): boolean {
  if (group.type !== 'agent' || group.tools.length) return false
  if (showThinkingForGroup(group) || agentMainContent(group)) {
    if (group === lastAgentGroup.value) {
      return isQaIntent() || isKnowledgeQaGroup(group) || showThinkingForGroup(group)
    }
    return !!(showThinkingForGroup(group) && agentMainContent(group))
  }
  return false
}

function showAgentHeader(group: (typeof groupedMessages.value)[number]): boolean {
  return group.type === 'agent'
}

function showThinkingForGroup(group: (typeof groupedMessages.value)[number]): boolean {
  if (group !== lastAgentGroup.value) return false
  if (confirmedPlanArchive.value && planExecutionActive.value) return false
  if (chatStore.exploringSteps.length || chatStore.reasoningSteps.length) return true
  return chatStore.isStreaming && (isQaIntent() || isKnowledgeQaGroup(group))
}

function shouldAllowPlanContinue(): boolean {
  if (isQaIntent()) return false
  if (isKnowledgeQaGroup(lastAgentGroup.value)) return false
  if (confirmedPlanArchive.value) return true
  const traceId = lastAgentGroup.value?.msg.traceId
  const tools = traceId ? getToolCallsForTrace(traceId) : []
  return tools.some(t => !!(t as PendingConfirmTool).planStepTotal)
}

function isOpsToolConclusion(conclusion: string): boolean {
  const opsTools = [
    'get_memory_info', 'get_disk_usage', 'get_network_connections',
    'get_cpu_info', 'execute_command', 'manage_service',
  ]
  return opsTools.some(t => conclusion.includes(t))
}

function repairSessionMessagesOnLoad() {
  for (const group of groupedMessages.value) {
    if (group.type !== 'agent' || group.tools.length > 0) continue
    const raw = group.msg.content || ''
    if (!raw.includes('## 执行结论') && !raw.includes(TOOLS_CONTENT_MARKER)) continue
    const { intro, body, conclusion } = splitAgentContent(raw)
    if (!conclusion) continue
    if (isProgressOnlyConclusion(conclusion) || isOpsToolConclusion(conclusion)) {
      const prefix = [intro, body].filter(Boolean).join('\n\n').trim()
      group.msg.content = prefix
    }
  }
  const last = lastAgentGroup.value
  if (last && isKnowledgeQaGroup(last)) {
    confirmedPlanArchive.value = null
    planProgress.value = null
  }
  chatStore.setMessages(
    chatStore.messages.filter(m =>
      !(m.role === 'system' && (m.content || '').includes('续跑方案失败')),
    ),
  )
  ensurePlanArchiveFromTools()
  planProgress.value = computePlanProgressFromTools()
  syncPlanFinalConclusion()
}

/** 根据当前工具卡状态，同步方案进度或最终执行结论 */
function isProgressOnlyConclusion(text: string): boolean {
  if (!text.includes('## 执行结论')) return false
  const body = text.split('## 执行结论')[1] || ''
  return body.includes('当前方案执行进度如下')
    || body.includes('方案进度：')
    || body.includes('已完成步骤')
}

function hasRichConclusion(text: string): boolean {
  if (!text?.includes('## 执行结论')) return false
  if (isProgressOnlyConclusion(text)) return false
  if (isLightweightConclusion(text)) return false
  const body = extractLastConclusionBlock(text)
    .replace(/^##\s*执行结论\s*/i, '')
    .trim()
  if (body.length < 50) return false
  if (/\*\*(总览|关键发现|结论与建议)\*\*/.test(body)) return true
  if (/\bPID\s*\d+/i.test(body) || /\d+\.?\d*\s*%/.test(body)) return true
  return body.includes('**') && (body.includes('\n- ') || body.includes('\n1.'))
}

function assistantHasFinalConclusion(): boolean {
  for (let i = chatStore.messages.length - 1; i >= 0; i--) {
    const msg = chatStore.messages[i]
    if (msg.role !== 'assistant') continue
    const c = msg.content || ''
    if (hasRichConclusion(c)) return true
    if (c.includes('## 执行结论') && !isLightweightConclusion(c)) return true
  }
  return false
}

function shouldDeferClientConclusion(): boolean {
  return chatStore.isStreaming || chatStore.responsePhase === 'summary'
}

function syncPlanProgressConclusion() {
  if (isQaIntent() || isKnowledgeQaGroup(lastAgentGroup.value)) return
  if (shouldDeferClientConclusion()) return
  if (assistantHasFinalConclusion()) return

  const lastGroup = lastAgentGroup.value
  if (!lastGroup?.tools.length && !confirmedPlanArchive.value) return

  const traceId = lastGroup?.msg.traceId
  const merged = traceId ? getToolCallsForTrace(traceId) : getAllToolCallsMerged()
  if (!merged.length) return

  if (confirmedPlanArchive.value) {
    planProgress.value = computePlanProgressFromTools()
    if (planAllCompleted.value || isPlanCompleteFromTools()) {
      syncPlanFinalConclusion()
    }
    return
  }

  if (isPlanIncomplete() || planExecutionActive.value) {
    planProgress.value = computePlanProgressFromTools()
    return
  }

  if (!lastAssistantHasConclusion()) {
    syncLightweightConclusion()
  }
}

function isPlanCompleteFromTools(): boolean {
  const arch = confirmedPlanArchive.value
  if (!arch?.plan?.steps?.length) return false
  return countTerminalPlanSteps(getAllToolCallsMerged(), arch.plan.steps.length)
    >= arch.plan.steps.length
}

/** 方案全部步骤终态后，若后端未写入结论则前端按工具结果补全 */
function syncPlanFinalConclusion() {
  if (isQaIntent() || isKnowledgeQaGroup(lastAgentGroup.value)) return
  if (shouldDeferClientConclusion()) return
  if (lastAssistantHasConclusion() || assistantHasFinalConclusion()) return
  if (!confirmedPlanArchive.value?.plan?.steps?.length) return
  if (!planAllCompleted.value && !isPlanCompleteFromTools()) return

  const arch = confirmedPlanArchive.value
  const steps = arch.plan.steps as { order: number; action: string }[]
  const merged = getAllToolCallsMerged()
  const phenomenon = (arch.plan.phenomenon as string) || findLastUserQuestion().slice(0, 80)

  let okCount = 0
  let failCount = 0
  const lines: string[] = ['## 执行结论', '']
  lines.push(`针对您的诉求「${phenomenon}」，运维诊断方案已执行完毕。\n`)
  lines.push('**方案执行摘要**')

  for (const step of [...steps].sort((a, b) => a.order - b.order)) {
    const matches = merged.filter(t => (t as PendingConfirmTool).planStepOrder === step.order)
    if (!matches.length) {
      lines.push(`- 步骤 ${step.order} · ${step.action} → 未执行`)
      continue
    }
    const best = matches.reduce((a, b) =>
      toolStatusPriority(b.status) >= toolStatusPriority(a.status) ? b : a,
    )
    const cmd = previewCmdFromTool(best)
    const summary = best.displaySummary || best.result?.display_summary || ''
    if (best.status === 'completed') {
      okCount++
      lines.push(`- 步骤 ${step.order} · ${step.action}（\`${cmd}\`）→ ${summary || '已完成'}`)
    } else if (['failed', 'blocked'].includes(best.status)) {
      failCount++
      const err = best.result?.error || summary || '执行未成功'
      lines.push(`- 步骤 ${step.order} · ${step.action}（\`${cmd}\`）→ ⚠ ${err}`)
    } else {
      lines.push(`- 步骤 ${step.order} · ${step.action} → 状态：${best.status}`)
    }
  }

  lines.push(
    `\n**统计**：共 ${steps.length} 个步骤，成功 ${okCount} 步${failCount ? `，未成功 ${failCount} 步` : ''}。`,
  )
  lines.push('\n**结论与建议**')
  if (failCount) {
    lines.push('- 方案已走完，部分步骤未成功，请根据摘要中的失败原因逐项处理。')
    const low = `${phenomenon}`.toLowerCase()
    if (low.includes('cups') || phenomenon.includes('打印')) {
      lines.push('- 麒麟系 CUPS 日志可能不在 /var/log/cups/error_log，建议用 `journalctl -u cups -n 50` 继续排查。')
    }
  } else {
    lines.push('- 方案步骤均已执行，请结合上方各步工具输出综合判断当前状态。')
  }

  const conclusion = lines.join('\n')
  const target = lastAgentGroup.value?.msg
  if (!target) return
  const { intro, body } = splitAgentContent(target.content || '')
  const prefix = [intro, body].filter(Boolean).join('\n\n').trim()
  const base = (target.content || '').includes(TOOLS_CONTENT_MARKER)
    ? (target.content || '')
    : (prefix ? `${prefix}${TOOLS_CONTENT_MARKER}` : TOOLS_CONTENT_MARKER)
  target.content = mergeConclusionPreservingReport(base, conclusion)
}

/** 轻量 ReAct（无方案步骤）完成后，若后端未写入结论则前端补全 */
function syncLightweightConclusion() {
  if (isQaIntent() || isKnowledgeQaGroup(lastAgentGroup.value)) return
  if (confirmedPlanArchive.value || planExecutionActive.value) return
  if (shouldDeferClientConclusion()) return
  if (assistantHasFinalConclusion() || lastAssistantHasConclusion()) return

  const lastGroup = lastAgentGroup.value
  if (!lastGroup?.tools.length) return

  const traceId = lastGroup.msg.traceId
  const merged = traceId ? getToolCallsForTrace(traceId) : getAllToolCallsMerged()
  const completed = merged.filter(t => t.status === 'completed')
  const pending = merged.filter(t => ['pending_confirm', 'pending_approval'].includes(t.status))
  if (!completed.length || pending.length) return

  const userQ = findLastUserQuestion()
  const speedTc = completed.find(t => t.toolName === 'get_network_speed')
  const speedPrimary = speedTc?.result?.data?.primary

  const lines: string[] = ['## 执行结论', '']
  lines.push('**总览**')
  if (speedPrimary) {
    const { iface, rx_kbps, tx_kbps, rx_mbps, tx_mbps, rating, rating_label } = speedPrimary
    if (rating === 'idle') {
      lines.push(
        `网卡 **${iface}** 当前几乎无网络传输（下行 ${rx_kbps} KB/s、上行 ${tx_kbps} KB/s），处于**空闲状态**。`,
      )
    } else {
      lines.push(
        `网卡 **${iface}** 实时网速：下行 **${rx_kbps} KB/s**（${rx_mbps} Mbps）、上行 **${tx_kbps} KB/s**（${tx_mbps} Mbps），评价：**${rating_label}**。`,
      )
    }
  } else if (userQ) {
    lines.push(`已根据您的诉求「${userQ.slice(0, 80)}」完成检查，结果如下。`)
  } else {
    lines.push('已完成远程检查，结果如下。')
  }
  lines.push('', '**关键发现**')
  for (const tc of completed) {
    const summary = tc.displaySummary || tc.result?.display_summary || '已完成'
    lines.push(`- \`${previewCmdFromTool(tc)}\` → ${summary}`)
  }
  lines.push('', '**结论与建议**')
  if (speedPrimary) {
    if (speedPrimary.rating === 'idle') {
      lines.push('1. **当前评价：空闲** — 此刻无活跃传输，不代表网卡故障。')
      lines.push('2. 若要测试峰值带宽，请在有下载/业务流量时再采样。')
    } else if (['low', 'normal'].includes(speedPrimary.rating)) {
      lines.push('1. **当前评价：正常** — 实时网速处于健康范围。')
      lines.push('2. 若仍感觉慢，请排查 DNS、对端服务或链路质量。')
    } else {
      lines.push('1. **当前评价：偏高** — 带宽占用明显，请确认是否为预期任务。')
      lines.push('2. 可用 `ss -tunp` 排查高占用连接。')
    }
  } else if (userQ && /网速|带宽|流量|网络/.test(userQ)) {
    lines.push('1. 本次仅获取累计流量，无法评价实时网速快慢。')
    lines.push('2. 请重新提问或使用 get_network_speed 进行 1 秒采样。')
  } else {
    lines.push('1. 以上数据来自目标主机实时查询，可作为当前状态参考。')
    lines.push('2. 如需进一步排查，请说明具体现象。')
  }

  const conclusion = lines.join('\n')
  const target = lastGroup.msg
  const { intro, body } = splitAgentContent(target.content || '')
  const prefix = [intro, body].filter(Boolean).join('\n\n').trim()
  const base = (target.content || '').includes(TOOLS_CONTENT_MARKER)
    ? (target.content || '')
    : (prefix ? `${prefix}${TOOLS_CONTENT_MARKER}` : '')
  target.content = mergeConclusionPreservingReport(base, conclusion)
}

function showPendingConfirmAction(payload: {
  pendingExecutionId: string
  toolName: string
  params: Record<string, any>
  riskLevel?: string
  commandPreview?: string
  message?: string
}, options?: { silent?: boolean }) {
  if (
    pendingAction.value
    && !pendingAction.value.resolved
    && pendingAction.value.type === 'confirm'
    && pendingAction.value.pendingExecutionId === payload.pendingExecutionId
  ) {
    return
  }
  pendingAction.value = {
    type: 'confirm',
    pendingExecutionId: payload.pendingExecutionId,
    toolName: payload.toolName,
    params: payload.params || {},
    riskLevel: payload.riskLevel || 'L2',
    commandPreview: payload.commandPreview || buildCommandPreviewFromTool(payload as PendingConfirmTool),
    message: payload.message || '请在下方确认后执行。',
    resolved: false,
  }
  if (!options?.silent) scrollToBottom()
}

async function restorePendingConfirmFromMessages(): Promise<boolean> {
  const sid = chatStore.currentSessionId
  if (!sid) return false
  const tool = findPendingConfirmTool()
  try {
    const awaiting = await getAwaitingRun(sid)
    const item = awaiting?.items?.find((i: any) =>
      i.kind === 'confirm' || (!i.approvalId && i.pendingExecutionId),
    )
    if (item?.pendingExecutionId) {
      showPendingConfirmAction({
        pendingExecutionId: item.pendingExecutionId,
        toolName: item.toolName || tool?.toolName || 'execute_command',
        params: item.toolParams || tool?.params || {},
        riskLevel: item.riskLevel || tool?.riskLevel || 'L2',
        commandPreview: item.commandPreview || (tool ? buildCommandPreviewFromTool(tool) : ''),
        message: '请在下方确认后执行。',
      }, { silent: true })
      return true
    }
  } catch { /* ignore */ }
  if (tool?.pendingExecutionId) {
    showPendingConfirmAction({
      pendingExecutionId: tool.pendingExecutionId,
      toolName: tool.toolName,
      params: tool.params || {},
      riskLevel: tool.riskLevel || 'L2',
      commandPreview: buildCommandPreviewFromTool(tool),
      message: '请在下方确认后执行。',
    }, { silent: true })
    return true
  }
  syncPlanProgressConclusion()
  if (pendingAction.value?.type === 'confirm') {
    pendingAction.value = null
  }
  return false
}

function finishExploringSteps() {
  for (const s of chatStore.exploringSteps) {
    if (s.status === 'running') {
      chatStore.upsertExploringStep({ ...s, status: 'done' })
    }
  }
}

function settleExploringSteps(hint = '步骤已结束') {
  for (const s of chatStore.exploringSteps) {
    if (s.status === 'running') {
      chatStore.upsertExploringStep({ ...s, status: 'done', detail: hint })
    }
  }
  chatStore.setResponsePhase('', '')
}

function planArchiveStorageKey(sessionId: string) {
  return `kylin-plan-archive-${sessionId}`
}

function persistPlanArchive() {
  const sid = chatStore.currentSessionId
  if (!sid || !confirmedPlanArchive.value) return
  try {
    sessionStorage.setItem(planArchiveStorageKey(sid), JSON.stringify(confirmedPlanArchive.value))
  } catch { /* ignore */ }
}

function restorePlanArchive(sessionId: string) {
  confirmedPlanArchive.value = null
  try {
    const raw = sessionStorage.getItem(planArchiveStorageKey(sessionId))
    if (raw) confirmedPlanArchive.value = JSON.parse(raw)
  } catch { /* ignore */ }
}

async function applyDiagnosticPlanStart(payload: any) {
  stopPlanFallbackPoll()
  if (!planRiskMessage.value) {
    planRiskMessage.value = '您的请求涉及高风险操作，相关指令将需要审批后方可执行。'
  }
  diagnosticPlan.value = {
    planId: '',
    plan: {
      title: payload.title || '运维诊断与执行方案',
      intent: payload.intent,
      phenomenon: payload.phenomenon || '',
      possible_causes: [],
      steps: [],
      analysis_summary: '',
    },
    resolved: false,
    generating: true,
    traceId: payload.traceId,
  }
  chatStore.setStreaming(true)
  chatStore.setResponsePhase('plan', '正在生成诊断与执行方案…')
  chatStore.upsertExploringStep({
    id: 'plan_gen',
    title: '生成诊断方案',
    detail: '正在构建执行步骤…',
    status: 'running',
  })
  scrollToBottom()
}

function applyDiagnosticPlanDelta(delta: any) {
  if (!diagnosticPlan.value) {
    void applyDiagnosticPlanStart({
      traceId: delta.traceId,
      title: '运维诊断与执行方案',
      intent: chatStore.currentIntent || '',
      phenomenon: '',
    })
  }
  const current = diagnosticPlan.value!
  const plan = { ...current.plan }
  switch (delta.field) {
    case 'analysis_token':
      plan.analysis_summary = (plan.analysis_summary || '') + (delta.token || '')
      break
    case 'analysis_summary':
      plan.analysis_summary = delta.value || ''
      break
    case 'rag_sources':
      plan.rag_sources = delta.value
      break
    case 'possible_cause': {
      const causes = [...(plan.possible_causes || [])]
      causes[delta.index] = delta.value
      plan.possible_causes = causes.filter(Boolean)
      break
    }
    case 'possible_causes':
      plan.possible_causes = delta.value
      break
    case 'step': {
      const steps = [...(plan.steps || [])]
      steps[delta.index] = delta.value
      plan.steps = steps.filter(Boolean)
      break
    }
    case 'risk_note':
      plan.risk_note = delta.value
      break
    case 'preliminary_analysis':
      plan.preliminary_analysis = delta.value
      break
    case 'environment_scan':
      plan.environment_scan = delta.value
      break
    case 'file_protection':
      plan.file_protection_whitelist = delta.value
      plan.file_protection_count = delta.count
      break
    default:
      break
  }
  diagnosticPlan.value = { ...current, plan }
  scrollToBottom()
}

async function applyDiagnosticPlanPayload(payload: any) {
  if (!payload?.planId) return
  stopPlanFallbackPoll()
  if (!planRiskMessage.value) {
    planRiskMessage.value = '您的请求涉及高风险操作，相关指令将需要审批后方可执行。'
  }
  diagnosticPlan.value = {
    planId: payload.planId,
    plan: {
      ...(diagnosticPlan.value?.plan || {}),
      ...(payload.plan || {}),
      traceId: payload.traceId,
    },
    resolved: false,
    generating: false,
    traceId: payload.traceId,
  }
  finishExploringSteps()
  chatStore.setResponsePhase('plan', '请确认下方诊断方案')
  chatStore.upsertExploringStep({
    id: 'plan_gen',
    title: '生成诊断方案',
    detail: '方案已就绪',
    status: 'done',
  })
  const intro = '已生成运维诊断方案，请在下方确认后开始执行（含环境预检）。\n\n'
  const lastAssistant = [...chatStore.messages].reverse().find(m => m.role === 'assistant')
  if (!lastAssistant?.content?.includes('运维诊断方案')) {
    chatStore.appendToLastMessage(intro)
  }
  chatStore.setStreaming(false)
  scrollToBottom()
}

async function fetchPendingPlanFallback(sessionId: string) {
  if (!sessionId || diagnosticPlan.value?.planId) return false
  try {
    const p = await getPendingPlan(sessionId)
    if (p?.planId && p?.plan) {
      await applyDiagnosticPlanPayload(p)
      return true
    }
  } catch { /* ignore */ }
  return false
}

function stopPlanFallbackPoll() {
  if (planFallbackTimer.value) clearTimeout(planFallbackTimer.value)
  if (planPollTimer.value) clearInterval(planPollTimer.value)
  planFallbackTimer.value = null
  planPollTimer.value = null
}

/** 意图识别为高风险/故障分析后，SSE 若中断仍能从 pending-plan API 恢复方案卡片 */
function startPlanFallbackPoll(sessionId: string) {
  if (!sessionId || diagnosticPlan.value?.planId) return
  stopPlanFallbackPoll()
  chatStore.upsertExploringStep({
    id: 'plan_gen',
    title: '生成诊断方案',
    detail: '正在构建执行步骤…',
    status: 'running',
  })
  chatStore.setResponsePhase('plan', '正在生成诊断方案…')
  scrollToBottom()

  let attempts = 0
  const pollOnce = async () => {
    attempts += 1
    const ok = await fetchPendingPlanFallback(sessionId)
    if (ok) {
      stopPlanFallbackPoll()
      chatStore.upsertExploringStep({
        id: 'plan_gen',
        title: '生成诊断方案',
        detail: '方案已就绪',
        status: 'done',
      })
      return true
    }
    if (attempts >= 15) {
      stopPlanFallbackPoll()
      chatStore.setStreaming(false)
      finishExploringSteps()
    }
    return false
  }

  planFallbackTimer.value = setTimeout(async () => {
    if (await pollOnce()) return
    planPollTimer.value = setInterval(() => { void pollOnce() }, 2000)
  }, 800)
}

async function syncMessagesFallback(sessionId: string) {
  try {
    const data = await getMessages(sessionId)
    if (data?.items?.length) {
      chatStore.setMessages(data.items)
    }
    await fetchPendingPlanFallback(sessionId)
    syncPlanProgressConclusion()
    await restorePendingConfirmFromMessages()
    pruneRedundantRejectionNotices()
    if (!lastAssistantHasConclusion()) {
      await recoverRejectedApprovalSummary(sessionId)
    }
    syncPlanFinalConclusion()
    scrollToBottom()
  } catch { /* ignore */ }
}

function showApprovedRunConfirm(payload: {
  approvalId: string
  pendingExecutionId?: string
  toolName: string
  params: Record<string, any>
  riskLevel: string
  commandPreview?: string
  message?: string
}, options?: { silent?: boolean }) {
  stopAwaitingRunPolling()
  stopApprovalPolling()
  waitingApprovalId.value = null
  pendingAction.value = {
    type: 'approved_run',
    approvalId: payload.approvalId,
    pendingExecutionId: payload.pendingExecutionId,
    toolName: payload.toolName,
    params: payload.params || {},
    riskLevel: payload.riskLevel || 'L4',
    commandPreview: payload.commandPreview,
    message: payload.message || '管理员已批准此操作，请确认是否在虚拟机执行。',
    resolved: false,
  }
  if (!options?.silent) {
    chatStore.addMessage({
      id: Date.now().toString(36) + '-apvok-' + Math.random().toString(36).slice(2, 10),
      role: 'system',
      content: '管理员已批准，请在下方确认要执行的命令。',
      createdAt: new Date().toISOString(),
    })
    scrollToBottom()
  }
}

function lastAssistantHasConclusion() {
  for (let i = chatStore.messages.length - 1; i >= 0; i--) {
    const m = chatStore.messages[i]
    if (m.role === 'assistant') {
      return (m.content || '').includes('## 执行结论')
    }
  }
  return false
}

function pruneRedundantRejectionNotices() {
  if (!lastAssistantHasConclusion()) return
  const redundant = new Set([
    '操作已被管理员拒绝',
    '审批已超时，操作未执行',
    '操作已被拒绝',
  ])
  chatStore.setMessages(
    chatStore.messages.filter(m => !(m.role === 'system' && redundant.has(m.content || ''))),
  )
}

async function recoverRejectedApprovalSummary(sessionId: string) {
  if (lastAssistantHasConclusion()) return
  try {
    const data = await getApprovalHistory(1, 30)
    const items = data?.items || []
    const hit = items.find((a: any) =>
      a.sessionId === sessionId && ['rejected', 'timeout'].includes(a.status),
    )
    if (hit?.id) {
      await handleApprovalResolved(hit.id)
    }
  } catch { /* ignore */ }
}

function collectPendingApprovalIds(): string[] {
  const ids = new Set<string>()
  for (const m of chatStore.messages) {
    for (const tc of m.toolCalls || []) {
      if (tc.status === 'pending_approval' && (tc as any).approvalId) {
        ids.add((tc as any).approvalId)
      }
    }
  }
  if (waitingApprovalId.value) ids.add(waitingApprovalId.value)
  return [...ids]
}

function markToolsByApproval(approvalId: string, status: 'rejected' | 'approved', reason?: string) {
  for (const m of chatStore.messages) {
    if (!m.toolCalls?.length) continue
    for (const tc of m.toolCalls) {
      if ((tc as any).approvalId !== approvalId) continue
      if (status === 'rejected') {
        tc.status = 'rejected'
        tc.result = { success: false, error: reason || '管理员已拒绝：不予执行' }
      }
    }
  }
}

async function handleApprovalResolved(approvalId: string) {
  const sid = chatStore.currentSessionId
  try {
    const detail = await getApprovalById(approvalId)
    if (detail?.status === 'approved') {
      let pendingExecutionId: string | undefined
      if (sid) {
        try {
          const awaiting = await getAwaitingRun(sid)
          const item = awaiting?.items?.find((i: any) => i.approvalId === approvalId)
          pendingExecutionId = item?.pendingExecutionId
        } catch { /* ignore */ }
      }
      showApprovedRunConfirm({
        approvalId,
        pendingExecutionId,
        toolName: detail.toolName,
        params: detail.toolParams || {},
        riskLevel: detail.riskLevel,
        commandPreview: detail.commandPreview,
        message: '管理员已批准此操作，请确认是否在虚拟机执行。',
      })
      return
    }
    if (detail?.status === 'rejected' || detail?.status === 'timeout') {
      pendingAction.value = null
      waitingApprovalId.value = null
      const reason = detail?.status === 'timeout'
        ? '审批超时，操作未执行'
        : (detail?.comment ? `管理员已拒绝：${detail.comment}` : '管理员已拒绝：不予执行')
      markToolsByApproval(approvalId, 'rejected', reason)
      planProgress.value = computePlanProgressFromTools()
      scrollToBottom()
      if (!sid) return
      chatStore.setStreaming(true)
      try {
        await finalizeApprovalRejection(sid, approvalId, {
          onToken: (token: string) => {
            chatStore.appendToLastMessage(token)
            scrollToBottom()
          },
          onSummaryStart: () => {
            chatStore.prepareSummaryStream()
            chatStore.setResponsePhase('summary', '正在生成执行结论…')
          },
          onSummaryDone: () => {
            chatStore.setResponsePhase('', '')
            syncPlanProgressConclusion()
          },
          onToolCallsUpdated: (payload) => {
            if (!payload?.toolCalls?.length) return
            const msgs = chatStore.messages
            const idx = payload.messageId
              ? msgs.findIndex(m => m.id === payload.messageId)
              : -1
            if (idx >= 0) {
              msgs[idx].toolCalls = payload.toolCalls
            } else {
              for (let i = msgs.length - 1; i >= 0; i--) {
                if (msgs[i].role === 'tool_call') {
                  msgs[i].toolCalls = payload.toolCalls
                  break
                }
              }
            }
          },
          onError: () => { /* 结论生成失败时由 syncMessagesFallback 兜底 */ },
          onDone: () => {},
        })
      } finally {
        chatStore.setStreaming(false)
        await syncMessagesFallback(sid)
        pruneRedundantRejectionNotices()
        scrollToBottom()
      }
      return
    }
  } catch {
    pendingAction.value = null
  }
}

function startApprovalPolling(approvalId?: string) {
  stopApprovalPolling()
  const pollOnce = async () => {
    const ids = approvalId ? [approvalId] : collectPendingApprovalIds()
    if (!ids.length) {
      stopApprovalPolling()
      return
    }
    let anyResolved = false
    for (const id of ids) {
      try {
        const detail = await getApprovalById(id)
        if (!detail || detail.status === 'pending') continue
        anyResolved = true
        const pa = pendingAction.value
        if (pa?.type === 'approval' && pa.approvalId === id && !pa.resolved) {
          pa.resolved = true
        }
        await handleApprovalResolved(id)
      } catch { /* ignore transient errors */ }
    }
    if (anyResolved && !collectPendingApprovalIds().length) {
      stopApprovalPolling()
    }
  }
  pollOnce()
  pollTimer.value = setInterval(pollOnce, 2000)
}

function stopAwaitingRunPolling() {
  if (awaitingRunTimer.value) {
    clearInterval(awaitingRunTimer.value)
    awaitingRunTimer.value = null
  }
}

/** 轮询已批准、待用户确认执行的 L4 操作（审批页通过后对话页自动弹出确认框） */
function startAwaitingRunPolling(sessionId: string) {
  stopAwaitingRunPolling()
  const pollOnce = async () => {
    try {
      const awaiting = await getAwaitingRun(sessionId)
      const item = awaiting?.items?.find((i: any) => i.kind === 'approved_run' || i.approvalId)
      if (!item?.approvalId) return
      stopAwaitingRunPolling()
      stopApprovalPolling()
      waitingApprovalId.value = null
      showApprovedRunConfirm({
        approvalId: item.approvalId,
        pendingExecutionId: item.pendingExecutionId,
        toolName: item.toolName,
        params: item.toolParams || {},
        riskLevel: item.riskLevel,
        commandPreview: item.commandPreview,
        message: '管理员已批准此操作，请确认是否在虚拟机执行。',
      })
    } catch { /* ignore */ }
  }
  pollOnce()
  awaitingRunTimer.value = setInterval(pollOnce, 3000)
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
  const groups: { id: string; type: string; msg: Message; tools: ToolCall[]; intro: string; body: string; conclusion: string }[] = []
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
      const mergedTools = mergeToolCallsById(tools)
      const { intro, body, conclusion } = splitAgentContent(msg.content || '')
      groups.push({ id: msg.id, type: 'agent', msg, tools: mergedTools, intro, body, conclusion })
      i = j
    } else if (msg.role === 'user') {
      groups.push({ id: msg.id, type: 'user', msg, tools: [], intro: '', body: '', conclusion: '' })
      i++
    } else if (msg.role === 'system') {
      groups.push({ id: msg.id, type: 'system', msg, tools: [], intro: '', body: '', conclusion: '' })
      i++
    } else {
      const tc = mergeToolCallsById((msg.toolCalls || []) as ToolCall[])
      groups.push({ id: msg.id, type: 'agent', msg: { ...msg, content: '' }, tools: tc, intro: '', body: '', conclusion: '' })
      i++
    }
  }
  // 将仅含执行结论的 assistant 消息合并到前一组（工具卡所在组）
  for (let k = groups.length - 1; k > 0; k--) {
    const g = groups[k]
    const prev = groups[k - 1]
    if (
      g.type === 'agent'
      && prev.type === 'agent'
      && !g.tools.length
      && prev.tools.length
      && g.conclusion
      && !prev.conclusion
    ) {
      prev.conclusion = g.conclusion
      prev.msg = {
        ...prev.msg,
        content: [prev.msg.content, g.conclusion].filter(Boolean).join('\n\n'),
      }
      groups.splice(k, 1)
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

interface PlanUiState {
  riskMessage: string | null
  plan: Record<string, any>
  mode: 'confirm' | 'readonly'
  stream: boolean
  generating?: boolean
  confirmable?: boolean
  traceId?: string
  userQuestion?: string
}

function planUiForGroup(group: (typeof groupedMessages.value)[number]): PlanUiState | null {
  if (diagnosticPlan.value && !diagnosticPlan.value.resolved && group === lastAgentGroup.value) {
    return {
      riskMessage: planRiskMessage.value,
      plan: diagnosticPlan.value.plan,
      mode: 'confirm',
      stream: !diagnosticPlan.value.generating,
      generating: !!diagnosticPlan.value.generating,
      confirmable: !!diagnosticPlan.value.planId,
      traceId: diagnosticPlan.value.traceId || group.msg.traceId,
      userQuestion: userQuestionForGroup(group),
    }
  }
  const arch = confirmedPlanArchive.value
  if (arch && arch.anchorGroupId === group.id) {
    return {
      riskMessage: arch.riskMessage,
      plan: arch.plan,
      mode: 'readonly',
      stream: false,
      traceId: group.msg.traceId,
      userQuestion: userQuestionForGroup(group),
    }
  }
  return null
}

function hasAgentBlocks(group: (typeof groupedMessages.value)[number]) {
  const isLast = group === lastAgentGroup.value
  return !!(
    group.tools.length
    || (group.conclusion && showPlanConclusion(group))
    || (isLast && chatStore.stateCards.length)
    || (isLast && planExecutionActive.value && planProgressState.value)
  )
}

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

const phaseLabels: Record<string, string> = {
  intent: '识别意图',
  plan: '规划方案',
  execute: '执行工具',
  answer: '生成回答',
  summary: '撰写结论',
}

const showStreamingBar = computed(() => {
  if (!chatStore.isStreaming) return false
  const last = lastAgentGroup.value
  if (last && isKbStreamMask(last)) return false
  return true
})

const streamingStatusText = computed(() => {
  const phase = chatStore.responsePhase
  const msg = chatStore.responsePhaseMessage
  if (msg) return msg
  if (phase && phaseLabels[phase]) return phaseLabels[phase] + '…'
  if (chatStore.exploringSteps.length) {
    const last = chatStore.exploringSteps[chatStore.exploringSteps.length - 1]
    return last?.title ? `${last.title}…` : 'Agent 处理中…'
  }
  return 'Agent 思考中…'
})

function scrollToBottom() {
  nextTick(() => {
    const el = msgContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

/** 方案续跑/确认后，将视口定位到当前待执行的命令确认卡 */
function scrollToPendingConfirm() {
  nextTick(() => {
    const el = msgContainer.value
    if (!el) return
    const cards = el.querySelectorAll('.cmd-confirm-card')
    const target = cards[cards.length - 1] as HTMLElement | undefined
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    } else {
      scrollToBottom()
    }
  })
}

function scrollToTrace(traceId: string) {
  nextTick(() => {
    const container = msgContainer.value
    if (!container || !traceId) return
    const selector = `[data-trace-id="${traceId.replace(/"/g, '\\"')}"]`
    const el = container.querySelector(selector) as HTMLElement | null
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      highlightTraceId.value = traceId
      if (highlightTraceTimer) clearTimeout(highlightTraceTimer)
      highlightTraceTimer = setTimeout(() => {
        highlightTraceId.value = null
      }, 3200)
    } else {
      ElMessage.info('未定位到该轮对话，已打开会话')
    }
  })
}

function applyTraceFromRoute() {
  const trace = route.query.trace
  if (typeof trace === 'string' && trace) {
    chatStore.setCurrentTraceId(trace)
    scrollToTrace(trace)
  }
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
  showTraceFeedback.value = false
  activeFeedbackTraceId.value = null
  diagnosticPlan.value = null
  planRiskMessage.value = null
  confirmedPlanArchive.value = null
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
  showTraceFeedback.value = false
  activeFeedbackTraceId.value = null
  diagnosticPlan.value = null
  planRiskMessage.value = null
  chatStore.setCurrentSession(id)
  chatStore.resetAgentState()
  try {
    const data = await getMessages(id)
    chatStore.setMessages(data.items || [])
    repairSessionMessagesOnLoad()
    syncPlanProgressConclusion()
    restorePlanArchive(id)
    scrollToBottom()
  } catch {}
  await restorePendingActions(id)
  await syncFeedbackBarForSession(id)
  await loadRollbackStatus()
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

function toolCallMatches(
  tc: ToolCall,
  toolId?: string,
  pendingExecutionId?: string,
  approvalId?: string,
): boolean {
  const pe = (tc as PendingConfirmTool).pendingExecutionId
  const apv = (tc as PendingConfirmTool & { approvalId?: string }).approvalId
  if (toolId && (tc.id === toolId || pe === toolId)) return true
  if (pendingExecutionId && (pe === pendingExecutionId || tc.id === pendingExecutionId)) return true
  if (approvalId && apv === approvalId) return true
  return false
}

function findAllToolCallMatches(
  toolId?: string,
  pendingExecutionId?: string,
  approvalId?: string,
): PendingConfirmTool[] {
  const hits: PendingConfirmTool[] = []
  for (const msg of chatStore.messages) {
    if (msg.role !== 'tool_call' || !msg.toolCalls?.length) continue
    for (const tc of msg.toolCalls) {
      if (toolCallMatches(tc, toolId, pendingExecutionId, approvalId)) {
        hits.push(tc as PendingConfirmTool)
      }
    }
  }
  return hits
}

function findToolCallMatch(
  toolId?: string,
  pendingExecutionId?: string,
  approvalId?: string,
): PendingConfirmTool | null {
  const hits = findAllToolCallMatches(toolId, pendingExecutionId, approvalId)
  if (!hits.length) return null
  return hits.reduce((best, tc) =>
    (toolStatusPriority(tc.status) >= toolStatusPriority(best.status) ? tc : best),
  )
}

function findToolCallById(toolId: string): ToolCall | null {
  if (!toolId) return null
  return findToolCallMatch(toolId)
}

function upsertToolCall(tool: any) {
  const toolId = tool.id || tool.toolCallId
  const peId = tool.pendingExecutionId
  const apvId = tool.approvalId
  const existing = findToolCallMatch(toolId, peId, apvId)
  const next: ToolCall = {
    id: toolId || Date.now().toString(36),
    toolName: tool.toolName,
    params: tool.params || {},
    riskLevel: tool.riskLevel || 'L1',
    status: (tool.status || 'executing') as ToolCall['status'],
    ...(tool.pendingExecutionId ? { pendingExecutionId: tool.pendingExecutionId } as any : {}),
    ...(tool.commandPreview ? { commandPreview: tool.commandPreview } as any : {}),
    ...(tool.planStepOrder ? {
      planStepOrder: tool.planStepOrder,
      planStepTotal: tool.planStepTotal,
      planStepAction: tool.planStepAction,
    } as any : {}),
    ...(tool.approvalId ? { approvalId: tool.approvalId } as any : {}),
  }
  if (existing) {
    next.id = existing.id
    Object.assign(existing, next)
    return existing
  }
  chatStore.addMessage({
    id: Date.now().toString(36) + '-tc-' + Math.random().toString(36).slice(2, 10),
    role: 'tool_call',
    content: '',
    toolCalls: [next],
    createdAt: new Date().toISOString(),
  })
  return next
}

function applyToolResult(result: any) {
  const toolId = result.id || result.toolCallId
  const hits = findAllToolCallMatches(toolId, result.pendingExecutionId, result.approvalId)
  if (hits.length) {
    for (const hit of hits) {
      hit.status = (result.status || 'completed') as ToolCall['status']
      hit.result = result.result
      hit.displaySummary = result.displaySummary || result.result?.display_summary || ''
      if (hit.status !== 'pending_confirm') {
        delete (hit as PendingConfirmTool).pendingExecutionId
      }
      delete (hit as PendingConfirmTool & { approvalId?: string }).approvalId
    }
    planProgress.value = null
    syncPlanProgressConclusion()
    return
  }
  const msgs = chatStore.messages
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role !== 'tool_call' || !msgs[i].toolCalls?.length) continue
    const list = msgs[i].toolCalls!
    const idx = toolId ? list.findIndex(tc => tc.id === toolId) : list.length - 1
    if (idx < 0) continue
    const tc = list[idx]
    tc.status = result.status || 'completed'
    tc.result = result.result
    tc.displaySummary = result.displaySummary || result.result?.display_summary || ''
    planProgress.value = null
    syncPlanProgressConclusion()
    return
  }
}

async function handleSend(
  text: string,
  pendingData?: { approvalId?: string; pendingExecutionId?: string; confirmPlanId?: string },
) {
  if (!chatStore.currentSessionId) {
    await handleNewSession()
    return handleSend(text, pendingData)
  }

  const isResume = !!(pendingData?.approvalId || pendingData?.pendingExecutionId || pendingData?.confirmPlanId)

  if (chatStore.isStreaming) {
    if (!isResume) return
    abortController.value?.abort()
    chatStore.setStreaming(false)
  }

  if (!isResume) {
    const pre = validateChatInput(text)
    if (!pre.valid) {
      chatStore.addMessage({
        id: Date.now().toString(36) + '-val-' + Math.random().toString(36).slice(2, 10),
        role: 'system', content: pre.message || '输入无效', createdAt: new Date().toISOString(),
      })
      return
    }
    text = pre.sanitized || text
    showTraceFeedback.value = false
    activeFeedbackTraceId.value = null
    if (chatStore.currentSessionId) {
      clearPendingFeedbackTrace(chatStore.currentSessionId)
    }
    diagnosticPlan.value = null
    if (!isResume) {
      planRiskMessage.value = null
    }
    const msgId = Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10)
    const userMsg: Message = {
      id: msgId, role: 'user', content: text, createdAt: new Date().toISOString(),
    }
    chatStore.addMessage(userMsg)
    chatStore.resetAgentState()
  }

  if (!isResume) {
    pendingAction.value = null
  } else {
    stopAwaitingRunPolling()
    waitingApprovalId.value = null
  }
  chatStore.setStreaming(true)

  const assistantMsgId = Date.now().toString(36) + '-a-' + Math.random().toString(36).slice(2, 10)
  const resumeOnly = isResume && (
    !!pendingData?.pendingExecutionId || !!pendingData?.approvalId
  ) && !pendingData?.confirmPlanId
  const needAssistantBubble = !resumeOnly && (
    !isResume
    || !!pendingData?.confirmPlanId
    || !!pendingData?.approvalId
    || !!pendingData?.pendingExecutionId
  )
  if (needAssistantBubble) {
    const assistantMsg: Message = {
      id: assistantMsgId, role: 'assistant', content: '', createdAt: new Date().toISOString(),
    }
    chatStore.addMessage(assistantMsg)
  }
  scrollToBottom()

  const resumingConfirm = !!pendingData?.pendingExecutionId
  const resumePeId = pendingData?.pendingExecutionId
  if (resumingConfirm && confirmedPlanArchive.value) {
    settleExploringSteps('方案步骤执行中')
  }

  abortController.value = sendMessage(
    chatStore.currentSessionId!,
    isResume ? '(resume)' : text,
    {
      onToken: (token: string) => {
        const isSummaryToken = chatStore.responsePhase === 'summary'
          || token.includes('## 执行结论')
          || token.includes('**总览**')
        if (isSummaryToken) {
          if (token.includes('## 执行结论')) chatStore.prepareSummaryStream()
          chatStore.appendSummaryToken(token)
        } else {
          chatStore.appendToLastMessage(token)
        }
        scrollToBottom()
      },
      onToolCall: (tool: any) => {
        upsertToolCall(tool)
        scrollToBottom()
      },
      onToolResult: (result: any) => {
        applyToolResult(result)
      },
      onApprovalRequired: (approval: any) => {
        waitingApprovalId.value = approval.approvalId || null
        upsertToolCall({
          id: approval.id,
          toolName: approval.toolName,
          params: approval.params || {},
          riskLevel: approval.riskLevel,
          status: 'pending_approval',
          approvalId: approval.approvalId,
          pendingExecutionId: approval.pendingExecutionId,
          planStepOrder: approval.planStepOrder,
          planStepTotal: approval.planStepTotal,
          planStepAction: approval.planStepAction,
          commandPreview: approval.commandPreview,
        })
        planProgress.value = computePlanProgressFromTools()
        void approvalStore.refreshPending()
        pendingAction.value = {
          type: 'approval', approvalId: approval.approvalId,
          toolName: approval.toolName, params: approval.params || {},
          riskLevel: approval.riskLevel, message: approval.message,
          expiresAt: approval.expiresAt, resolved: false,
        }
        if (!confirmedPlanArchive.value) {
          chatStore.addMessage({
            id: Date.now().toString(36) + '-apv-' + Math.random().toString(36).slice(2, 10),
            role: 'system', content: approval.message, createdAt: new Date().toISOString(),
          })
        }
        chatStore.setStreaming(false)
        startApprovalPolling()
        const sid = chatStore.currentSessionId
        if (sid) startAwaitingRunPolling(sid)
      },
      onPlanProgress: (payload: any) => {
        if (payload) planProgress.value = payload
        scrollToBottom()
      },
      onConfirmRequired: (confirm: any) => {
        upsertToolCall({
          id: confirm.id,
          toolName: confirm.toolName,
          params: confirm.params || {},
          riskLevel: confirm.riskLevel,
          status: 'pending_confirm',
          pendingExecutionId: confirm.pendingExecutionId,
          planStepOrder: confirm.planStepOrder,
          planStepTotal: confirm.planStepTotal,
          planStepAction: confirm.planStepAction,
          commandPreview: confirm.commandPreview,
        })
        showPendingConfirmAction({
          pendingExecutionId: confirm.pendingExecutionId,
          toolName: confirm.toolName,
          params: confirm.params || {},
          riskLevel: confirm.riskLevel,
          commandPreview: confirm.commandPreview,
          message: confirm.message,
        })
        settleExploringSteps('待您确认后执行')
        chatStore.setStreaming(false)
        scrollToPendingConfirm()
      },
      onBlocked: (blocked: any) => {
        chatStore.addMessage({
          id: Date.now().toString(36) + '-blk-' + Math.random().toString(36).slice(2, 10),
          role: 'system', content: `已阻止: ${blocked.message}`, createdAt: new Date().toISOString(),
        })
      },
      onIntent: (intent: any) => {
        chatStore.setIntentResolved({
          intent: intent.intent,
          label: intent.label,
          confidence: intent.confidence,
        })
      },
      onIntentResolved: (payload: any) => {
        chatStore.setIntentResolved({
          intent: payload.intent,
          label: payload.label,
          confidence: payload.confidence,
        })
        const sid = chatStore.currentSessionId
        if (
          sid
          && ['high_risk', 'fault_analysis'].includes(payload.intent)
          && !diagnosticPlan.value?.planId
        ) {
          startPlanFallbackPoll(sid)
        }
      },
      onResponsePhase: (payload: any) => {
        chatStore.setResponsePhase(payload.phase || '', payload.message || payload.detail || '')
      },
      onSummaryStart: () => {
        chatStore.prepareSummaryStream()
        chatStore.setResponsePhase('summary', '正在生成执行结论…')
      },
      onSummaryDone: () => {
        chatStore.setResponsePhase('', '')
        planProgress.value = computePlanProgressFromTools()
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
        if (notice?.message) {
          planRiskMessage.value = notice.message
          scrollToBottom()
        }
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
      onExploringStep: (step: any) => {
        if (resumingConfirm && confirmedPlanArchive.value) return
        if (step?.id) {
          chatStore.upsertExploringStep({
            id: step.id,
            title: step.title || '',
            detail: step.detail,
            status: step.status || 'running',
          })
          scrollToBottom()
          if (
            step.id === 'intent'
            && step.status === 'done'
            && ['high_risk', 'fault_analysis'].includes(chatStore.currentIntent || '')
          ) {
            const sid = chatStore.currentSessionId
            if (sid && !diagnosticPlan.value?.planId) startPlanFallbackPoll(sid)
          }
        }
      },
      onRouteDispatch: (payload: any) => {
        if (payload?.linkLabel) {
          chatStore.upsertExploringStep({
            id: 'workflow-link',
            title: payload.linkLabel,
            detail: payload.linkDescription || payload.reason,
            status: 'done',
          })
        }
      },
      onTaskProgress: (payload: any) => {
        if (payload?.stageLabel) {
          chatStore.upsertExploringStep({
            id: 'task-progress',
            title: payload.stageLabel,
            detail: payload.progress != null ? `进度 ${payload.progress}%` : undefined,
            status: payload.isCompleted ? 'done' : 'running',
          })
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
        chatStore.setStreaming(false)
        const errMsg = err?.message || err?.error || '未知错误'
        const inConfirmFlow = !!(
          resumingConfirm
          || pendingAction.value?.type === 'confirm'
          || findPendingConfirmTool()
        )
        if (inConfirmFlow) {
          const sid = chatStore.currentSessionId
          const peId = resumingConfirm ? resumePeId : undefined
          void (async () => {
            if (sid) {
              const data = await getMessages(sid)
              if (data?.items?.length) chatStore.setMessages(data.items)
            }
            if (peId) {
              for (const tool of findAllToolCallMatches(peId, peId)) {
                if (tool.status === 'pending_confirm' || tool.status === 'executing') {
                  tool.status = 'failed'
                  tool.result = { success: false, error: errMsg }
                  delete tool.pendingExecutionId
                }
              }
            }
            syncPlanProgressConclusion()
            await restorePendingConfirmFromMessages()
          })()
          chatStore.addMessage({
            id: Date.now().toString(36) + '-err-' + Math.random().toString(36).slice(2, 10),
            role: 'system',
            content: `命令执行未成功：${errMsg}`,
            createdAt: new Date().toISOString(),
          })
          scrollToBottom()
          return
        }
        const inApprovalFlow = !!(
          waitingApprovalId.value
          || pendingAction.value?.type === 'approval'
          || pendingAction.value?.type === 'approved_run'
        )
        if (inApprovalFlow) {
          void restorePendingConfirmFromMessages()
          chatStore.addMessage({
            id: Date.now().toString(36) + '-net-' + Math.random().toString(36).slice(2, 10),
            role: 'system',
            content: '连接已中断，但审批流程仍在进行。管理员批准后请在本页下方点击「确认执行」；如未出现按钮，请稍候或刷新页面。',
            createdAt: new Date().toISOString(),
          })
          const sid = chatStore.currentSessionId
          const apvId = waitingApprovalId.value || pendingAction.value?.approvalId
          if (apvId && !pollTimer.value) startApprovalPolling()
          if (sid) startAwaitingRunPolling(sid)
          scrollToBottom()
          return
        }
        chatStore.addMessage({
          id: Date.now().toString(36) + '-err-' + Math.random().toString(36).slice(2, 10),
          role: 'system', content: `操作失败: ${err?.message || '未知错误'}`,
          createdAt: new Date().toISOString(),
        })
        stopApprovalPolling()
        stopAwaitingRunPolling()
        pendingAction.value = null
      },
      onDiagnosticPlanStart: (payload: any) => {
        void applyDiagnosticPlanStart(payload)
      },
      onDiagnosticPlanDelta: (delta: any) => {
        applyDiagnosticPlanDelta(delta)
      },
      onDiagnosticPlan: (payload: any) => {
        void applyDiagnosticPlanPayload(payload)
      },
      onEnvPrecheck: (env: any) => {
        if (!env?.passed) {
          chatStore.addMessage({
            id: Date.now().toString(36) + '-env-' + Math.random().toString(36).slice(2, 10),
            role: 'system',
            content: '环境预检查未通过: ' + JSON.stringify(env?.checks || env),
            createdAt: new Date().toISOString(),
          })
        }
      },
      onDone: (result: any) => {
        stopPlanFallbackPoll()
        if (result.traceId) chatStore.setCurrentTraceId(result.traceId)
        chatStore.setStreaming(false)
        const awaitingAction = ['awaiting_approval', 'awaiting_user_action', 'awaiting_confirm'].includes(result.status)
        if (result.approvalId) waitingApprovalId.value = result.approvalId
        if (result.status === 'completed') {
          waitingApprovalId.value = null
          stopAwaitingRunPolling()
        }
        if (!awaitingAction) {
          stopApprovalPolling()
        } else {
          const apvId = result.approvalId
            || waitingApprovalId.value
            || pendingAction.value?.approvalId
          if (apvId && !pollTimer.value) {
            startApprovalPolling()
          }
        }
        if (result.status === 'awaiting_user_action' || result.status === 'awaiting_confirm') {
          const sid = chatStore.currentSessionId
          if (sid) startAwaitingRunPolling(sid)
          settleExploringSteps('待您确认后执行')
          if (result.pendingConfirm || resumingConfirm) scrollToPendingConfirm()
        }
        if (result.status === 'awaiting_approval') {
          settleExploringSteps('待管理员审批')
        }
        if (result.status === 'completed') {
          finishExploringSteps()
          chatStore.setResponsePhase('', '')
      if (result.planCompleted || planAllCompleted.value) {
        planProgress.value = computePlanProgressFromTools()
        syncPlanFinalConclusion()
      }
      void loadRollbackStatus()
        }
        if (result.planInProgress) {
          planProgress.value = computePlanProgressFromTools()
          if (result.pendingApproval) {
            settleExploringSteps('待管理员审批后继续方案')
          }
          if (!result.pendingConfirm && !result.pendingApproval && shouldAllowPlanContinue()) {
            setTimeout(() => tryContinueStuckPlan(), 400)
          }
        } else if (
          result.status === 'completed'
          && confirmedPlanArchive.value
          && isPlanIncomplete()
          && !result.planCompleted
        ) {
          planProgress.value = computePlanProgressFromTools()
          if (shouldAllowPlanContinue()) {
            setTimeout(() => tryContinueStuckPlan(), 400)
          }
        }
        if (result.status === 'awaiting_plan_confirm') {
          finishExploringSteps()
        } else if (result.status === 'permission_denied') {
          stopPlanFallbackPoll()
          finishExploringSteps()
          chatStore.upsertExploringStep({
            id: 'plan_gen',
            title: '生成诊断方案',
            detail: '权限不足，已终止',
            status: 'error',
          })
        } else if (result.status === 'completed' && chatStore.messages.some(m => m.role === 'tool_call')) {
          if (shouldAllowPlanContinue() && isPlanIncomplete() && !result.planCompleted) {
            setTimeout(() => tryContinueStuckPlan(), 300)
          } else {
            const sid = chatStore.currentSessionId
            if (sid && result.traceId) {
              setPendingFeedbackTrace(sid, result.traceId)
              void syncFeedbackBarForSession(sid)
            }
          }
        } else if (!awaitingAction) {
          showTraceFeedback.value = false
          activeFeedbackTraceId.value = null
        }
        const sid = chatStore.currentSessionId
        if (sid && (result.status === 'awaiting_plan_confirm' || (!diagnosticPlan.value && chatStore.currentIntent === 'high_risk'))) {
          void fetchPendingPlanFallback(sid)
        }
        if (
          sid
          && !diagnosticPlan.value
          && ['high_risk', 'fault_analysis'].includes(chatStore.currentIntent || '')
        ) {
          void syncMessagesFallback(sid)
        }
        if (
          sid
          && (
            resumingConfirm
            || result.planInProgress
            || result.pendingConfirm
            || result.pendingApproval
            || result.status === 'awaiting_user_action'
            || (result.status === 'completed' && isPlanIncomplete() && !result.planCompleted)
            || (result.status === 'completed' && chatStore.messages.some(m => m.role === 'tool_call'))
          )
        ) {
          void (async () => {
            await syncMessagesFallback(sid)
            syncPlanProgressConclusion()
            ensurePlanArchiveFromTools()
            if (result.status === 'awaiting_user_action' || result.pendingConfirm) {
              await restorePendingConfirmFromMessages()
              scrollToPendingConfirm()
            } else if (result.pendingApproval || result.approvalId) {
              const awaiting = await getAwaitingRun(sid)
              const approved = awaiting?.items?.find((i: any) => i.kind === 'approved_run')
              if (approved?.approvalId) {
                showApprovedRunConfirm({
                  approvalId: approved.approvalId,
                  pendingExecutionId: approved.pendingExecutionId,
                  toolName: approved.toolName,
                  params: approved.toolParams || {},
                  riskLevel: approved.riskLevel,
                  commandPreview: approved.commandPreview,
                }, { silent: true })
              }
            } else if (shouldAllowPlanContinue() && isPlanIncomplete() && !result.planCompleted) {
              tryContinueStuckPlan()
            } else if (!awaitingAction) {
              pendingAction.value = null
            }
            scrollToBottom()
          })()
        } else if (!awaitingAction) {
          pendingAction.value = null
        }
        loadSessions()
        scrollToBottom()
      },
    },
    pendingData?.approvalId,
    pendingData?.pendingExecutionId,
    selectedServerId.value,
    pendingData?.confirmPlanId,
  )
}

function handlePlanConfirm() {
  if (!diagnosticPlan.value?.planId) return
  const planId = diagnosticPlan.value.planId
  const anchor = lastAgentGroup.value
  if (anchor) {
    confirmedPlanArchive.value = {
      anchorGroupId: anchor.id,
      planId,
      plan: { ...diagnosticPlan.value.plan },
      riskMessage: planRiskMessage.value,
    }
    persistPlanArchive()
  }
  diagnosticPlan.value = null
  showTraceFeedback.value = false
  // 保留思考过程步骤直至执行结束
  chatStore.setReasoningSteps([])
  chatStore.setStateCards([])
  handleSend('', { confirmPlanId: planId })
}

function handlePlanCancel() {
  diagnosticPlan.value = null
  planRiskMessage.value = null
  confirmedPlanArchive.value = null
  const sid = chatStore.currentSessionId
  if (sid) {
    try { sessionStorage.removeItem(planArchiveStorageKey(sid)) } catch { /* ignore */ }
  }
  chatStore.addMessage({
    id: Date.now().toString(36) + '-pccl-' + Math.random().toString(36).slice(2, 10),
    role: 'system', content: '已取消诊断方案执行', createdAt: new Date().toISOString(),
  })
}

async function confirmRollback(mode: 'single_step' | 'full', tool?: ToolCall) {
  if (mode === 'full') {
    await ElMessageBox.confirm(
      '将按逻辑快照逆向撤销本会话中所有可回滚的写操作，此操作不可自动恢复。是否继续？',
      '确认全量回滚',
      {
        type: 'warning',
        confirmButtonText: '确认回滚',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--warning',
      },
    )
    return
  }
  const name = tool ? toolDisplayName(tool.toolName) : '该步骤'
  const hint = tool?.id ? rollbackByTool.value[tool.id]?.rollbackHint : ''
  const detail = hint ? `\n\n${hint}` : ''
  await ElMessageBox.confirm(
    `将撤销「${name}」对虚拟机系统的变更。${detail}`,
    '确认单步回滚',
    {
      type: 'warning',
      confirmButtonText: '确认回滚',
      cancelButtonText: '取消',
    },
  )
}

async function handleToolRollback(tool: ToolCall) {
  const sid = chatStore.currentSessionId
  if (!sid || !tool.id) return
  try {
    await confirmRollback('single_step', tool)
  } catch {
    return
  }
  const meta = rollbackByTool.value[tool.id]
  rollbackBusyId.value = tool.id
  try {
    const res = await rollbackSession(sid, 'single_step', {
      toolCallId: tool.id,
      logId: meta?.logId,
    })
    ElMessage.success(res?.message || '单步回滚完成')
    chatStore.addMessage({
      id: Date.now().toString(36) + '-rb-' + Math.random().toString(36).slice(2, 10),
      role: 'system',
      content: res?.message || '单步回滚完成',
      createdAt: new Date().toISOString(),
    })
    await loadRollbackStatus()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '单步回滚失败')
  } finally {
    rollbackBusyId.value = null
  }
}

async function handleRollback(mode: 'single_step' | 'full') {
  const sid = chatStore.currentSessionId
  if (!sid) return
  try {
    await confirmRollback(mode)
  } catch {
    return
  }
  if (mode === 'full') fullRollbackBusy.value = true
  try {
    const res = await rollbackSession(sid, mode)
    ElMessage.success(res?.message || '回滚请求已处理')
    chatStore.addMessage({
      id: Date.now().toString(36) + '-rb-' + Math.random().toString(36).slice(2, 10),
      role: 'system',
      content: res?.message || '回滚完成',
      createdAt: new Date().toISOString(),
    })
    await loadRollbackStatus()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '回滚失败')
  } finally {
    fullRollbackBusy.value = false
  }
}

function handleStop() {
  abortController.value?.abort()
  chatStore.setStreaming(false)
  pendingAction.value = null
  waitingApprovalId.value = null
  stopApprovalPolling()
  stopAwaitingRunPolling()
}

async function handleApprove() {
  if (!pendingAction.value || pendingAction.value.type !== 'approval') return
  const approvalId = pendingAction.value.approvalId
  if (!approvalId) return
  const saved = { ...pendingAction.value }
  try {
    const res = await approveApproval(approvalId, '通过')
    stopApprovalPolling()
    saved.resolved = true
    const data = res?.data || res
    showApprovedRunConfirm({
      approvalId,
      toolName: data?.toolName || saved.toolName,
      params: data?.toolParams || saved.params,
      riskLevel: data?.riskLevel || saved.riskLevel,
      commandPreview: data?.commandPreview,
      message: '审批已通过，请确认是否在虚拟机执行。',
    })
  } catch (e: any) {
    chatStore.addMessage({
      id: Date.now().toString(36) + '-err-' + Math.random().toString(36).slice(2, 10),
      role: 'system',
      content: '审批操作失败: ' + (e?.response?.data?.detail || e?.message || '请重试'),
      createdAt: new Date().toISOString(),
    })
  }
}

function handleApprovedRun() {
  if (!pendingAction.value || pendingAction.value.type !== 'approved_run') return
  const approvalId = pendingAction.value.approvalId
  const pendingExecutionId = pendingAction.value.pendingExecutionId
  if (!approvalId) return
  for (const tool of findAllToolCallMatches(undefined, pendingExecutionId, approvalId)) {
    tool.status = 'executing'
  }
  pendingAction.value.resolved = true
  pendingAction.value = null
  handleSend('', { approvalId, pendingExecutionId })
}

async function handleApprovedCancel() {
  if (!pendingAction.value || pendingAction.value.type !== 'approved_run') return
  const approvalId = pendingAction.value.approvalId
  const sessionId = chatStore.currentSessionId
  if (sessionId && approvalId) {
    try {
      await cancelAwaitingRun(sessionId, { approvalId })
    } catch {}
  }
  pendingAction.value.resolved = true
  pendingAction.value = null
  chatStore.addMessage({
    id: Date.now().toString(36) + '-ccl-' + Math.random().toString(36).slice(2, 10),
    role: 'system', content: '已取消执行，命令未在虚拟机运行', createdAt: new Date().toISOString(),
  })
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
    await handleApprovalResolved(approvalId)
  } catch (e: any) {
    chatStore.addMessage({
      id: Date.now().toString(36) + '-err-' + Math.random().toString(36).slice(2, 10),
      role: 'system', content: '审批操作失败: ' + (e?.response?.data?.detail || e?.message || '请重试'),
      createdAt: new Date().toISOString(),
    })
  }
}

function handleConfirmForTool(tc: ToolCall) {
  const peId = (tc as PendingConfirmTool).pendingExecutionId
  if (!peId) return handleConfirm()
  showPendingConfirmAction({
    pendingExecutionId: peId,
    toolName: tc.toolName,
    params: tc.params || {},
    riskLevel: tc.riskLevel || 'L2',
    commandPreview: buildCommandPreviewFromTool(tc as PendingConfirmTool),
  })
  handleConfirm()
}

function handleSkipForTool(tc: ToolCall) {
  const peId = (tc as PendingConfirmTool).pendingExecutionId
  if (peId) {
    showPendingConfirmAction({
      pendingExecutionId: peId,
      toolName: tc.toolName,
      params: tc.params || {},
      riskLevel: tc.riskLevel || 'L2',
      commandPreview: buildCommandPreviewFromTool(tc as PendingConfirmTool),
    })
  }
  handleSkip()
}

function handleCancelForTool(tc: ToolCall) {
  const peId = (tc as PendingConfirmTool).pendingExecutionId
  if (peId) {
    showPendingConfirmAction({
      pendingExecutionId: peId,
      toolName: tc.toolName,
      params: tc.params || {},
      riskLevel: tc.riskLevel || 'L2',
      commandPreview: buildCommandPreviewFromTool(tc as PendingConfirmTool),
    })
  }
  handleCancel()
}

async function handleConfirm() {
  if (chatStore.isStreaming) return
  let peId = pendingAction.value?.pendingExecutionId
  if (!peId) {
    peId = findPendingConfirmTool()?.pendingExecutionId
  }
  if (!peId) return
  if (!pendingAction.value || pendingAction.value.type !== 'confirm') {
    const tool = findPendingConfirmTool()
    if (tool) {
      showPendingConfirmAction({
        pendingExecutionId: peId,
        toolName: tool.toolName,
        params: tool.params || {},
        riskLevel: tool.riskLevel || 'L2',
        commandPreview: buildCommandPreviewFromTool(tool),
      })
    }
  }
  const tools = findAllToolCallMatches(peId, peId)
  if (!tools.length) {
    const fallback = findPendingConfirmTool()
    if (fallback) tools.push(fallback)
  }
  for (const tool of tools) tool.status = 'executing'
  syncPlanProgressConclusion()
  handleSend('', { pendingExecutionId: peId })
}

async function handleCancel() {
  const peId = pendingAction.value?.pendingExecutionId
    || findPendingConfirmTool()?.pendingExecutionId
  const sid = chatStore.currentSessionId
  if (sid && peId) {
    try {
      await cancelAwaitingRun(sid, { pendingExecutionId: peId })
    } catch { /* ignore */ }
  }
  const tool = peId ? findToolCallMatch(peId, peId) : findPendingConfirmTool()
  if (tool) tool.status = 'rejected'
  stopApprovalPolling()
  pendingAction.value = null
  chatStore.addMessage({
    id: Date.now().toString(36) + '-ccl-' + Math.random().toString(36).slice(2, 10),
    role: 'system', content: '操作已取消', createdAt: new Date().toISOString(),
  })
}

async function handleSkip() {
  const peId = pendingAction.value?.pendingExecutionId
    || findPendingConfirmTool()?.pendingExecutionId
  const sid = chatStore.currentSessionId
  if (sid && peId) {
    try {
      await cancelAwaitingRun(sid, { pendingExecutionId: peId })
    } catch { /* ignore */ }
  }
  const tool = peId ? findToolCallMatch(peId, peId) : findPendingConfirmTool()
  if (tool) tool.status = 'rejected'
  pendingAction.value = null
  chatStore.addMessage({
    id: Date.now().toString(36) + '-ccl-' + Math.random().toString(36).slice(2, 10),
    role: 'system', content: '已跳过该步骤', createdAt: new Date().toISOString(),
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
  stopAwaitingRunPolling()
  stopPlanFallbackPoll()
  window.removeEventListener('focus', handleWindowFocus)
})

function handleWindowFocus() {
  const sid = chatStore.currentSessionId
  if (sid) restorePendingActions(sid)
}

async function restorePendingActions(sessionId: string) {
  stopApprovalPolling()
  stopAwaitingRunPolling()
  try {
    syncPlanProgressConclusion()
    const pendingPlan = await getPendingPlan(sessionId)
    if (pendingPlan?.planId && pendingPlan?.plan) {
      pendingAction.value = null
      await applyDiagnosticPlanPayload(pendingPlan)
      return
    }

    const awaiting = await getAwaitingRun(sessionId)
    const confirmItem = awaiting?.items?.find((i: any) =>
      i.kind === 'confirm' || (!i.approvalId && i.pendingExecutionId),
    )
    if (confirmItem?.pendingExecutionId) {
      showPendingConfirmAction({
        pendingExecutionId: confirmItem.pendingExecutionId,
        toolName: confirmItem.toolName,
        params: confirmItem.toolParams || {},
        riskLevel: confirmItem.riskLevel,
        commandPreview: confirmItem.commandPreview,
      }, { silent: true })
      return
    }

    const runItem = awaiting?.items?.find((i: any) => i.kind === 'approved_run' || i.approvalId)
    if (runItem?.approvalId) {
      showApprovedRunConfirm({
        approvalId: runItem.approvalId,
        pendingExecutionId: runItem.pendingExecutionId,
        toolName: runItem.toolName,
        params: runItem.toolParams || {},
        riskLevel: runItem.riskLevel,
        commandPreview: runItem.commandPreview,
        message: '管理员已批准此操作，请确认是否在虚拟机执行。',
      }, { silent: true })
      return
    }

    if (await restorePendingConfirmFromMessages()) return

    pendingAction.value = null
    const data = await getPendingApprovals()
    const items = data?.items || []
    const match = items.find((item: any) => item.sessionId === sessionId)
    if (match) {
      waitingApprovalId.value = match.id
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
      startApprovalPolling()
      startAwaitingRunPolling(sessionId)
    }
  } catch {}
}

onMounted(async () => {
  window.addEventListener('focus', handleWindowFocus)
  await loadServerList()
  await loadSessions()
  if (route.params.id) {
    chatStore.setCurrentSession(route.params.id as string)
    try {
      const data = await getMessages(route.params.id as string)
      chatStore.setMessages(data.items || [])
      repairSessionMessagesOnLoad()
      syncPlanProgressConclusion()
    } catch {}
    await restorePendingActions(route.params.id as string)
    ensurePlanArchiveFromTools()
    syncPlanProgressConclusion()
    if (shouldAllowPlanContinue()) {
      setTimeout(() => tryContinueStuckPlan(), 800)
    }
    await recoverRejectedApprovalSummary(route.params.id as string)
    pruneRedundantRejectionNotices()
    await syncFeedbackBarForSession(route.params.id as string)
    await loadRollbackStatus()
    applyTraceFromRoute()
  }
})

watch(() => route.params.id, async (id) => {
  if (id) {
    showTraceFeedback.value = false
    activeFeedbackTraceId.value = null
    chatStore.setCurrentSession(id as string)
    try {
      const data = await getMessages(id as string)
      chatStore.setMessages(data.items || [])
      repairSessionMessagesOnLoad()
      syncPlanProgressConclusion()
    } catch {}
    await restorePendingActions(id as string)
    ensurePlanArchiveFromTools()
    syncPlanProgressConclusion()
    if (shouldAllowPlanContinue()) {
      setTimeout(() => tryContinueStuckPlan(), 800)
    }
    pruneRedundantRejectionNotices()
    await syncFeedbackBarForSession(id as string)
    await loadRollbackStatus()
    applyTraceFromRoute()
  }
})

watch(() => route.query.trace, (trace) => {
  if (typeof trace === 'string' && trace && route.params.id) {
    scrollToTrace(trace)
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
  min-height: 0;
  background: #ffffff;
}

.chat-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  position: relative;

  &.chat-body--welcome {
    --welcome-visual-center: 50%;
  }
}

/* 图2 内联布局；流式期间思考栏 sticky 轻遮罩，正文从下方穿过 */
.kb-answer-compose {
  position: relative;
}

.kb-answer-compose--streaming {
  .thinking-stack {
    position: sticky;
    top: 0;
    z-index: 12;
    margin-bottom: 0;
    padding-bottom: 4px;
    background: #fff;

    :deep(.exploring-panel) {
      box-shadow: 0 4px 12px -4px rgba(15, 23, 42, 0.1);
    }

    &::after {
      content: '';
      display: block;
      height: 10px;
      margin-top: 2px;
      background: linear-gradient(180deg, rgba(15, 23, 42, 0.06) 0%, transparent 100%);
      pointer-events: none;
    }
  }

  .kb-answer-body {
    position: relative;
    z-index: 1;
    margin-top: -2px;
  }
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

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.feedback-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid #dbeafe;
  border-radius: 6px;
  background: #fff;
  color: #2563eb;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
  &:hover:not(:disabled) {
    border-color: #2563eb;
    background: #eff6ff;
  }
  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    color: #94a3b8;
    border-color: #e2e8f0;
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
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px;
  position: relative;
  z-index: 1;

  &.chat-messages--welcome {
    position: relative;
    min-height: 100%;
    padding: 0 32px;
    overflow: hidden;
  }
}

.msg-wrapper {
  position: relative;
  border-radius: 12px;
  transition: box-shadow 0.25s ease, background 0.25s ease;
  &:hover .msg-delete-btn { opacity: 1; }
  &.trace-highlight {
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.35), 0 8px 24px rgba(37, 99, 235, 0.12);
    background: rgba(239, 246, 255, 0.65);
    animation: trace-pulse 1.2s ease 2;
  }
}

@keyframes trace-pulse {
  0%, 100% { box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.35), 0 8px 24px rgba(37, 99, 235, 0.12); }
  50% { box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.22), 0 10px 28px rgba(37, 99, 235, 0.16); }
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
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  z-index: 2;
  width: 100%;
  max-width: 640px;

  .welcome-title {
    transform: translateY(-50%);
    font-size: 28px;
    font-weight: 700;
    color: #2563eb;
    margin: 0;
    letter-spacing: 0.02em;
    position: relative;
    z-index: 1;
    line-height: 1.3;
  }

  .welcome-desc {
    font-size: 14px;
    color: #64748b;
    margin-top: 14px;
    max-width: 420px;
    line-height: 1.6;
    position: relative;
    z-index: 1;
  }

  :deep(.kb-danmaku-stream) {
    width: 100%;
    max-width: 620px;
    margin-top: 18px;
  }
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 22px;
  justify-content: center;
  position: relative;
  z-index: 1;
  max-width: 640px;
}

.quick-btn {
  padding: 8px 18px;
  border-radius: 20px;
  border: 1px solid rgba(186, 230, 253, 0.9);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(6px);
  color: #64748b;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
  &:hover {
    border-color: #2563eb;
    color: #2563eb;
    background: rgba(239, 246, 255, 0.95);
  }
}

/* 与 Agent 头像列对齐：34px 头像 + 12px 间距 */
.agent-aligned-blocks {
  margin-left: 46px;
  max-width: calc(100% - 46px);
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 4px;
  margin-bottom: 8px;

  :deep(.reasoning-chain),
  :deep(.state-cards) {
    margin: 0;
  }
}

.exploring-stack,
.thinking-stack {
  margin-top: 6px;
  margin-bottom: 4px;
}

.plan-flow-stack {
  margin-top: 6px;
  gap: 10px;
}

.msg-system.agent-aligned-blocks {
  margin-top: 4px;
  margin-bottom: 8px;
}

.system-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  margin: 0;
  border-radius: 8px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  font-size: 13px;
  color: #92400e;
  width: 100%;
  box-sizing: border-box;
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

.step-approval-notice {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin: 0 0 8px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #fed7aa;
  background: #fff7ed;
  font-size: 13px;
  line-height: 1.5;
  color: #9a3412;

  .notice-badge {
    flex-shrink: 0;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 6px;
    background: #ffedd5;
    color: #c2410c;
  }
}

.action-dock {
  margin-top: 8px;
  margin-bottom: 12px;

  .approval-bar-inner {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px 16px;
    box-shadow: 0 2px 10px rgba(15, 23, 42, 0.06);
  }
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

.approval-hint {
  margin: 8px 0 0;
  font-size: 13px;
  color: #57534e;
  line-height: 1.5;
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
