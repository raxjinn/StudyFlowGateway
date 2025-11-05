<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <h1 class="text-3xl font-bold">Queues</h1>
      <button @click="refresh" class="btn-secondary">
        Refresh
      </button>
    </div>
    
    <!-- Queue Statistics -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
      <div class="card">
        <p class="text-sm text-gray-600 dark:text-gray-400">Pending</p>
        <p class="text-3xl font-bold">{{ queueStats.pending || 0 }}</p>
      </div>
      <div class="card">
        <p class="text-sm text-gray-600 dark:text-gray-400">Processing</p>
        <p class="text-3xl font-bold">{{ queueStats.processing || 0 }}</p>
      </div>
      <div class="card">
        <p class="text-sm text-gray-600 dark:text-gray-400">Completed</p>
        <p class="text-3xl font-bold text-green-600">{{ queueStats.completed || 0 }}</p>
      </div>
      <div class="card">
        <p class="text-sm text-gray-600 dark:text-gray-400">Failed</p>
        <p class="text-3xl font-bold text-red-600">{{ queueStats.failed || 0 }}</p>
      </div>
    </div>
    
    <!-- Actions -->
    <div class="card">
      <h2 class="text-xl font-semibold mb-4">Queue Actions</h2>
      <div class="flex space-x-4">
        <button @click="handleRetryAll" class="btn-primary" :disabled="retrying">
          {{ retrying ? 'Retrying...' : 'Retry All Failed Jobs' }}
        </button>
        <button @click="handleRetryDeadLetter" class="btn-secondary" :disabled="retrying">
          Retry Dead Letter Queue
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { queuesAPI } from '../api/services'

const queueStats = ref({})
const retrying = ref(false)

const fetchStats = async () => {
  try {
    const response = await queuesAPI.getStats()
    queueStats.value = response.data || {}
  } catch (error) {
    console.error('Failed to fetch queue stats:', error)
  }
}

const refresh = () => {
  fetchStats()
}

const handleRetryAll = async () => {
  retrying.value = true
  try {
    await queuesAPI.retry()
    alert('Retry initiated')
    await fetchStats()
  } catch (error) {
    alert('Failed to retry jobs: ' + (error.response?.data?.detail || error.message))
  } finally {
    retrying.value = false
  }
}

const handleRetryDeadLetter = async () => {
  // Similar to retry all but filtered for dead_letter status
  // This would require API support
  alert('Dead letter retry not yet implemented in API')
}

onMounted(() => {
  fetchStats()
  setInterval(fetchStats, 10000) // Refresh every 10 seconds
})
</script>

