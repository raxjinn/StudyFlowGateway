import { defineStore } from 'pinia'
import { authAPI } from '../api/services'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    token: localStorage.getItem('access_token') || null,
    isAuthenticated: !!localStorage.getItem('access_token')
  }),

  actions: {
    async login(username, password) {
      try {
        const response = await authAPI.login(username, password)
        const { access_token } = response.data
        
        this.token = access_token
        this.isAuthenticated = true
        localStorage.setItem('access_token', access_token)
        
        // Fetch user info
        await this.fetchUser()
        
        return { success: true }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.detail || 'Login failed'
        }
      }
    },

    async logout() {
      try {
        await authAPI.logout()
      } catch (error) {
        console.error('Logout error:', error)
      } finally {
        this.token = null
        this.user = null
        this.isAuthenticated = false
        localStorage.removeItem('access_token')
      }
    },

    async fetchUser() {
      try {
        const response = await authAPI.getCurrentUser()
        this.user = response.data
      } catch (error) {
        console.error('Failed to fetch user:', error)
        this.logout()
      }
    },

    async changePassword(currentPassword, newPassword) {
      try {
        await authAPI.changePassword(currentPassword, newPassword)
        return { success: true }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.detail || 'Password change failed'
        }
      }
    }
  },

  getters: {
    isAdmin: (state) => state.user?.role === 'admin',
    isOperator: (state) => ['admin', 'operator'].includes(state.user?.role),
    userName: (state) => state.user?.username || 'Guest'
  }
})

