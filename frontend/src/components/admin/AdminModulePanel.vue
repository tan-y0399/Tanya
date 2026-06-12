<template>
  <div class="module-panel">
    <p v-if="description" class="module-desc" v-html="description" />

    <ul v-if="features.length" class="module-features">
      <li v-for="(item, index) in features" :key="index">
        <strong>{{ item.label }}</strong>
        <span> — {{ item.text }}</span>
      </li>
    </ul>

    <div class="module-body">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
export interface ModuleFeature {
  label: string
  text: string
}

withDefaults(
  defineProps<{
    description?: string
    features?: ModuleFeature[]
  }>(),
  { features: () => [] },
)
</script>

<style lang="scss" scoped>
.module-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.module-desc {
  margin: 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.65;

  :deep(code) {
    padding: 1px 6px;
    border-radius: 4px;
    background: #f1f5f9;
    font-size: 12px;
    color: #475569;
  }

  :deep(strong) {
    color: #475569;
    font-weight: 700;
  }
}

.module-features {
  margin: 0;
  padding: 12px 14px 12px 30px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  font-size: 12px;
  color: #64748b;
  line-height: 1.7;

  li + li {
    margin-top: 2px;
  }

  strong {
    color: #334155;
    font-weight: 700;
  }
}

.module-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
</style>
