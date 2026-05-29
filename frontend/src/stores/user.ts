import { defineStore } from 'pinia'
import { ref } from 'vue'

// 从 localStorage 恢复 userInfo 的辅助函数
function getSavedUserInfo() {
  try {
    const info = localStorage.getItem('userInfo')
    if (info) {
      return JSON.parse(info)
    }
  } catch (e) {
    console.error('Failed to parse saved userInfo:', e)
  }
  return null
}

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref<{ id: string; username: string; role: string } | null>(getSavedUserInfo())

  function setToken(t: string) {
    token.value = t
    localStorage.setItem('token', t)
  }

  function setUserInfo(info: { id: string; username: string; role: string }) {
    userInfo.value = info
    localStorage.setItem('userInfo', JSON.stringify(info))
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
  }

  return { token, userInfo, setToken, setUserInfo, logout }
})
