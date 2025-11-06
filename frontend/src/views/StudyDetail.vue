<template>
  <div class="space-y-6" v-if="study">
    <div class="flex justify-between items-center">
      <div>
        <router-link to="/studies" class="text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300 font-medium transition-colors">
          ← Back to Studies
        </router-link>
        <h1 class="text-3xl font-bold mt-2">Study Details</h1>
      </div>
      <button @click="handleForward" class="btn-primary" :disabled="forwarding">
        {{ forwarding ? 'Forwarding...' : 'Forward Study' }}
      </button>
    </div>
    
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Study Information -->
      <div class="card">
        <h2 class="text-xl font-semibold mb-4">Study Information</h2>
        <dl class="space-y-2">
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-gray-400">Study Instance UID</dt>
            <dd class="mt-1 text-sm font-mono">{{ study.study_instance_uid }}</dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-gray-400">Patient ID</dt>
            <dd class="mt-1 text-sm">{{ study.patient_id || '-' }}</dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-gray-400">Patient Name</dt>
            <dd class="mt-1 text-sm">{{ study.patient_name || '-' }}</dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-gray-400">Study Date</dt>
            <dd class="mt-1 text-sm">{{ study.study_date || '-' }}</dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-gray-400">Accession Number</dt>
            <dd class="mt-1 text-sm">{{ study.accession_number || '-' }}</dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-gray-400">Status</dt>
            <dd class="mt-1">
              <span
                :class="{
                  'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200': study.status === 'forwarded',
                  'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200': study.status === 'processing',
                  'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200': study.status === 'failed',
                  'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200': study.status === 'received'
                }"
                class="px-2 py-1 text-xs font-semibold rounded-full"
              >
                {{ study.status }}
              </span>
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-gray-400">File Count</dt>
            <dd class="mt-1 text-sm">{{ study.file_count }}</dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-gray-400">Total Size</dt>
            <dd class="mt-1 text-sm">{{ formatBytes(study.total_size_bytes) }}</dd>
          </div>
        </dl>
      </div>
      
      <!-- Forward Jobs -->
      <div class="card">
        <h2 class="text-xl font-semibold mb-4">Forward Jobs</h2>
        <div v-if="forwardJobs.length === 0" class="text-gray-500 dark:text-gray-400">
          No forward jobs
        </div>
        <div v-else class="space-y-2">
          <div
            v-for="job in forwardJobs"
            :key="job.id"
            class="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
          >
            <div class="flex justify-between items-start">
              <div>
                <p class="font-medium">{{ job.destination }}</p>
                <p class="text-sm text-gray-500 dark:text-gray-400">
                  Status: {{ job.status }} | Attempts: {{ job.attempts }}/{{ job.max_attempts }}
                </p>
                <p v-if="job.error_message" class="text-sm text-red-600 dark:text-red-400 mt-1">
                  {{ job.error_message }}
                </p>
              </div>
              <span
                :class="{
                  'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200': job.status === 'completed',
                  'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200': job.status === 'processing',
                  'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200': job.status === 'failed',
                  'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200': job.status === 'pending'
                }"
                class="px-2 py-1 text-xs font-semibold rounded-full"
              >
                {{ job.status }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  
  <div v-else class="text-center py-12">
    <div v-if="loading">Loading...</div>
    <div v-else>Study not found</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { studiesAPI, destinationsAPI } from '../api/services'

const route = useRoute()
const router = useRouter()

const study = ref(null)
const forwardJobs = ref([])
const loading = ref(false)
const forwarding = ref(false)

const formatBytes = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const fetchStudy = async () => {
  loading.value = true
  try {
    const studyId = route.params.id
    const [studyRes, jobsRes] = await Promise.all([
      studiesAPI.get(studyId),
      studiesAPI.getForwardJobs(studyId)
    ])
    
    study.value = studyRes.data
    forwardJobs.value = jobsRes.data || []
  } catch (error) {
    console.error('Failed to fetch study:', error)
  } finally {
    loading.value = false
  }
}

const handleForward = async () => {
  // Get list of enabled destinations
  try {
    const destsRes = await destinationsAPI.list({ enabled: true })
    const destinations = destsRes.data || []
    
    if (destinations.length === 0) {
      alert('No enabled destinations available')
      return
    }
    
    forwarding.value = true
    const destinationIds = destinations.map(d => d.id)
    
    await studiesAPI.forward(route.params.id, destinationIds)
    alert('Study forwarded successfully')
    await fetchStudy()
  } catch (error) {
    alert('Failed to forward study: ' + (error.response?.data?.detail || error.message))
  } finally {
    forwarding.value = false
  }
}

onMounted(() => {
  fetchStudy()
})
</script>

