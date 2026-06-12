<template>
  <div class="tech-field" :class="{ required }">
    <div class="field-head">
      <label v-if="label" class="field-label">
        <span v-if="code" class="field-code">{{ code }}</span>
        {{ label }}
        <span v-if="required" class="req">*</span>
      </label>
      <span v-if="tag" class="field-tag">{{ tag }}</span>
    </div>
    <p v-if="hint" class="field-hint">{{ hint }}</p>
    <div class="field-control">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  label?: string
  hint?: string
  code?: string
  tag?: string
  required?: boolean
}>()
</script>

<style lang="scss" scoped>
.tech-field {
  margin-bottom: 14px;

  &:last-child {
    margin-bottom: 0;
  }
}

.field-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.field-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
  color: #334155;
}

.field-code {
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(37, 99, 235, 0.08);
  border: 1px solid rgba(37, 99, 235, 0.12);
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #2563eb;
}

.field-tag {
  padding: 2px 8px;
  border-radius: 999px;
  background: #f1f5f9;
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
}

.req {
  color: #ef4444;
}

.field-hint {
  margin: 0 0 8px;
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.45;
}

.field-control {
  :deep(.el-input__wrapper),
  :deep(.el-textarea__inner) {
    border-radius: 10px;
    box-shadow: 0 0 0 1px #e2e8f0 inset;
    transition: box-shadow 0.15s;
  }

  :deep(.el-input__wrapper.is-focus),
  :deep(.el-textarea__inner:focus) {
    box-shadow: 0 0 0 1px var(--dialog-accent, #2563eb) inset, 0 0 0 3px color-mix(in srgb, var(--dialog-accent, #2563eb) 12%, transparent);
  }

  :deep(.el-select) {
    width: 100%;
  }

  :deep(.el-input-number) {
    width: 100%;
  }
}
</style>
