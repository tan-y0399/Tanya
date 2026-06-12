<template>
  <div class="module-hub" :style="{ '--hub-color': config.color }">
    <div class="hub-head">
      <span class="hub-tag">{{ config.tag }}</span>
      <h3>{{ config.title }}</h3>
      <p>{{ config.desc }}</p>
    </div>
    <div class="hub-grid">
      <div v-for="card in config.cards" :key="card.code" class="hub-card">
        <span class="card-code">{{ card.code }}</span>
        <strong class="card-title">{{ card.label }}</strong>
        <span class="card-desc">{{ card.desc }}</span>
        <div class="card-flow">
          <span
            v-for="(step, i) in card.flow"
            :key="step"
            class="flow-step"
            :class="{ last: i === card.flow.length - 1 }"
          >{{ step }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { TAB_HUB } from './auditTabMeta'

const props = defineProps<{ activeTab: string }>()

const config = computed(() => TAB_HUB[props.activeTab] ?? TAB_HUB[''])
</script>

<style scoped lang="scss">
.module-hub {
  margin-bottom: 20px;
  padding: 18px 20px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background:
    radial-gradient(ellipse at 100% 0%, color-mix(in srgb, var(--hub-color) 8%, transparent), transparent 55%),
    linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
}

.hub-head {
  margin-bottom: 16px;
  h3 {
    margin: 6px 0 4px;
    font-size: 16px;
    font-weight: 700;
    color: #1e293b;
  }
  p {
    margin: 0;
    font-size: 12px;
    color: #64748b;
    line-height: 1.5;
  }
}

.hub-tag {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: var(--hub-color);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid color-mix(in srgb, var(--hub-color) 25%, #e2e8f0);
  background: color-mix(in srgb, var(--hub-color) 8%, #fff);
}

.hub-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.hub-card {
  padding: 14px;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--hub-color) 18%, #e2e8f0);
  background: #fff;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.04);
  transition: border-color 0.15s, box-shadow 0.15s;
  &:hover {
    border-color: color-mix(in srgb, var(--hub-color) 35%, #cbd5e1);
    box-shadow: 0 6px 18px color-mix(in srgb, var(--hub-color) 10%, transparent);
  }
}

.card-code {
  display: inline-block;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: var(--hub-color);
  margin-bottom: 6px;
}

.card-title {
  display: block;
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 4px;
}

.card-desc {
  display: block;
  font-size: 10px;
  color: #64748b;
  line-height: 1.4;
  margin-bottom: 10px;
}

.card-flow {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.flow-step {
  font-size: 9px;
  font-weight: 600;
  color: #475569;
  padding: 2px 6px;
  border-radius: 4px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  position: relative;
  &:not(.last)::after {
    content: '→';
    position: absolute;
    right: -10px;
    color: var(--hub-color);
    opacity: 0.75;
    font-size: 8px;
  }
  &:not(.last) { margin-right: 8px; }
}

@media (max-width: 860px) {
  .hub-grid { grid-template-columns: 1fr; }
}
</style>
