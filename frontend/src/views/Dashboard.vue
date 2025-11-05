<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <h1 class="text-3xl font-bold">Dashboard</h1>
      <button @click="refresh" class="btn-secondary">
        Refresh
      </button>
    </div>
    
    <!-- Metrics Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <MetricCard
        title="Studies Received"
        :value="stats.studies_received || 0"
        icon="📁"
      />
      <MetricCard
        title="Studies Forwarded"
        :value="stats.studies_forwarded || 0"
        icon="📤"
      />
      <MetricCard
        title="Queue Depth"
        :value="queueStats.pending || 0"
        icon="⏳"
      />
      <MetricCard
        title="Active Destinations"
        :value="stats.active_destinations || 0"
        icon="🎯"
      />
    </div>
    
    <!-- Charts -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="card">
        <h2 class="text-xl font-semibold mb-4">Recent Activity</h2>
        <div class="text-gray-500 dark:text-gray-400">
          Chart placeholder - Recent activity timeline
        </div>
      </div>
      
      <div class="card">
        <h2 class="text-xl font-semibold mb-4">Queue Status</h2>
        <div class="space-y-2">
          <div class="flex justify-between">
            <span>Pending:</span>
            <span class="font-semibold">{{ queueStats.pending || 0 }}</span>
          </div>
          <div class="flex justify-between">
            <span>Processing:</span>
            <span class="font-semibold">{{ queueStats.processing || 0 }}</span>
          </div>
          <div class="flex justify-between">
            <span>Completed:</span>
            <span class="font-semibold text-green-600">{{ queueStats.completed || 0 }}</span>
          </div>
          <div class="flex justify-between">
            <span>Failed:</span>
            <span class="font-semibold text-red-600">{{ queueStats.failed || 0 }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { metricsAPI, queuesAPI } from '../api/services'
import MetricCard from '../components/MetricCard.vue'

const stats = ref({})
const queueStats = ref({})
const loading = ref(false)

const fetchData = async () => {
  loading.value = true
  try {
    const [metricsRes, queuesRes] = await Promise.all([
      metricsAPI.getMetrics(),
      queuesAPI.getStats()
    ])
    
    stats.value = metricsRes.data || {}
    queueStats.value = queuesRes.data || {}
  } catch (error) {
    console.error('Failed to fetch dashboard data:', error)
  } finally {
    loading.value = false
  }
}

const refresh = () => {
  fetchData()
}

onMounted(() => {
  fetchData()
  // Refresh every 30 seconds
  setInterval(fetchData, 30000)
})
</script>

