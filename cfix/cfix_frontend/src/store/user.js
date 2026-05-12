import { defineStore } from 'pinia'
import { getMe } from '@/api/auth'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    username: localStorage.getItem('username') || '',
    role: '',
    status: 1
  }),
  getters: {
    isLogin: state => !!state.token
  },
  actions: {
    setLogin(data) {
      this.token = data.access_token
      this.username = data.username || this.username
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('token_type', data.token_type || 'bearer')
      if (data.username) localStorage.setItem('username', data.username)
    },
    clearLogin() {
      this.token = ''
      this.username = ''
      this.role = ''
      localStorage.removeItem('token')
      localStorage.removeItem('token_type')
      localStorage.removeItem('username')
    },
    async fetchProfile() {
      if (!this.token) return null
      const res = await getMe()
      this.username = res.data?.username || this.username
      this.role = res.data?.role || ''
      this.status = res.data?.status ?? 1
      localStorage.setItem('username', this.username)
      return res.data
    }
  }
})
