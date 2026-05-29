<template>
  <div class="state-cards" :style="{ borderLeftColor: riskColor }">
    <div class="cards-container">
      <div v-for="(card, index) in cards" :key="index" class="state-card" :class="card.status">
        <div class="card-icon">
          {{ getStatusIcon(card.status) }}
        </div>
        <div class="card-content">
          <div class="card-title">{{ card.title }}</div>
          <div class="card-value">{{ card.content }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface StateCard {
  title: string
  content: string
  status: 'success' | 'warning' | 'error' | 'info'
}

interface Props {
  cards: StateCard[]
  riskColor?: string
}

withDefaults(defineProps<Props>(), {
  riskColor: '#3b82f6',
})

const getStatusIcon = (status: string) => {
  const icons: Record<string, string> = {
    success: 'OK',
    warning: '!!',
    error: 'XX',
    info: '--',
  }
  return icons[status] || icons.info
}
</script>

<style scoped>
.state-cards {
  margin: 12px 0;
  border-left: 3px solid #3b82f6;
  padding-left: 12px;
}

.cards-container {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.state-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.state-card.success {
  border-color: #10b981;
  background: #ecfdf5;
}

.state-card.warning {
  border-color: #f59e0b;
  background: #fffbeb;
}

.state-card.error {
  border-color: #ef4444;
  background: #fef2f2;
}

.state-card.info {
  border-color: #3b82f6;
  background: #eff6ff;
}

.card-icon {
  font-size: 14px;
  font-weight: 700;
  width: 24px;
  text-align: center;
}

.card-content .card-title {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 2px;
}

.card-content .card-value {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}
</style>
