<template>
  <div class="connectivity-block">
    <p v-if="message" class="reach-hint" :class="ok ? 'ok' : 'err'">
      <span class="hint-prefix">{{ ok ? '✓ REACHABLE' : '✕ UNREACHABLE' }}</span>
      {{ message }}
    </p>

    <div class="diag-panel" v-if="suggestions.length && !ok">
      <button type="button" class="diag-toggle" @click="expanded = !expanded">
        <span class="diag-title">排查与修复建议</span>
        <span class="diag-chevron" :class="{ open: expanded }">▾</span>
      </button>
      <ul v-show="expanded">
        <li v-for="(tip, i) in suggestions" :key="i">{{ tip }}</li>
      </ul>
      <p class="diag-note" v-if="showSubnetNote && expanded">
        快速修复：在 VMware/UTM 中将目标 VM 网卡改为 <strong>NAT</strong>，然后使用
        <button type="button" class="link-btn" @click="emit('applySuggestedHost')">{{ suggestedHost }}</button>
        重新添加。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

withDefaults(defineProps<{
  message?: string
  ok?: boolean
  suggestions?: string[]
  showSubnetNote?: boolean
  suggestedHost?: string
}>(), {
  suggestions: () => [],
  suggestedHost: '192.168.64.128',
})

const emit = defineEmits<{ applySuggestedHost: [] }>()
const expanded = ref(true)
</script>

<style lang="scss" scoped>
.reach-hint {
  font-size: 12px;
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  line-height: 1.5;
  &.ok {
    color: #047857;
    background: rgba(16, 185, 129, 0.08);
    border: 1px solid rgba(16, 185, 129, 0.25);
  }
  &.err {
    color: #b91c1c;
    background: rgba(239, 68, 68, 0.06);
    border: 1px solid rgba(239, 68, 68, 0.2);
  }
}

.hint-prefix {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-weight: 700;
  font-size: 10px;
  letter-spacing: 0.04em;
  margin-right: 8px;
}

.diag-panel {
  margin-top: 10px;
  padding: 12px 14px;
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(254, 242, 242, 0.9), rgba(255, 247, 237, 0.9));
  border: 1px solid #fecaca;
  border-left: 3px solid #ef4444;
}

.diag-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
  text-align: left;
}

.diag-title {
  font-size: 12px;
  font-weight: 700;
  color: #b91c1c;
  margin: 0;
}

.diag-chevron {
  color: #b91c1c;
  transition: transform 0.2s;
  &.open { transform: rotate(180deg); }
}

ul {
  margin: 10px 0 0;
  padding-left: 18px;
  font-size: 11px;
  color: #7f1d1d;
  line-height: 1.65;
}

.diag-note {
  margin: 10px 0 0;
  font-size: 11px;
  color: #92400e;
  line-height: 1.5;
  strong { color: #b45309; }
}

.link-btn {
  margin-left: 4px;
  padding: 0;
  border: none;
  background: none;
  color: #2563eb;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  text-decoration: underline;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
</style>
