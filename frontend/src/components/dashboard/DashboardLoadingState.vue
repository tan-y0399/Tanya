<template>
  <div class="dash-loading">
    <div class="scope-dots">
      <span></span><span></span><span></span>
    </div>
    <p class="loading-title">正在建立 SSH 遥测链路…</p>
    <p class="loading-target" v-if="targetLabel">TARGET · {{ targetLabel }}</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{ targetLabel?: string }>()
</script>

<style lang="scss" scoped>
.dash-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 72px 24px;
  gap: 12px;
}

.scope-dots {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  span {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #06b6d4;
    animation: bounce 1.2s ease-in-out infinite;
    &:nth-child(2) { animation-delay: 0.15s; }
    &:nth-child(3) { animation-delay: 0.3s; }
  }
}

.loading-title {
  margin: 0;
  font-size: 14px;
  color: #64748b;
}

.loading-target {
  margin: 0;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
  color: #06b6d4;
  letter-spacing: 0.04em;
  animation: blink 1.5s ease-in-out infinite;
}

@keyframes bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
  40% { transform: translateY(-8px); opacity: 1; }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}
</style>
