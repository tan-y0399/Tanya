<template>
  <div class="admin-config-stage">
    <div class="config-grid" :class="puzzlePhase" :style="gridStyle">
      <SettingsPuzzlePiece
        quadrant="tl"
        class="grid-llm"
        :phase="puzzlePhase"
        :disabled="saving"
      >
        <div class="llm-overview">
          <div class="overview-left">
            <span class="llm-badge">LLM ONLINE</span>
            <span class="llm-model">{{ llm.model || '未配置模型' }}</span>
          </div>
          <div class="model-ring">
            <span class="ring-val">{{ llm.maxTokens }}</span>
            <span class="ring-label">TOK</span>
          </div>
        </div>

        <div class="llm-metrics">
          <div class="metric-cell">
            <span class="m-label">BASE</span>
            <span class="m-val">{{ apiHostShort }}</span>
          </div>
          <div class="metric-cell">
            <span class="m-label">TEMP</span>
            <span class="m-val">{{ llm.temperature }}</span>
          </div>
          <div class="metric-cell">
            <span class="m-label">KEY</span>
            <span class="m-val">{{ llm.apiKey ? 'SET' : '—' }}</span>
          </div>
        </div>

        <div class="field">
          <label>API 地址</label>
          <span class="field-hint">OpenAI 兼容接口，如 http://host:port/v1</span>
          <el-input v-model="llm.apiBase" :disabled="saving" placeholder="https://api.example.com/v1" />
        </div>
        <div class="field">
          <label>模型名称</label>
          <span class="field-hint">调用的模型 ID</span>
          <el-input v-model="llm.model" :disabled="saving" placeholder="deepseek-chat" />
        </div>
        <div class="field">
          <label>API Key</label>
          <span class="field-hint">留空表示不修改已保存的值</span>
          <el-input v-model="llm.apiKey" type="password" show-password :disabled="saving" placeholder="••••••••" />
        </div>
        <div class="field-row">
          <div class="field">
            <label>温度</label>
            <span class="field-hint">0 更稳定，越高越发散</span>
            <el-input-number v-model="llm.temperature" :min="0" :max="2" :step="0.1" :precision="1" :disabled="saving" />
          </div>
          <div class="field">
            <label>最大 Token</label>
            <span class="field-hint">单次回复长度上限</span>
            <el-input-number v-model="llm.maxTokens" :min="512" :max="32768" :step="512" :disabled="saving" />
          </div>
        </div>
      </SettingsPuzzlePiece>

      <SettingsPuzzlePiece
        quadrant="tr"
        class="grid-sec"
        :phase="puzzlePhase"
        :disabled="saving"
        channel-tag="MOD-02"
        channel-code="SEC"
        channel-label="安全配置"
        channel-color="#6366f1"
      >
        <SettingsSecurityPanel
          v-model:approval-timeout="security.approvalTimeout"
          v-model:max-rounds="security.maxRounds"
          :disabled="saving"
          :high-risk-tools="highRiskTools"
        />
      </SettingsPuzzlePiece>

      <div class="config-hub-cell">
        <div class="radar-field" :class="puzzlePhase" aria-hidden="true">
          <svg class="radar-rings" viewBox="0 0 400 400">
            <circle cx="200" cy="200" r="52" fill="none" stroke="rgba(5,150,105,0.12)" stroke-width="0.8" />
            <circle cx="200" cy="200" r="92" fill="none" stroke="rgba(5,150,105,0.08)" stroke-width="0.8" stroke-dasharray="4 6" />
            <circle cx="200" cy="200" r="132" fill="none" stroke="rgba(5,150,105,0.06)" stroke-width="0.8" />
          </svg>
          <div class="radar-sweep"></div>
          <div class="radar-sweep-core"></div>
        </div>
        <div class="center-cross" :class="puzzlePhase" aria-hidden="true"></div>
        <SettingsHubConnector :phase="puzzlePhase" :disabled="saving" @save="emit('save')" />
      </div>
    </div>

    <div class="mobile-save-row">
      <button type="button" class="mobile-save-btn" :disabled="saving" @click="emit('save')">
        {{ saving ? '保存中…' : '保存配置' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import SettingsPuzzlePiece from '@/components/settings/SettingsPuzzlePiece.vue'
import SettingsHubConnector from '@/components/settings/SettingsHubConnector.vue'
import SettingsSecurityPanel from '@/components/settings/SettingsSecurityPanel.vue'

export interface AdminLlmConfig {
  apiBase: string
  model: string
  apiKey: string
  temperature: number
  maxTokens: number
}

export interface AdminSecurityConfig {
  approvalTimeout: number
  maxRounds: number
}

const props = defineProps<{
  llm: AdminLlmConfig
  security: AdminSecurityConfig
  saving: boolean
  highRiskTools?: number
}>()

const emit = defineEmits<{ save: [] }>()

type PuzzlePhase = 'idle' | 'assembling' | 'locked' | 'success' | 'releasing'

const puzzlePhase = ref<PuzzlePhase>('idle')
let phaseTimer = 0

const gridStyle = computed(() => {
  const locked = ['assembling', 'locked', 'success'].includes(puzzlePhase.value)
  return { '--junction-gap': locked ? '0px' : '22px' }
})

const apiHostShort = computed(() => {
  try {
    const u = new URL(props.llm.apiBase)
    return u.host.length > 18 ? `${u.host.slice(0, 14)}…` : u.host
  } catch {
    const s = props.llm.apiBase || '—'
    return s.length > 18 ? `${s.slice(0, 14)}…` : s || '—'
  }
})

watch(
  () => props.saving,
  (val, prev) => {
    window.clearTimeout(phaseTimer)
    if (val) {
      puzzlePhase.value = 'assembling'
      phaseTimer = window.setTimeout(() => {
        if (props.saving) puzzlePhase.value = 'locked'
      }, 400)
      return
    }
    if (prev) {
      puzzlePhase.value = 'success'
      phaseTimer = window.setTimeout(() => {
        puzzlePhase.value = 'releasing'
        phaseTimer = window.setTimeout(() => {
          puzzlePhase.value = 'idle'
        }, 650)
      }, 900)
    }
  },
)
</script>

<style lang="scss" scoped>
.admin-config-stage {
  position: relative;
  padding: 4px 0 8px;
}

.config-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) var(--junction-gap, 22px) minmax(0, 1fr);
  grid-template-rows: minmax(0, auto);
  transition: grid-template-columns 0.68s cubic-bezier(0.34, 1.08, 0.48, 1);
}

.grid-llm { grid-area: 1 / 1; }
.grid-sec { grid-area: 1 / 3; }

.config-hub-cell {
  grid-area: 1 / 2;
  position: relative;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
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
  width: 320px;
  height: 320px;
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

.radar-sweep,
.radar-sweep-core {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  animation: radar-rotate 6s linear infinite;
}

.radar-sweep {
  background: conic-gradient(
    from -90deg at 50% 50%,
    transparent 0deg,
    rgba(5, 150, 105, 0.04) 12deg,
    rgba(5, 150, 105, 0.14) 28deg,
    rgba(16, 185, 129, 0.2) 34deg,
    transparent 48deg,
    transparent 360deg
  );
}

.radar-sweep-core {
  background: conic-gradient(
    from -90deg at 50% 50%,
    transparent 0deg,
    transparent 30deg,
    rgba(16, 185, 129, 0.22) 31deg,
    rgba(52, 211, 153, 0.4) 32deg,
    transparent 33deg,
    transparent 360deg
  );
  animation-duration: 4s;
}

.assembling .radar-sweep,
.locked .radar-sweep,
.success .radar-sweep {
  animation-duration: 2.5s;
}

@keyframes radar-rotate {
  to { transform: rotate(360deg); }
}

.center-cross {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 100px;
  height: 100px;
  margin: -50px 0 0 -50px;
  pointer-events: none;
  z-index: 5;
  opacity: 0.35;
  transition: opacity 0.5s ease;

  &::before,
  &::after {
    content: '';
    position: absolute;
    background: linear-gradient(90deg, transparent, rgba(5, 150, 105, 0.35), transparent);
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
    background: linear-gradient(0deg, transparent, rgba(5, 150, 105, 0.35), transparent);
  }

  &.assembling,
  &.locked,
  &.success {
    opacity: 0;
  }
}

.llm-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  margin-bottom: 10px;
  border-radius: 8px;
  background: rgba(37, 99, 235, 0.06);
  border: 1px solid rgba(37, 99, 235, 0.14);
}

.overview-left {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.llm-badge {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #2563eb;
  padding: 2px 7px;
  border-radius: 4px;
  background: rgba(37, 99, 235, 0.12);
  width: fit-content;
}

.llm-model {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.model-ring {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 2px solid rgba(37, 99, 235, 0.25);
  background: rgba(255, 255, 255, 0.8);
  flex-shrink: 0;

  .ring-val {
    font-size: 10px;
    font-weight: 800;
    color: #2563eb;
    line-height: 1;
  }

  .ring-label {
    font-size: 6px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: #94a3b8;
    margin-top: 1px;
  }
}

.llm-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
  margin-bottom: 12px;
}

.metric-cell {
  padding: 6px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(37, 99, 235, 0.1);
  text-align: center;

  .m-label {
    display: block;
    font-size: 7px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: #94a3b8;
    margin-bottom: 2px;
  }

  .m-val {
    display: block;
    font-size: 10px;
    font-weight: 700;
    color: #1e293b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.field {
  margin-bottom: 12px;

  label {
    display: block;
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
    margin-bottom: 2px;
    letter-spacing: 0.04em;
  }

  .field-hint {
    display: block;
    font-size: 9px;
    color: #94a3b8;
    margin-bottom: 6px;
    line-height: 1.35;
  }

  :deep(.el-input__wrapper),
  :deep(.el-input-number) {
    width: 100%;
  }
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.mobile-save-row {
  display: none;
  justify-content: center;
  margin-top: 16px;
}

.mobile-save-btn {
  padding: 10px 28px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #059669, #10b981);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(5, 150, 105, 0.3);

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

@media (max-width: 860px) {
  .config-grid {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
  }

  .grid-llm,
  .grid-sec {
    grid-area: auto;
  }

  .config-hub-cell {
    display: none;
  }

  .mobile-save-row {
    display: flex;
  }

  :deep(.puzzle-piece.tl .piece-inner),
  :deep(.puzzle-piece.tr .piece-inner) {
    padding: 18px 20px 16px !important;
  }
}
</style>
