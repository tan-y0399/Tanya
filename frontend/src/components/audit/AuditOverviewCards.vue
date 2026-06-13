<template>
  <div class="audit-overview">
    <div
      v-for="card in cards"
      :key="card.key"
      class="overview-card"
      :class="card.tone"
      :style="{ '--card-accent': cardAccent(card.tone) }"
    >
      <div class="card-glow" aria-hidden="true"></div>
      <AuditIcon :name="card.icon" :tone="card.tone" size="lg" boxed />
      <div class="card-body">
        <span class="card-code">{{ card.key.toUpperCase() }}</span>
        <div class="card-value">{{ card.value }}</div>
        <div class="card-label">{{ card.label }}</div>
        <div v-if="card.hint" class="card-hint">{{ card.hint }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AuditIcon from './AuditIcon.vue'
import { STAT_CARDS, type AuditStats, securityBlockCount } from './auditEventMeta'

const props = defineProps<{
  stats: AuditStats | null
  loading?: boolean
}>()

const cards = computed(() => {
  const s = props.stats
  const values: Record<string, number | string> = {
    total: s?.total ?? '—',
    today: s?.today ?? '—',
    l3: s?.l3Plus ?? '—',
    blocked: s != null ? securityBlockCount(s) : '—',
  }
  return STAT_CARDS.map((c) => ({
    ...c,
    value: values[c.key],
  }))
})

function cardAccent(tone: string): string {
  const map: Record<string, string> = {
    blue: '#2563eb',
    cyan: '#0891b2',
    orange: '#ea580c',
    red: '#dc2626',
  }
  return map[tone] || '#64748b'
}
</script>

<style scoped lang="scss">
.audit-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.overview-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid color-mix(in srgb, var(--card-accent) 18%, #e2e8f0);
  background:
    radial-gradient(ellipse at 100% 0%, color-mix(in srgb, var(--card-accent) 8%, transparent), transparent 60%),
    #fff;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
  overflow: hidden;
  transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;

  &:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--card-accent) 30%, #cbd5e1);
    box-shadow: 0 8px 24px color-mix(in srgb, var(--card-accent) 10%, rgba(15, 23, 42, 0.06));
  }
}

.card-glow {
  position: absolute;
  inset: -30% auto auto -10%;
  width: 80px;
  height: 80px;
  background: radial-gradient(circle, color-mix(in srgb, var(--card-accent) 12%, transparent), transparent 70%);
  pointer-events: none;
}

.card-code {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: var(--card-accent);
  opacity: 0.85;
}

.card-value {
  font-size: 28px;
  font-weight: 700;
  font-family: 'JetBrains Mono', Consolas, monospace;
  line-height: 1.1;
  color: var(--card-accent);
}

.card-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-top: 4px;
}

.card-hint {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

@media (max-width: 1100px) {
  .audit-overview { grid-template-columns: repeat(2, 1fr); }
}
</style>
