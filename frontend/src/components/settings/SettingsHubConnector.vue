<template>
  <button
    type="button"
    class="hub-connector"
    :class="[phase, { disabled: disabled || phase === 'assembling' }]"
    :disabled="disabled || phase === 'assembling'"
    @click="emit('save')"
  >
    <span class="hub-ring" aria-hidden="true"></span>
    <span class="hub-ring ring-2" aria-hidden="true"></span>

    <span v-if="phase === 'success'" class="hub-content success">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="#10b981" stroke-width="1.5" />
        <path d="M8 12l3 3 5-6" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <span class="hub-text">保存成功</span>
    </span>

    <span v-else-if="phase === 'assembling'" class="hub-content loading">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" class="spin">
        <circle cx="12" cy="12" r="9" stroke="#2563eb" stroke-width="2" stroke-opacity="0.2" />
        <path d="M12 3a9 9 0 019 9" stroke="#2563eb" stroke-width="2" stroke-linecap="round" />
      </svg>
      <span class="hub-text">拼接中</span>
    </span>

    <span v-else class="hub-content idle">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path d="M12 3v6M12 15v6M3 12h6M15 12h6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
        <circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="1.6" />
      </svg>
      <span class="hub-text">保存配置</span>
    </span>
  </button>
</template>

<script setup lang="ts">
defineProps<{
  phase: 'idle' | 'assembling' | 'locked' | 'success' | 'releasing'
  disabled?: boolean
}>()

const emit = defineEmits<{ save: [] }>()
</script>

<style lang="scss" scoped>
.hub-connector {
  position: relative;
  z-index: 10;
  flex-shrink: 0;
  width: 88px;
  height: 88px;
  border: none;
  border-radius: 50%;
  background:
    radial-gradient(circle at 35% 30%, #ffffff, #f1f5f9 70%);
  box-shadow:
    0 0 0 4px rgba(255, 255, 255, 0.95),
    0 0 0 5px rgba(37, 99, 235, 0.15),
    0 8px 28px rgba(37, 99, 235, 0.18);
  cursor: pointer;
  transition: transform 0.3s ease, box-shadow 0.35s ease;
  overflow: visible;

  &:hover:not(:disabled) {
    transform: scale(1.06);
    box-shadow:
      0 0 0 4px rgba(255, 255, 255, 0.95),
      0 0 0 6px rgba(37, 99, 235, 0.25),
      0 12px 32px rgba(37, 99, 235, 0.22);
  }

  &:active:not(:disabled) {
    transform: scale(0.96);
  }

  &.assembling {
    box-shadow:
      0 0 0 4px rgba(255, 255, 255, 0.95),
      0 0 0 6px rgba(37, 99, 235, 0.35),
      0 0 24px rgba(37, 99, 235, 0.3);
  }

  &.success {
    box-shadow:
      0 0 0 4px rgba(255, 255, 255, 0.95),
      0 0 0 6px rgba(16, 185, 129, 0.35),
      0 0 28px rgba(16, 185, 129, 0.25);
  }

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}

.hub-ring {
  position: absolute;
  inset: -6px;
  border-radius: 50%;
  border: 1px dashed rgba(37, 99, 235, 0.25);
  animation: hub-spin 12s linear infinite;
  pointer-events: none;

  &.ring-2 {
    inset: -12px;
    border-style: dotted;
    opacity: 0.45;
    animation-direction: reverse;
    animation-duration: 18s;
  }
}

.assembling .hub-ring {
  animation-duration: 2s;
  border-color: rgba(37, 99, 235, 0.5);
}

.success .hub-ring {
  border-color: rgba(16, 185, 129, 0.45);
  animation: none;
}

@keyframes hub-spin {
  to { transform: rotate(360deg); }
}

.hub-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: #2563eb;
  height: 100%;
}

.hub-content.success { color: #059669; }
.hub-content.loading { color: #2563eb; }

.hub-text {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  line-height: 1.2;
  max-width: 72px;
  text-align: center;
}

.spin {
  animation: spin 0.75s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
