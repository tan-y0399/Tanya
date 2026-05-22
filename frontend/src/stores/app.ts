import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', {
  state: () => ({
    sessionId: 'demo-session',
    traceId: 'demo-trace',
  }),
})
