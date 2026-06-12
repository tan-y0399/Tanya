<template>
  <div class="settings-page">
    <div class="settings-bg" aria-hidden="true">
      <div class="bg-grid"></div>
    </div>

    <div class="settings-content">
      <header class="page-header">
        <div class="title-block">
          <span class="header-tag">CONFIG</span>
          <div>
            <h2 class="page-title">系统设置</h2>
            <p class="page-desc">[ LLM · TOOLS · SECURITY · STATUS · CORE MODULE ]</p>
          </div>
        </div>
        <div class="header-meta">
          <span class="meta-pill">4 MODULES</span>
          <span class="meta-pill hub">HUB INTERFACE</span>
        </div>
      </header>

      <div v-if="isLoading" class="settings-loading">
        <div class="loading-spinner"></div>
        <span>加载配置中...</span>
      </div>

      <div v-else-if="loadError" class="settings-error">
        <span>{{ loadError }}</span>
        <button type="button" @click="initSettings">重试</button>
      </div>

      <div v-else class="puzzle-stage">
        <div class="puzzle-grid" :class="puzzlePhase" :style="gridStyle">
          <SettingsPuzzlePiece quadrant="tl" class="grid-tl" :phase="puzzlePhase" :disabled="isSaving">
            <div class="field">
              <label>API 地址</label>
              <el-input v-model="settings.llm.apiBase" size="default" :disabled="formDisabled" />
            </div>
            <div class="field">
              <label>模型名称</label>
              <el-input v-model="settings.llm.model" size="default" :disabled="formDisabled" />
            </div>
            <div class="field">
              <label>API Key</label>
              <el-input v-model="settings.llm.apiKey" type="password" show-password size="default" :disabled="formDisabled" />
            </div>
            <div class="field-row">
              <div class="field">
                <label>温度</label>
                <el-input-number v-model="settings.llm.temperature" :min="0" :max="2" :step="0.1" :precision="1" size="default" :disabled="formDisabled" />
              </div>
              <div class="field">
                <label>最大 Token</label>
                <el-input-number v-model="settings.llm.maxTokens" :min="512" :max="32768" :step="512" size="default" :disabled="formDisabled" />
              </div>
            </div>
          </SettingsPuzzlePiece>

          <SettingsPuzzlePiece quadrant="tr" class="grid-tr" :phase="puzzlePhase" :disabled="isSaving">
            <div class="tool-list">
              <div v-for="tool in tools" :key="tool.id" class="tool-item">
                <div class="tool-info">
                  <span class="tool-name">{{ tool.name }}</span>
                  <span class="tool-desc">{{ tool.desc }}</span>
                </div>
                <el-switch v-model="tool.enabled" active-color="#06b6d4" :disabled="formDisabled" />
              </div>
            </div>
          </SettingsPuzzlePiece>

          <SettingsPuzzlePiece quadrant="bl" class="grid-bl" :phase="puzzlePhase" :disabled="isSaving">
            <SettingsSecurityPanel
              v-model:approval-timeout="settings.security.approvalTimeout"
              v-model:max-rounds="settings.security.maxRounds"
              :disabled="formDisabled || !isAdmin"
              :read-only="!isAdmin"
              :high-risk-tools="highRiskToolCount"
            />
          </SettingsPuzzlePiece>

          <SettingsPuzzlePiece quadrant="br" class="grid-br" :phase="puzzlePhase" :disabled="isSaving">
            <SettingsSystemStatus
              :components="components"
              :system-status="systemStatus"
              :version="systemVersion"
              :last-refresh="lastRefreshText"
              :llm-model="settings.llm.model"
              :enabled-tools="enabledToolCount"
              :total-tools="tools.length"
              :refreshing="isRefreshing"
              :disabled="formDisabled"
              @refresh="loadHealth"
            />
          </SettingsPuzzlePiece>

          <div class="puzzle-hub-cell">
            <div class="radar-field" :class="puzzlePhase" aria-hidden="true">
              <svg class="radar-rings" viewBox="0 0 400 400">
                <circle cx="200" cy="200" r="52" fill="none" stroke="rgba(37,99,235,0.1)" stroke-width="0.8" />
                <circle cx="200" cy="200" r="92" fill="none" stroke="rgba(37,99,235,0.08)" stroke-width="0.8" stroke-dasharray="4 6" />
                <circle cx="200" cy="200" r="132" fill="none" stroke="rgba(37,99,235,0.06)" stroke-width="0.8" />
                <circle cx="200" cy="200" r="172" fill="none" stroke="rgba(37,99,235,0.04)" stroke-width="0.8" stroke-dasharray="3 8" />
                <line x1="200" y1="200" x2="200" y2="28" stroke="rgba(37,99,235,0.06)" stroke-width="0.6" />
                <line x1="200" y1="200" x2="372" y2="200" stroke="rgba(37,99,235,0.06)" stroke-width="0.6" />
                <line x1="200" y1="200" x2="200" y2="372" stroke="rgba(37,99,235,0.06)" stroke-width="0.6" />
                <line x1="200" y1="200" x2="28" y2="200" stroke="rgba(37,99,235,0.06)" stroke-width="0.6" />
              </svg>
              <div class="radar-sweep"></div>
              <div class="radar-sweep-core"></div>
            </div>
            <div class="center-cross" :class="puzzlePhase" aria-hidden="true"></div>
            <SettingsHubConnector :phase="puzzlePhase" :disabled="isLoading" @save="saveSettings" />
          </div>
        </div>

        <div class="mobile-save-row">
          <button type="button" class="mobile-save-btn" :disabled="formDisabled" @click="saveSettings">
            {{ isSaving ? '保存中...' : '保存配置' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getConfig, updateConfig, getHealth } from '@/api/system'
import { getTools, batchUpdateTools } from '@/api/tools'
import { useUserStore } from '@/stores/user'
import SettingsPuzzlePiece from '@/components/settings/SettingsPuzzlePiece.vue'
import SettingsHubConnector from '@/components/settings/SettingsHubConnector.vue'
import SettingsSystemStatus, { type HealthComponent } from '@/components/settings/SettingsSystemStatus.vue'
import SettingsSecurityPanel from '@/components/settings/SettingsSecurityPanel.vue'

type PuzzlePhase = 'idle' | 'assembling' | 'locked' | 'success' | 'releasing'

const isSaving = ref(false)
const isRefreshing = ref(false)
const isLoading = ref(true)
const loadError = ref('')
const puzzlePhase = ref<PuzzlePhase>('idle')
const userStore = useUserStore()

const isAdmin = computed(() => userStore.userInfo?.role === 'admin')

const settings = reactive({
  llm: {
    apiBase: '',
    model: '',
    apiKey: '',
    temperature: 0.1,
    maxTokens: 4096,
  },
  security: {
    approvalTimeout: 60,
    maxRounds: 20,
  },
})

interface SettingsToolItem {
  id: string
  name: string
  desc: string
  enabled: boolean
  riskLevel: number
}

const tools = ref<SettingsToolItem[]>([])

const components = ref<HealthComponent[]>([
  { name: 'PostgreSQL 数据库', code: 'DB', status: 'online', latency: null, detail: '持久化存储' },
  { name: 'LLM API', code: 'LLM', status: 'online', latency: null, detail: '—' },
  { name: 'VM Agent 节点', code: 'SSH', status: 'online', latency: null, detail: '—', description: '麒麟 VM Agent 执行节点' },
])

const systemStatus = ref('healthy')
const systemVersion = ref('v1.0.0')
const lastRefreshAt = ref<Date | null>(null)

const enabledToolCount = computed(() => tools.value.filter(t => t.enabled).length)

const highRiskToolCount = computed(() =>
  tools.value.filter(t => t.enabled && t.riskLevel >= 3).length,
)

const lastRefreshText = computed(() => {
  if (!lastRefreshAt.value) return ''
  return lastRefreshAt.value.toLocaleTimeString('zh-CN', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
})

function mapCompStatus(raw: string): HealthComponent['status'] {
  if (raw === 'up') return 'online'
  if (raw === 'down') return 'offline'
  return 'warning'
}

function applyHealthData(data: any) {
  if (!data) return
  systemStatus.value = data.status || 'unknown'
  if (data.version) systemVersion.value = data.version.startsWith('v') ? data.version : `v${data.version}`
  lastRefreshAt.value = new Date()

  const comps = data.components || {}
  const list: HealthComponent[] = []

  if (comps.database) {
    list.push({
      name: 'PostgreSQL 数据库',
      code: 'DB',
      status: mapCompStatus(comps.database.status),
      latency: comps.database.latencyMs ?? null,
      detail: '持久化存储 · PostgreSQL',
    })
  }
  if (comps.llmApi) {
    list.push({
      name: 'LLM API',
      code: 'LLM',
      status: mapCompStatus(comps.llmApi.status),
      latency: comps.llmApi.latencyMs ?? null,
      detail: settings.llm.apiBase || settings.llm.model || '推理接口',
    })
  }
  if (comps.vmAgent) {
    list.push({
      name: 'VM Agent 节点',
      code: 'SSH',
      status: mapCompStatus(comps.vmAgent.status),
      latency: comps.vmAgent.latencyMs ?? null,
      detail: comps.vmAgent.host || '远程执行节点',
      description: comps.vmAgent.description,
    })
  }

  if (list.length) components.value = list
}

const formDisabled = computed(() => isSaving.value || puzzlePhase.value !== 'idle')

const gridStyle = computed(() => ({
  '--junction-gap': puzzlePhase.value === 'idle' || puzzlePhase.value === 'releasing' ? '22px' : '0px',
}))

function wait(ms: number) {
  return new Promise<void>(resolve => { window.setTimeout(resolve, ms) })
}

async function loadHealth() {
  if (isRefreshing.value || formDisabled.value) return
  isRefreshing.value = true
  try {
    const data = await getHealth()
    applyHealthData(data)
    ElMessage.success('状态刷新成功')
  } catch {
    ElMessage.error('状态刷新失败')
  } finally {
    isRefreshing.value = false
  }
}

function buildSavePayload() {
  const payload: Record<string, unknown> = {
    llm: { ...settings.llm },
  }
  if (isAdmin.value) {
    payload.security = {
      approvalTimeout: settings.security.approvalTimeout,
      maxConversationRounds: settings.security.maxRounds,
    }
  }
  return payload
}

function extractErrorMessage(error: unknown) {
  const err = error as { response?: { data?: { detail?: string | { msg?: string }[] } }; message?: string }
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg
  return err?.message || '配置保存失败，请重试'
}

async function saveSettings() {
  if (isSaving.value || puzzlePhase.value !== 'idle') return

  isSaving.value = true
  puzzlePhase.value = 'assembling'

  const apiPromise = Promise.all([
    updateConfig(buildSavePayload()),
    batchUpdateTools(tools.value.map(t => ({ id: t.id, enabled: t.enabled }))),
  ])

  await wait(720)
  puzzlePhase.value = 'locked'

  try {
    await apiPromise
    puzzlePhase.value = 'success'
    applyToolsData((await getTools()).items)
    await wait(2400)
  } catch (error: unknown) {
    ElMessage.error(extractErrorMessage(error))
    puzzlePhase.value = 'releasing'
    await wait(450)
    puzzlePhase.value = 'idle'
    isSaving.value = false
    return
  }

  puzzlePhase.value = 'releasing'
  await wait(550)
  puzzlePhase.value = 'idle'
  isSaving.value = false
}

function applyToolsData(items: Awaited<ReturnType<typeof getTools>>['items']) {
  tools.value = items.map(t => ({
    id: t.id,
    name: t.name,
    desc: t.description || '',
    enabled: t.enabled,
    riskLevel: t.riskLevel,
  }))
}

async function initSettings() {
  isLoading.value = true
  loadError.value = ''
  try {
    const [configData, healthData, toolsData] = await Promise.all([
      getConfig(),
      getHealth(),
      getTools(),
    ])
    if (configData) {
      if (configData.llm) Object.assign(settings.llm, configData.llm)
      if (configData.security) {
        settings.security.approvalTimeout = configData.security.approvalTimeout ?? settings.security.approvalTimeout
        settings.security.maxRounds =
          configData.security.maxConversationRounds
          ?? configData.security.maxRounds
          ?? settings.security.maxRounds
      }
    }
    applyHealthData(healthData)
    applyToolsData(toolsData.items)
  } catch {
    loadError.value = '无法加载配置，请检查后端服务是否运行'
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  initSettings()
})
</script>

<style lang="scss" scoped>
.settings-page {
  position: relative;
  min-height: 100%;
}

.settings-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;

  .bg-grid {
    position: absolute;
    inset: 0;
    background-image: radial-gradient(circle, rgba(148, 163, 184, 0.18) 1px, transparent 1px);
    background-size: 22px 22px;
    opacity: 0.55;
  }
}

.settings-content {
  position: relative;
  z-index: 1;
  max-width: 1100px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 22px;
}

.title-block {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.header-tag {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #6366f1;
  padding: 3px 7px;
  border-radius: 4px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
  margin-top: 4px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #1e293b;
}

.page-desc {
  margin: 4px 0 0;
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #94a3b8;
}

.header-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-pill {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #64748b;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.8);

  &.hub {
    color: #2563eb;
    border-color: rgba(37, 99, 235, 0.25);
    background: rgba(37, 99, 235, 0.06);
  }
}

.puzzle-stage {
  position: relative;
  padding: 8px 0 12px;
}

.puzzle-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) var(--junction-gap, 22px) minmax(0, 1fr);
  grid-template-rows: minmax(0, auto) var(--junction-gap, 22px) minmax(0, auto);
  transition:
    grid-template-columns 0.68s cubic-bezier(0.34, 1.08, 0.48, 1),
    grid-template-rows 0.68s cubic-bezier(0.34, 1.08, 0.48, 1);
}

.grid-tl { grid-area: 1 / 1; }
.grid-tr { grid-area: 1 / 3; }
.grid-bl { grid-area: 3 / 1; }
.grid-br { grid-area: 3 / 3; }

.puzzle-hub-cell {
  grid-area: 2 / 2;
  position: relative;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  min-height: 0;
  pointer-events: none;

  :deep(.hub-connector) {
    pointer-events: auto;
  }
}

.radar-field {
  position: absolute;
  left: 50%;
  top: 50%;
  z-index: 0;
  width: 360px;
  height: 360px;
  transform: translate(-50%, -50%);
  pointer-events: none;
  mask-image: radial-gradient(circle, #000 38%, transparent 78%);
  -webkit-mask-image: radial-gradient(circle, #000 38%, transparent 78%);
}

.radar-rings {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.radar-sweep {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: conic-gradient(
    from -90deg at 50% 50%,
    transparent 0deg,
    rgba(37, 99, 235, 0.03) 8deg,
    rgba(37, 99, 235, 0.1) 24deg,
    rgba(6, 182, 212, 0.22) 32deg,
    rgba(37, 99, 235, 0.08) 42deg,
    transparent 52deg,
    transparent 360deg
  );
  animation: radar-rotate 10s linear infinite;
}

.radar-sweep-core {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: conic-gradient(
    from -90deg at 50% 50%,
    transparent 0deg,
    transparent 30deg,
    rgba(99, 102, 241, 0.14) 31deg,
    rgba(6, 182, 212, 0.35) 32deg,
    transparent 33deg,
    transparent 360deg
  );
  animation: radar-rotate 10s linear infinite;
}

.radar-field.assembling,
.radar-field.locked {
  .radar-sweep,
  .radar-sweep-core {
    animation-duration: 2.8s;
  }
}

.radar-field.success {
  .radar-sweep {
    background: conic-gradient(
      from -90deg at 50% 50%,
      transparent 0deg,
      rgba(16, 185, 129, 0.06) 20deg,
      rgba(16, 185, 129, 0.2) 32deg,
      transparent 48deg,
      transparent 360deg
    );
    animation-duration: 4s;
  }

  .radar-sweep-core {
    background: conic-gradient(
      from -90deg at 50% 50%,
      transparent 0deg,
      transparent 30deg,
      rgba(16, 185, 129, 0.25) 31deg,
      rgba(52, 211, 153, 0.45) 32deg,
      transparent 33deg,
      transparent 360deg
    );
    animation-duration: 4s;
  }
}

@keyframes radar-rotate {
  to { transform: rotate(360deg); }
}

.center-cross {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 120px;
  height: 120px;
  margin: -60px 0 0 -60px;
  pointer-events: none;
  z-index: 5;
  opacity: 0.35;
  transition: opacity 0.5s ease;

  &::before,
  &::after {
    content: '';
    position: absolute;
    background: linear-gradient(90deg, transparent, rgba(37, 99, 235, 0.35), transparent);
  }

  &::before {
    left: 0;
    right: 0;
    top: 50%;
    height: 1px;
    margin-top: -0.5px;
  }

  &::after {
    top: 0;
    bottom: 0;
    left: 50%;
    width: 1px;
    margin-left: -0.5px;
    background: linear-gradient(0deg, transparent, rgba(37, 99, 235, 0.35), transparent);
  }

  &.assembling,
  &.locked,
  &.success {
    opacity: 0;
  }
}

.field {
  margin-bottom: 12px;

  label {
    display: block;
    font-size: 11px;
    font-weight: 600;
    color: #94a3b8;
    margin-bottom: 4px;
    letter-spacing: 0.04em;
  }
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.tool-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 268px;
  overflow-y: auto;
  padding-right: 2px;
}

.tool-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 8px;
  transition: background 0.15s;

  &:hover { background: rgba(6, 182, 212, 0.05); }

  .tool-name {
    font-family: 'Inter', 'PingFang SC', sans-serif;
    font-size: 12px;
    color: #0891b2;
    font-weight: 600;
    display: block;
  }

  .tool-desc {
    font-size: 10px;
    color: #94a3b8;
  }
}

.settings-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px;
  color: #94a3b8;
  gap: 16px;

  .loading-spinner {
    width: 36px;
    height: 36px;
    border: 3px solid #e2e8f0;
    border-top-color: #2563eb;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
}

.settings-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 48px;
  color: #dc2626;
  font-size: 14px;

  button {
    padding: 8px 20px;
    border: 1px solid #2563eb;
    border-radius: 8px;
    background: #fff;
    color: #2563eb;
    font-size: 13px;
    cursor: pointer;

    &:hover { background: #eff6ff; }
  }
}

.spinning {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 860px) {
  .puzzle-grid {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
  }

  .grid-tl,
  .grid-tr,
  .grid-bl,
  .grid-br {
    grid-area: auto;
  }

  .puzzle-hub-cell {
    display: none;
  }

  .mobile-save-row {
    display: flex;
    justify-content: center;
    margin-top: 20px;
  }

  .puzzle-piece.tl .piece-inner,
  .puzzle-piece.tr .piece-inner,
  .puzzle-piece.bl .piece-inner,
  .puzzle-piece.br .piece-inner {
    padding: 18px 20px 16px !important;
  }
}

.mobile-save-row {
  display: none;
}

.mobile-save-btn {
  padding: 10px 28px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #2563eb, #3b82f6);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(37, 99, 235, 0.25);

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}
</style>
