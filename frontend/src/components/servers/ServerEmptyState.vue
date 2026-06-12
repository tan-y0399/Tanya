<template>
  <div class="server-empty-state">
    <div class="empty-visual">
      <svg width="120" height="80" viewBox="0 0 120 80" fill="none" aria-hidden="true">
        <circle cx="60" cy="40" r="14" stroke="#93c5fd" stroke-width="1.5" stroke-dasharray="4 3"/>
        <circle cx="24" cy="24" r="10" stroke="#bfdbfe" stroke-width="1.2"/>
        <circle cx="96" cy="24" r="10" stroke="#bfdbfe" stroke-width="1.2"/>
        <circle cx="24" cy="56" r="10" stroke="#bfdbfe" stroke-width="1.2"/>
        <circle cx="96" cy="56" r="10" stroke="#bfdbfe" stroke-width="1.2"/>
        <line x1="34" y1="28" x2="48" y2="34" stroke="#dbeafe" stroke-width="1"/>
        <line x1="86" y1="28" x2="72" y2="34" stroke="#dbeafe" stroke-width="1"/>
        <line x1="34" y1="52" x2="48" y2="46" stroke="#dbeafe" stroke-width="1"/>
        <line x1="86" y1="52" x2="72" y2="46" stroke="#dbeafe" stroke-width="1"/>
        <circle cx="60" cy="40" r="5" fill="#2563eb" opacity="0.6"/>
      </svg>
      <div class="ripple-ring"></div>
    </div>
    <h3 class="empty-title">尚未接入任何节点</h3>
    <p class="empty-desc">添加第一台服务器，自动完成 SSH 免密配置与运维用户部署</p>
    <button type="button" class="tech-btn primary empty-cta" @click="emit('add')">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
      添加服务器
    </button>
  </div>
</template>

<script setup lang="ts">
const emit = defineEmits<{ add: [] }>()
</script>

<style lang="scss" scoped>
.server-empty-state {
  text-align: center;
  padding: 72px 24px 80px;
}

.empty-visual {
  position: relative;
  display: inline-flex;
  margin-bottom: 24px;
}

.ripple-ring {
  position: absolute;
  inset: -20px;
  border-radius: 50%;
  border: 1px solid rgba(147, 197, 253, 0.4);
  animation: ripple-expand 3s ease-out infinite;
}

.empty-title {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 8px;
}

.empty-desc {
  font-size: 14px;
  color: #94a3b8;
  margin: 0 0 24px;
  max-width: 360px;
  margin-left: auto;
  margin-right: auto;
  line-height: 1.6;
}

.empty-cta {
  background: linear-gradient(135deg, #2563eb, #6366f1) !important;
  border: none !important;
  color: #fff !important;
  box-shadow: 0 4px 16px rgba(37, 99, 235, 0.35);
  font-weight: 600;
  &:hover { transform: translateY(-1px); box-shadow: 0 6px 22px rgba(37, 99, 235, 0.45); }
}

@keyframes ripple-expand {
  0% { transform: scale(0.85); opacity: 0.6; }
  100% { transform: scale(1.15); opacity: 0; }
}
</style>
