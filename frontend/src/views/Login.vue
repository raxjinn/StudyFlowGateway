<template>
  <div class="flex items-center justify-center min-h-[calc(100vh-4rem)]">
    <div class="card max-w-md w-full">
      <h1 class="text-2xl font-bold text-center mb-6">Login</h1>
      
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
  
  const result = await authStore.login(username.value, password.value)
  
  if (result.success) {
    router.push('/dashboard')
  } else {
    error.value = result.error || 'Login failed'
  }
  
  loading.value = false
}
</script>

