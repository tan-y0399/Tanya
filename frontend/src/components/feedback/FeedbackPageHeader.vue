<template>
  <header class="fb-header">
    <div class="header-main">
      <div class="title-bar">
        <span class="title-accent"></span>
        <div>
          <div class="mod-tag">MOD-FB · 反馈中心</div>
          <h2 class="page-title">反馈中心</h2>
          <p class="page-sub">[ SESSION · EVAL · MANUAL ]</p>
        </div>
      </div>
      <p class="page-desc">会话反馈、会话评价与手动反馈统一管理，与管理员高效沟通</p>
    </div>
    <button type="button" class="submit-btn" @click="emit('create')">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M8 2v12M2 8h12" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
      </svg>
      提交反馈
    </button>
  </header>
</template>

<script setup lang="ts">
const emit = defineEmits<{ create: [] }>()
</script>

<style lang="scss" scoped>
.fb-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.title-bar {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.title-accent {
  width: 4px;
  height: 52px;
  border-radius: 2px;
  background: linear-gradient(180deg, #7c3aed, #2563eb);
  flex-shrink: 0;
}

.mod-tag {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #7c3aed;
  margin-bottom: 4px;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
}

.page-sub {
  margin: 4px 0 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #94a3b8;
}

.page-desc {
  margin: 8px 0 0;
  font-size: 13px;
  color: #64748b;
}

.submit-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 4px 18px rgba(124, 58, 237, 0.28);
  transition: transform 0.15s, box-shadow 0.2s;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 22px rgba(124, 58, 237, 0.35);
  }
}
</style>
