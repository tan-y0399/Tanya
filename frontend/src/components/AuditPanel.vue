<template>
  <el-card shadow="never">
    <template #header>
      <div class="panel-header">
        <span>审计日志</span>
        <el-tag type="info">{{ items.length }} 条记录</el-tag>
      </div>
    </template>

    <el-timeline>
      <el-timeline-item
        v-for="item in items"
        :key="item.traceId + item.createdAt"
        :timestamp="item.createdAt"
      >
        <strong>{{ item.event }}</strong> - {{ item.detail }}
      </el-timeline-item>
    </el-timeline>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{
  items: Array<{ traceId: string; event: string; detail: string; createdAt: string }>
}>()
</script>
