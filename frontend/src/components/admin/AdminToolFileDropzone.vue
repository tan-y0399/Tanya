<template>
  <div class="tool-file-zone" :class="{ dragging, passed, failed: failed && !validating }">
    <input
      ref="fileInputRef"
      type="file"
      class="file-input"
      accept=".py,.json"
      @change="onFileInput"
    />

    <div
      class="drop-area"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
      @click="fileInputRef?.click()"
    >
      <div class="drop-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M12 16V4m0 0l-4 4m4-4l4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M4 17v1a3 3 0 003 3h10a3 3 0 003-3v-1" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </div>
      <p class="drop-title">拖拽工具文件到此处，或点击选择</p>
      <p class="drop-hint">支持 <code>.py</code> / <code>.json</code> · 自动诊断代码并试运行</p>
      <p v-if="filename" class="drop-file">
        <span class="file-badge">FILE</span>{{ filename }}
        <button type="button" class="clear-btn" @click.stop="clearFile">清除</button>
      </p>
    </div>

    <div v-if="validating || steps.length" class="validate-flow">
      <div
        v-for="step in steps"
        :key="step.key"
        class="flow-step"
        :class="step.status"
      >
        <span class="step-dot" />
        <div class="step-body">
          <span class="step-label">{{ step.label }}</span>
          <span class="step-msg">{{ step.message }}</span>
          <ul v-if="step.details?.length" class="step-details">
            <li v-for="(d, i) in step.details" :key="i">{{ d }}</li>
          </ul>
        </div>
      </div>
      <div v-if="validating" class="flow-loading">校验中…</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { validateToolFile, type ToolFileValidation } from '@/api/tools'

const props = defineProps<{ resetKey?: number }>()

const emit = defineEmits<{
  validated: [ToolFileValidation]
  cleared: []
}>()

const fileInputRef = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const validating = ref(false)
const filename = ref('')
const passed = ref(false)
const failed = ref(false)
const steps = ref<Array<{ key: string; label: string; message: string; status: string; details?: string[] }>>([])

watch(() => props.resetKey, () => clearFile())

const hasFile = computed(() => !!filename.value)

async function processFile(file: File) {
  if (!file.name.match(/\.(py|json)$/i)) {
    steps.value = [{
      key: 'diagnose',
      label: '代码诊断',
      message: '仅支持 .py 或 .json 文件',
      status: 'error',
    }]
    failed.value = true
    passed.value = false
    return
  }

  filename.value = file.name
  validating.value = true
  failed.value = false
  passed.value = false
  steps.value = [
    { key: 'diagnose', label: '代码诊断', message: '正在分析文件结构与语法…', status: 'running' },
    { key: 'trial', label: '试运行', message: '等待诊断完成', status: 'pending' },
  ]

  try {
    const text = await file.text()
    const result = await validateToolFile(file.name, text)
    applyResult(result)
    if (result.ok) {
      emit('validated', result)
    }
  } catch (e: any) {
    const status = e?.response?.status
    let msg = e?.response?.data?.detail || e?.message || '校验请求失败'
    if (status === 405) {
      msg = '接口 Method Not Allowed：后端未加载 /tools/validate-file，请重启 KylinOps 后端服务后重试'
    } else if (status === 401 || status === 403) {
      msg = '无权限执行校验，请使用管理员账号登录'
    }
    steps.value = [{
      key: 'diagnose',
      label: '代码诊断',
      message: msg,
      status: 'error',
    }]
    failed.value = true
    passed.value = false
  } finally {
    validating.value = false
  }
}

function applyResult(result: ToolFileValidation) {
  const diag = result.diagnose || { ok: false, messages: [], errors: [] }
  const trial = result.trial || { ok: false, error: '' }

  if (!diag.ok) {
    steps.value = [
      {
        key: 'diagnose',
        label: '代码诊断',
        message: diag.errors?.[0] || '诊断未通过',
        status: 'error',
        details: diag.errors?.slice(1),
      },
      { key: 'trial', label: '试运行', message: '已跳过', status: 'skipped' },
    ]
    failed.value = true
    passed.value = false
    return
  }

  const diagnoseStep = {
    key: 'diagnose',
    label: '代码诊断',
    message: '诊断通过',
    status: 'ok',
    details: diag.messages,
  }

  if (!trial.ok) {
    steps.value = [
      diagnoseStep,
      {
        key: 'trial',
        label: '试运行',
        message: trial.error || '试运行失败',
        status: 'error',
      },
    ]
    failed.value = true
    passed.value = false
    return
  }

  steps.value = [
    diagnoseStep,
    {
      key: 'trial',
      label: '试运行',
      message: 'run() 执行成功，可以添加',
      status: 'ok',
    },
  ]
  passed.value = true
  failed.value = false
}

function onDrop(e: DragEvent) {
  dragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) processFile(file)
}

function onFileInput(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) processFile(file)
}

function clearFile() {
  filename.value = ''
  steps.value = []
  passed.value = false
  failed.value = false
  validating.value = false
  if (fileInputRef.value) fileInputRef.value.value = ''
  emit('cleared')
}

defineExpose({ clearFile, hasFile, passed })
</script>

<style lang="scss" scoped>
.tool-file-zone {
  margin-bottom: 16px;
  border-radius: 14px;
  border: 1px dashed rgba(124, 58, 237, 0.35);
  background: linear-gradient(180deg, rgba(245, 243, 255, 0.9), rgba(255, 255, 255, 0.6));
  transition: border-color 0.2s, box-shadow 0.2s;

  &.dragging {
    border-color: #7c3aed;
    box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.12);
  }

  &.passed {
    border-color: rgba(16, 185, 129, 0.5);
    background: linear-gradient(180deg, rgba(236, 253, 245, 0.9), rgba(255, 255, 255, 0.7));
  }

  &.failed {
    border-color: rgba(239, 68, 68, 0.45);
    background: linear-gradient(180deg, rgba(254, 242, 242, 0.85), rgba(255, 255, 255, 0.7));
  }
}

.file-input {
  display: none;
}

.drop-area {
  padding: 18px 16px;
  text-align: center;
  cursor: pointer;
}

.drop-icon {
  width: 40px;
  height: 40px;
  margin: 0 auto 10px;
  border-radius: 12px;
  background: rgba(124, 58, 237, 0.12);
  color: #7c3aed;
  display: flex;
  align-items: center;
  justify-content: center;

  svg { width: 22px; height: 22px; }
}

.drop-title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
}

.drop-hint {
  margin: 0;
  font-size: 12px;
  color: #64748b;

  code {
    padding: 1px 5px;
    border-radius: 4px;
    background: rgba(124, 58, 237, 0.08);
    color: #6d28d9;
    font-size: 11px;
  }
}

.drop-file {
  margin: 12px 0 0;
  font-size: 12px;
  color: #475569;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.file-badge {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  padding: 2px 6px;
  border-radius: 4px;
  background: #ede9fe;
  color: #6d28d9;
}

.clear-btn {
  border: none;
  background: none;
  color: #94a3b8;
  font-size: 12px;
  cursor: pointer;
  &:hover { color: #ef4444; }
}

.validate-flow {
  padding: 0 14px 14px;
  border-top: 1px solid rgba(226, 232, 240, 0.7);
}

.flow-step {
  display: flex;
  gap: 10px;
  padding: 10px 0;

  &:not(:last-child) {
    border-bottom: 1px dashed rgba(226, 232, 240, 0.8);
  }

  &.ok .step-dot { background: #10b981; box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2); }
  &.error .step-dot { background: #ef4444; box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15); }
  &.running .step-dot { background: #7c3aed; animation: pulse 1s ease infinite; }
  &.pending .step-dot { background: #cbd5e1; }
  &.skipped .step-dot { background: #e2e8f0; }
}

.step-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-top: 4px;
  flex-shrink: 0;
}

.step-label {
  display: block;
  font-size: 12px;
  font-weight: 700;
  color: #334155;
}

.step-msg {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.step-details {
  margin: 6px 0 0;
  padding-left: 16px;
  font-size: 11px;
  color: #94a3b8;
  li { margin: 2px 0; }
}

.flow-loading {
  font-size: 12px;
  color: #7c3aed;
  padding-top: 6px;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}
</style>
