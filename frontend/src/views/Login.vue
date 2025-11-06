<template>
  <div class="flex items-center justify-center min-h-[calc(100vh-4rem)] bg-gradient-to-br from-accent-800 to-accent-900">
    <div class="card max-w-md w-full shadow-xl bg-white dark:bg-accent-800">
      <div class="text-center mb-6">
        <h1 class="text-3xl font-bold text-primary-600 dark:text-primary-500 mb-2">DICOM Gateway</h1>
        <p class="text-gray-600 dark:text-gray-400">Sign in to your account</p>
      </div>
      
      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label class="label">Username</label>
          <input
            v-model="username"
            type="text"
            class="input"
            required
            autocomplete="username"
          />
        </div>
        
        <div>
          <label class="label">Password</label>
          <input
            v-model="password"
            type="password"
            class="input"
            required
            autocomplete="current-password"
          />
        </div>
        
        <div v-if="error" class="text-red-600 dark:text-red-400 text-sm">
          {{ error }}
        </div>
        
        <button
          type="submit"
          class="btn-primary w-full"
          :disabled="loading"
        >
          {{ loading ? 'Logging in...' : 'Login' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

const handleLogin = async () => {
  error.value = ''
  loading.value = true
  
  try {
    const result = await authStore.login(username.value, password.value)
    
    if (result.success) {
      router.push('/dashboard')
    } else {
      error.value = result.error || 'Login failed'
      // Keep error visible for at least 3 seconds
      setTimeout(() => {
        if (error.value === result.error) {
          error.value = ''
        }
      }, 3000)
    }
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || 'Login failed. Please check your credentials.'
    // Keep error visible for at least 3 seconds
    setTimeout(() => {
      if (error.value === err.response?.data?.detail || err.message) {
        error.value = ''
      }
    }, 3000)
  } finally {
    loading.value = false
  }
}
</script>

