<template>
  <div class="risk-notice" role="alert">
    <span class="risk-icon" aria-hidden="true">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 9v4M12 17h.01"/>
        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
      </svg>
    </span>
    <p class="risk-text">{{ message }}</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{ message: string }>()
</script>

<style scoped lang="scss">
.risk-notice {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 11px 14px;
  border-radius: 10px;
  background: linear-gradient(90deg, #fffbeb 0%, #fff 100%);
  border: 1px solid #fcd34d;
  box-shadow: 0 1px 4px rgba(245, 158, 11, 0.12);
}
.risk-icon {
  flex-shrink: 0;
  color: #d97706;
  margin-top: 1px;
}
.risk-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #92400e;
  font-weight: 500;
}
</style>
