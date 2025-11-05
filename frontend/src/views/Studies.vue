<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <h1 class="text-3xl font-bold">Studies</h1>
      <div class="flex space-x-2">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search..."
          class="input"
        />
        <button @click="refresh" class="btn-secondary">
          Refresh
        </button>
      </div>
    </div>
    
    <!-- Filters -->
    <div class="card">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div>
          <label class="label">Status</label>
          <select v-model="filters.status" class="input">
            <option value="">All</option>
            <option value="received">Received</option>
            <option value="processing">Processing</option>
            <option value="forwarded">Forwarded</option>
            <option value="failed">Failed</option>
          </select>
        </div>
        <div>
          <label class="label">Patient ID</label>
          <input v-model="filters.patient_id" type="text" class="input" />
        </div>
        <div>
          <label class="label">Study Date</label>
          <input v-model="filters.study_date" type="date" class="input" />
        </div>
        <div class="flex items-end">
          <button @click="clearFilters" class="btn-secondary w-full">
            Clear Filters
          </button>
        </div>
      </div>
    </div>
    
    <!-- Studies Table -->
    <div class="card overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
        <thead>
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Study UID
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Patient ID
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Study Date
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Status
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Files
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
          <tr v-for="study in studies" :key="study.id" class="hover:bg-gray-50 dark:hover:bg-gray-700">
            <td class="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-900 dark:text-gray-100">
              {{ study.study_instance_uid.substring(0, 40) }}...
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
              {{ study.patient_id || '-' }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
              {{ study.study_date || '-' }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
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
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
              {{ study.file_count }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
              <router-link
                :to="`/studies/${study.id}`"
                class="text-primary-600 hover:text-primary-800 dark:text-primary-400"
              >
                View
              </router-link>
            </td>
          </tr>
        </tbody>
      </table>
      
      <div v-if="loading" class="p-4 text-center text-gray-500">
        Loading...
      </div>
      
      <div v-if="!loading && studies.length === 0" class="p-4 text-center text-gray-500">
        No studies found
      </div>
      
      <!-- Pagination -->
      <div v-if="total > 0" class="px-6 py-4 flex items-center justify-between border-t border-gray-200 dark:border-gray-700">
        <div class="text-sm text-gray-700 dark:text-gray-300">
          Showing {{ skip + 1 }} to {{ Math.min(skip + limit, total) }} of {{ total }}
        </div>
        <div class="flex space-x-2">
          <button
            @click="previousPage"
            :disabled="skip === 0"
            class="btn-secondary"
          >
            Previous
          </button>
          <button
            @click="nextPage"
            :disabled="skip + limit >= total"
            class="btn-secondary"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { studiesAPI } from '../api/services'

const studies = ref([])
const loading = ref(false)
const total = ref(0)
const skip = ref(0)
const limit = ref(50)

const searchQuery = ref('')
const filters = ref({
  status: '',
  patient_id: '',
  study_date: ''
})

const fetchStudies = async () => {
  loading.value = true
  try {
    const params = {
      skip: skip.value,
      limit: limit.value,
      ...filters.value
    }
    
    // Remove empty filters
    Object.keys(params).forEach(key => {
      if (params[key] === '') {
        delete params[key]
      }
    })
    
    const response = await studiesAPI.list(params)
    studies.value = response.data || []
    // Note: API doesn't return total count, so we'll need to handle pagination differently
  } catch (error) {
    console.error('Failed to fetch studies:', error)
  } finally {
    loading.value = false
  }
}

const refresh = () => {
  skip.value = 0
  fetchStudies()
}

const clearFilters = () => {
  filters.value = {
    status: '',
    patient_id: '',
    study_date: ''
  }
  refresh()
}

const nextPage = () => {
  skip.value += limit.value
  fetchStudies()
}

const previousPage = () => {
  skip.value = Math.max(0, skip.value - limit.value)
  fetchStudies()
}

watch([filters, searchQuery], () => {
  refresh()
})

onMounted(() => {
  fetchStudies()
})
</script>

