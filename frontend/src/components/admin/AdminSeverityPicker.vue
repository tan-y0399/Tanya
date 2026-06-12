<template>
  <AdminTechCardPicker
    :model-value="modelValue"
    :options="options"
    :columns="3"
    :aria-label="ariaLabel"
    @update:model-value="emit('update:modelValue', $event as ArticleSeverity)"
  />
</template>

<script setup lang="ts">
import AdminTechCardPicker from './AdminTechCardPicker.vue'
import type { TechCardOption } from './AdminTechCardPicker.vue'

export type ArticleSeverity = 'info' | 'warning' | 'critical'

defineProps<{
  modelValue: ArticleSeverity
  ariaLabel?: string
}>()

const emit = defineEmits<{ 'update:modelValue': [ArticleSeverity] }>()

const options: TechCardOption[] = [
  { value: 'info', code: 'INFO', label: '一般', desc: '常规运维知识', tone: 'info', icon: 'info' },
  { value: 'warning', code: 'WARN', label: '警告', desc: '需关注的异常场景', tone: 'warning', icon: 'warning' },
  { value: 'critical', code: 'CRIT', label: '严重', desc: '紧急故障与高危', tone: 'critical', icon: 'critical' },
]
</script>
