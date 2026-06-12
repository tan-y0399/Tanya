<template>
  <div class="offline-banner glass-panel">
    <div class="banner-accent"></div>
    <div class="banner-body">
      <span class="banner-badge">SIGNAL LOST</span>
      <strong>无法连接目标节点</strong>
      <p>请检查 SSH 服务是否正常，或前往服务器管理配置节点连接</p>
    </div>
    <button type="button" class="tech-btn primary" @click="$router.push('/servers')">前往服务器管理</button>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
const $router = useRouter()
</script>

<style lang="scss" scoped>
.offline-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  margin-bottom: 16px;
  border-color: rgba(251, 191, 36, 0.45) !important;
  background: rgba(255, 251, 235, 0.92) !important;
  position: relative;
  overflow: hidden;
}

.banner-accent {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: linear-gradient(180deg, #f59e0b, #fbbf24);
}

.banner-body {
  flex: 1;
  padding-left: 8px;
  strong { display: block; font-size: 14px; color: #92400e; margin-bottom: 4px; }
  p { margin: 0; font-size: 12px; color: #a16207; line-height: 1.5; }
}

.banner-badge {
  display: inline-block;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #b45309;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(251, 191, 36, 0.2);
  border: 1px solid rgba(251, 191, 36, 0.45);
  margin-bottom: 8px;
}

.tech-btn.primary {
  background: linear-gradient(135deg, #2563eb, #6366f1) !important;
  border: none !important;
  color: #fff !important;
  white-space: nowrap;
}
</style>
