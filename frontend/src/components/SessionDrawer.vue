<template>
  <el-drawer v-model="visible" title="会话列表" size="320px">
    <div class="drawer-actions">
      <el-input v-model="keyword" placeholder="搜索会话" clearable />
      <el-button type="primary" @click="handleCreate">新建会话</el-button>
    </div>

    <el-menu :default-active="activeSessionId" @select="handleSelect">
      <el-menu-item v-for="item in filteredSessions" :key="item.sessionId" :index="item.sessionId">
        <div class="session-title">{{ item.title }}</div>
        <div class="session-time">{{ item.updatedAt }}</div>
      </el-menu-item>
    </el-menu>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { SessionItem } from '../api/session'

const props = defineProps<{
  modelValue: boolean
  sessions: SessionItem[]
  activeSessionId: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  select: [sessionId: string]
  create: []
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const keyword = ref('')

const filteredSessions = computed(() =>
  props.sessions.filter((item) => item.title.includes(keyword.value) || item.sessionId.includes(keyword.value)),
)

const handleSelect = (sessionId: string) => {
  emit('select', sessionId)
  emit('update:modelValue', false)
}

const handleCreate = () => {
  emit('create')
}
</script>
