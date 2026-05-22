import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSystemStore = defineStore('system', () => {
  const config = ref<Record<string, any>>({})
  const healthStatus = ref<Record<string, any>>({})

  function setConfig(c: Record<string, any>) {
    config.value = c
  }

  function setHealthStatus(s: Record<string, any>) {
    healthStatus.value = s
  }

  return { config, healthStatus, setConfig, setHealthStatus }
})
