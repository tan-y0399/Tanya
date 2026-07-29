<template>
  <div class="audit-filter card" :class="{ 'is-searching': searching }">
    <div class="search-progress" :class="{ active: searching }">
      <div class="search-progress-bar"></div>
    </div>

    <div class="module-tabs">
      <button
        v-for="tab in MODULE_TABS"
        :key="tab.key"
        class="module-tab"
        :class="{ active: activeTab === tab.key, loading: searching && activeTab === tab.key }"
        :disabled="searching"
        @click="$emit('tab-change', tab.key)"
      >
        <span class="tab-icon">
          <AuditIcon
            :name="tab.icon"
            :tone="activeTab === tab.key ? 'blue' : 'muted'"
            size="sm"
          />
        </span>
        <span>{{ tab.label }}</span>
        <span v-if="tabStat(tab)" class="tab-badge">{{ tabStat(tab) }}</span>
      </button>
    </div>

    <div class="filter-panel" :class="{ focused: panelFocused }">
      <div class="filter-row">
        <div class="filter-field wide" @focusin="panelFocused = true" @focusout="onPanelFocusOut">
          <span class="field-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="1.6" />
              <path d="M16 16l4.5 4.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
          </span>
          <el-input
            v-model="localKeyword"
            placeholder="关键词 / TraceId"
            class="filter-control tech-input"
            clearable
            :disabled="searching"
            @keyup.enter="emitSearch"
            @clear="onFieldClear"
          />
        </div>

        <div class="filter-field">
          <span class="field-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="8" r="3.2" stroke="currentColor" stroke-width="1.6" />
              <path d="M6.5 19c.9-2.8 2.9-4.2 5.5-4.2s4.6 1.4 5.5 4.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
          </span>
          <el-input
            v-model="localUsername"
            placeholder="用户名"
            class="filter-control tech-input"
            clearable
            :disabled="searching"
            @keyup.enter="emitSearch"
          />
        </div>

        <div class="filter-field">
          <span class="field-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 4.5 17.5 7v5c0 3.1-2.4 5.9-5.5 6.8-3.1-.9-5.5-3.7-5.5-6.8V7L12 4.5Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
            </svg>
          </span>
          <el-select
            v-model="localRisk"
            placeholder="风险等级"
            class="filter-control tech-select"
            clearable
            :disabled="searching"
          >
            <el-option label="全部" value="" />
            <el-option label="L1 只读" value="L1" />
            <el-option label="L2 可逆" value="L2" />
            <el-option label="L3 不可逆" value="L3" />
            <el-option label="L4 关键变更" value="L4" />
            <el-option label="L5 禁止" value="L5" />
          </el-select>
        </div>

        <div class="filter-field date">
          <span class="field-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <rect x="4.5" y="6" width="15" height="13" rx="2" stroke="currentColor" stroke-width="1.6" />
              <path d="M4.5 10.5h15M9 4.5v3M15 4.5v3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
          </span>
          <el-date-picker
            v-model="localDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            class="filter-control tech-date"
            :disabled="searching"
          />
        </div>

        <div class="filter-actions">
          <button
            class="search-btn tech-btn primary"
            :class="{ loading: searching }"
            :disabled="searching"
            @click="emitSearch"
          >
            <span v-if="searching" class="btn-spinner" aria-hidden="true"></span>
            <svg v-else width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <circle cx="6" cy="6" r="4.5" stroke="currentColor" stroke-width="1.5" />
              <path d="M9.5 9.5L13 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            </svg>
            <span>{{ searching ? '查询中…' : '搜索' }}</span>
          </button>
          <button
            v-if="hasActiveFilters"
            class="reset-btn tech-btn"
            :disabled="searching"
            @click="resetFilters"
          >
            重置
          </button>
        </div>
      </div>

      <div v-if="activeFilterTags.length" class="active-tags">
        <span class="tags-label">已选条件</span>
        <span v-for="tag in activeFilterTags" :key="tag.key" class="filter-tag">
          {{ tag.label }}
          <button type="button" class="tag-close" :disabled="searching" @click="clearTag(tag.key)">×</button>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import AuditIcon from './AuditIcon.vue'
import { MODULE_TABS, type AuditStats } from './auditEventMeta'

type ModuleTab = {
  key: string
  label: string
  icon: string
  statKey?: string
}

const props = defineProps<{
  activeTab: string
  keyword: string
  username: string
  riskLevel: string
  dateRange: [Date, Date] | null
  stats: AuditStats | null
  searching?: boolean
}>()

const emit = defineEmits<{
  search: []
  'tab-change': [key: string]
  'update:keyword': [v: string]
  'update:username': [v: string]
  'update:riskLevel': [v: string]
  'update:dateRange': [v: [Date, Date] | null]
}>()

const localKeyword = ref(props.keyword)
const localUsername = ref(props.username)
const localRisk = ref(props.riskLevel)
const localDateRange = ref<[Date, Date] | null>(props.dateRange)
const panelFocused = ref(false)

watch(() => props.keyword, (v) => { localKeyword.value = v })
watch(() => props.username, (v) => { localUsername.value = v })
watch(() => props.riskLevel, (v) => { localRisk.value = v })
watch(() => props.dateRange, (v) => { localDateRange.value = v })

const hasActiveFilters = computed(() =>
  !!localKeyword.value
  || !!localUsername.value
  || !!localRisk.value
  || !!localDateRange.value?.length,
)

const activeFilterTags = computed(() => {
  const tags: Array<{ key: string; label: string }> = []
  if (localKeyword.value) tags.push({ key: 'keyword', label: `关键词: ${localKeyword.value}` })
  if (localUsername.value) tags.push({ key: 'username', label: `用户: ${localUsername.value}` })
  if (localRisk.value) tags.push({ key: 'riskLevel', label: `风险: ${localRisk.value}` })
  if (localDateRange.value?.length === 2) {
    const [start, end] = localDateRange.value
    tags.push({
      key: 'dateRange',
      label: `时间: ${start.toLocaleDateString()} - ${end.toLocaleDateString()}`,
    })
  }
  return tags
})

function tabStat(tab: ModuleTab) {
  if (!props.stats) return 0
  if (tab.key === '') return props.stats.total
  const key = tab.statKey || tab.key
  if (key === 'blocked_injection') return props.stats.byEventType?.blocked_injection ?? 0
  return props.stats.byEventType?.[key] ?? 0
}

function onPanelFocusOut(e: FocusEvent) {
  const current = e.currentTarget as HTMLElement | null
  if (current && !current.contains(e.relatedTarget as Node)) {
    panelFocused.value = false
  }
}

function emitSearch() {
  if (props.searching) return
  emit('update:keyword', localKeyword.value)
  emit('update:username', localUsername.value)
  emit('update:riskLevel', localRisk.value)
  emit('update:dateRange', localDateRange.value)
  emit('search')
}

function resetFilters() {
  if (props.searching) return
  localKeyword.value = ''
  localUsername.value = ''
  localRisk.value = ''
  localDateRange.value = null
  emit('update:keyword', '')
  emit('update:username', '')
  emit('update:riskLevel', '')
  emit('update:dateRange', null)
  emit('search')
}

function clearTag(key: string) {
  if (props.searching) return
  if (key === 'keyword') localKeyword.value = ''
  if (key === 'username') localUsername.value = ''
  if (key === 'riskLevel') localRisk.value = ''
  if (key === 'dateRange') localDateRange.value = null
  emitSearch()
}

function onFieldClear() {
  if (!localKeyword.value && !props.searching) emitSearch()
}
</script>

<style scoped lang="scss">
.audit-filter {
  position: relative;
  padding: 16px;
  margin-bottom: 16px;
  overflow: hidden;
  transition: box-shadow 0.2s ease;

  &.is-searching {
    box-shadow: 0 8px 28px rgba(37, 99, 235, 0.08);
  }
}

.search-progress {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: #e2e8f0;
  opacity: 0;
  transition: opacity 0.2s ease;
  pointer-events: none;

  &.active {
    opacity: 1;
  }
}

.search-progress-bar {
  height: 100%;
  width: 35%;
  background: linear-gradient(90deg, #2563eb, #60a5fa, #2563eb);
  background-size: 200% 100%;
  border-radius: 0 2px 2px 0;
  animation: progress-slide 1.1s ease-in-out infinite;
}

@keyframes progress-slide {
  0% { transform: translateX(-120%); background-position: 0% 50%; }
  100% { transform: translateX(320%); background-position: 100% 50%; }
}

.module-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
  padding-bottom: 14px;
  border-bottom: 1px solid #f1f5f9;
}

.tab-icon {
  display: inline-flex;
  align-items: center;
}

.module-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.18s ease;
  user-select: none;

  &:hover:not(:disabled) {
    border-color: #cbd5e1;
    color: #334155;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
  }

  &:active:not(:disabled) {
    transform: translateY(0) scale(0.98);
  }

  &.active {
    background: linear-gradient(135deg, #eff6ff, #eef2ff);
    border-color: #93c5fd;
    color: #1d4ed8;
    font-weight: 600;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.12);
  }

  &.loading {
    position: relative;
    &::after {
      content: '';
      position: absolute;
      inset: -1px;
      border-radius: inherit;
      border: 1px solid rgba(37, 99, 235, 0.35);
      animation: tab-pulse 1.2s ease-in-out infinite;
    }
  }

  &:disabled {
    opacity: 0.72;
    cursor: not-allowed;
  }
}

@keyframes tab-pulse {
  0%, 100% { opacity: 0.35; }
  50% { opacity: 1; }
}

.tab-badge {
  min-width: 18px;
  padding: 0 6px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.12);
  color: #2563eb;
  font-size: 11px;
  font-weight: 700;
}

.filter-panel {
  padding: 12px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;

  &.focused {
    background: #fff;
    border-color: #bfdbfe;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08);
  }
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: stretch;
}

.filter-field {
  position: relative;
  display: flex;
  align-items: center;
  width: 150px;
  min-height: 40px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e2e8f0;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.15s ease;

  &:hover {
    border-color: #cbd5e1;
  }

  &:focus-within {
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    transform: translateY(-1px);
  }

  &.wide {
    width: 220px;
    flex: 1;
    min-width: 200px;
  }

  &.date {
    width: 280px;
  }
}

.field-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  flex-shrink: 0;
  color: #94a3b8;
  transition: color 0.2s ease;
}

.filter-field:focus-within .field-icon {
  color: #2563eb;
}

.filter-control {
  flex: 1;
  min-width: 0;
}

.filter-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.search-btn {
  min-width: 108px;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(120deg, transparent 30%, rgba(255, 255, 255, 0.22) 50%, transparent 70%);
    transform: translateX(-120%);
    transition: transform 0.45s ease;
  }

  &:hover:not(:disabled)::before {
    transform: translateX(120%);
  }

  &.loading {
    background: #3b82f6;
    cursor: wait;
    box-shadow: 0 2px 10px rgba(37, 99, 235, 0.28);
  }

  &:disabled {
    opacity: 0.88;
    cursor: not-allowed;
  }
}

.reset-btn {
  min-width: 64px;
}

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.active-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #e2e8f0;
}

.tags-label {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 600;
}

.filter-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px 4px 10px;
  border-radius: 999px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  font-size: 12px;
}

.tag-close {
  border: none;
  background: transparent;
  color: #60a5fa;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  padding: 0 2px;
  border-radius: 4px;
  transition: color 0.15s ease, background 0.15s ease;

  &:hover:not(:disabled) {
    color: #1d4ed8;
    background: rgba(37, 99, 235, 0.1);
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }
}

:deep(.filter-control.tech-input .el-input__wrapper) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding-left: 0 !important;
}

:deep(.filter-control.tech-select .el-select__wrapper) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding-left: 0 !important;
  min-height: 38px;
}

:deep(.filter-control.tech-date.el-date-editor) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  width: 100% !important;
  padding-left: 0 !important;
}

:deep(.filter-field .el-input.is-disabled .el-input__wrapper),
:deep(.filter-field .el-select__wrapper.is-disabled),
:deep(.filter-field .el-date-editor.is-disabled) {
  opacity: 0.65;
}
</style>
