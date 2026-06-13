import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getPendingApprovals, getApprovalStats } from '@/api/approval'

export const useApprovalStore = defineStore('approval', () => {
  const pendingTotal = ref(0)
  const pendingItems = ref<any[]>([])
  const stats = ref<Record<string, number>>({})
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let pollRefs = 0

  async function refreshPending() {
    try {
      const data = await getPendingApprovals()
      pendingItems.value = data.items || []
      pendingTotal.value = data.total || 0
    } catch {
      /* 保留上次结果，避免闪烁 */
    }
  }

  async function refreshStats() {
    try {
      stats.value = await getApprovalStats()
    } catch {
      stats.value = {}
    }
  }

  async function refreshAll() {
    await Promise.all([refreshPending(), refreshStats()])
  }

  /** 侧边栏 / 审批页共用轮询；多组件挂载时引用计数 */
  function startPolling(intervalMs = 5000) {
    pollRefs += 1
    if (pollTimer) return
    void refreshAll()
    pollTimer = setInterval(() => {
      void refreshAll()
    }, intervalMs)
  }

  function stopPolling() {
    pollRefs = Math.max(0, pollRefs - 1)
    if (pollRefs > 0 || !pollTimer) return
    clearInterval(pollTimer)
    pollTimer = null
  }

  return {
    pendingTotal,
    pendingItems,
    stats,
    refreshPending,
    refreshStats,
    refreshAll,
    startPolling,
    stopPolling,
  }
})
