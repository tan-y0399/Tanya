import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref<{ id: string; username: string; role: string } | null>(null)

  function setToken(t: string) {
    token.value = t
    localStorage.setItem('token', t)
  }

  function setUserInfo(info: { id: string; username: string; role: string }) {
    userInfo.value = info
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
  }

  return { token, userInfo, setToken, setUserInfo, logout }
})
