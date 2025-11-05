<template>
  <nav class="bg-white dark:bg-gray-800 shadow-lg">
    <div class="container mx-auto px-4">
      <div class="flex justify-between items-center h-16">
        <div class="flex items-center space-x-8">
          <router-link to="/dashboard" class="text-xl font-bold text-primary-600">
            DICOM Gateway
          </router-link>
          
          <div class="flex space-x-4" v-if="authStore.isAuthenticated">
            <router-link
              to="/dashboard"
              class="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-700"
              active-class="bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300"
            >
              Dashboard
            </router-link>
            <router-link
              to="/studies"
              class="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-700"
              active-class="bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300"
            >
              Studies
            </router-link>
            <router-link
              to="/destinations"
              class="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-700"
              active-class="bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300"
            >
              Destinations
            </router-link>
            <router-link
              to="/queues"
              class="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-700"
              active-class="bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300"
            >
              Queues
            </router-link>
            <router-link
              to="/settings"
              class="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-700"
              active-class="bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300"
            >
              Settings
            </router-link>
          </div>
        </div>
        
        <div class="flex items-center space-x-4" v-if="authStore.isAuthenticated">
          <span class="text-sm text-gray-600 dark:text-gray-400">
            {{ authStore.userName }}
          </span>
          <button
            @click="handleLogout"
            class="btn-secondary text-sm"
          >
            Logout
          </button>
          <button
            @click="toggleDarkMode"
            class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <svg v-if="!isDark" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
            <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const isDark = ref(false)

onMounted(() => {
  isDark.value = document.documentElement.classList.contains('dark')
  if (authStore.isAuthenticated && !authStore.user) {
    authStore.fetchUser()
  }
})

const toggleDarkMode = () => {
  isDark.value = !isDark.value
  if (isDark.value) {
    document.documentElement.classList.add('dark')
    localStorage.setItem('darkMode', 'true')
  } else {
    document.documentElement.classList.remove('dark')
    localStorage.setItem('darkMode', 'false')
  }
}

const handleLogout = async () => {
  await authStore.logout()
  router.push('/login')
}
</script>

