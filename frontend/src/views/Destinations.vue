<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <h1 class="text-3xl font-bold">Destinations</h1>
      <button @click="showCreateModal = true" class="btn-primary">
        Add Destination
      </button>
    </div>
    
    <!-- Destinations Table -->
    <div class="card overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
        <thead>
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Name
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              AE Title
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Host:Port
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Status
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Last Success
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
          <tr v-for="dest in destinations" :key="dest.id" class="hover:bg-gray-50 dark:hover:bg-gray-700">
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
              {{ dest.name }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-mono">
              {{ dest.ae_title }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
              {{ dest.host }}:{{ dest.port }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <span
                :class="{
                  'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200': dest.enabled,
                  'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200': !dest.enabled
                }"
                class="px-2 py-1 text-xs font-semibold rounded-full"
              >
                {{ dest.enabled ? 'Enabled' : 'Disabled' }}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
              {{ dest.last_success_at ? formatDate(dest.last_success_at) : '-' }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm space-x-2">
              <button
                @click="editDestination(dest)"
                class="text-primary-600 hover:text-primary-700 dark:text-primary-500 dark:hover:text-primary-400 font-medium transition-colors"
              >
                Edit
              </button>
              <button
                @click="deleteDestination(dest.id)"
                class="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 font-medium transition-colors"
              >
                Delete
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    
    <!-- Create/Edit Modal -->
    <DestinationModal
      v-if="showCreateModal || editingDestination"
      :destination="editingDestination"
      @close="closeModal"
      @saved="handleDestinationSaved"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { destinationsAPI } from '../api/services'
import DestinationModal from '../components/DestinationModal.vue'

const destinations = ref([])
const loading = ref(false)
const showCreateModal = ref(false)
const editingDestination = ref(null)

const formatDate = (dateString) => {
  return new Date(dateString).toLocaleString()
}

const fetchDestinations = async () => {
  loading.value = true
  try {
    const response = await destinationsAPI.list()
    destinations.value = response.data || []
  } catch (error) {
    console.error('Failed to fetch destinations:', error)
  } finally {
    loading.value = false
  }
}

const editDestination = (dest) => {
  editingDestination.value = dest
}

const deleteDestination = async (id) => {
  if (!confirm('Are you sure you want to delete this destination?')) {
    return
  }
  
  try {
    await destinationsAPI.delete(id)
    await fetchDestinations()
  } catch (error) {
    alert('Failed to delete destination: ' + (error.response?.data?.detail || error.message))
  }
}

const closeModal = () => {
  showCreateModal.value = false
  editingDestination.value = null
}

const handleDestinationSaved = () => {
  closeModal()
  fetchDestinations()
}

onMounted(() => {
  fetchDestinations()
})
</script>

