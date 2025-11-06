<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <h1 class="text-3xl font-bold">Users</h1>
      <button @click="showCreateModal = true" class="btn-primary">
        Create User
      </button>
    </div>
    
    <!-- Users Table -->
    <div class="card overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
        <thead>
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Username
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Email
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Full Name
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Role
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Status
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Last Login
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
          <tr v-for="user in users" :key="user.id" class="hover:bg-gray-50 dark:hover:bg-gray-700">
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
              {{ user.username }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
              {{ user.email || '-' }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
              {{ user.full_name || '-' }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <span
                :class="{
                  'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200': user.role === 'admin',
                  'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200': user.role === 'operator',
                  'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200': user.role === 'user',
                  'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200': user.role === 'viewer'
                }"
                class="px-2 py-1 text-xs font-semibold rounded-full"
              >
                {{ user.role }}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <span
                :class="{
                  'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200': user.enabled,
                  'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200': !user.enabled
                }"
                class="px-2 py-1 text-xs font-semibold rounded-full"
              >
                {{ user.enabled ? 'Enabled' : 'Disabled' }}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
              {{ user.last_login_at ? formatDate(user.last_login_at) : 'Never' }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm space-x-2">
              <button
                @click="editUser(user)"
                class="text-primary-600 hover:text-primary-800 dark:text-primary-400"
              >
                Edit
              </button>
              <button
                v-if="user.id !== authStore.user?.id"
                @click="deleteUser(user.id, user.username)"
                class="text-red-600 hover:text-red-800 dark:text-red-400"
              >
                Delete
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      
      <div v-if="users.length === 0 && !loading" class="px-6 py-4 text-center text-gray-500 dark:text-gray-400">
        No users found
      </div>
    </div>
    
    <!-- Create/Edit Modal -->
    <UserModal
      v-if="showCreateModal || editingUser"
      :user="editingUser"
      @close="closeModal"
      @saved="handleUserSaved"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { authAPI } from '../api/services'
import { useAuthStore } from '../stores/auth'
import UserModal from '../components/UserModal.vue'

const authStore = useAuthStore()

const users = ref([])
const loading = ref(false)
const showCreateModal = ref(false)
const editingUser = ref(null)

const formatDate = (dateString) => {
  return new Date(dateString).toLocaleString()
}

const fetchUsers = async () => {
  loading.value = true
  try {
    const response = await authAPI.listUsers()
    users.value = response.data || []
  } catch (error) {
    console.error('Failed to fetch users:', error)
    alert('Failed to fetch users: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

const editUser = (user) => {
  editingUser.value = user
}

const deleteUser = async (id, username) => {
  if (!confirm(`Are you sure you want to delete user "${username}"? This action cannot be undone.`)) {
    return
  }
  
  try {
    await authAPI.deleteUser(id)
    await fetchUsers()
  } catch (error) {
    alert('Failed to delete user: ' + (error.response?.data?.detail || error.message))
  }
}

const closeModal = () => {
  showCreateModal.value = false
  editingUser.value = null
}

const handleUserSaved = () => {
  closeModal()
  fetchUsers()
}

onMounted(() => {
  fetchUsers()
})
</script>

