<template>
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="card max-w-2xl w-full max-h-[90vh] overflow-y-auto">
      <div class="flex justify-between items-center mb-4">
        <h2 class="text-2xl font-bold">
          {{ user ? 'Edit User' : 'Create User' }}
        </h2>
        <button @click="$emit('close')" class="text-gray-500 hover:text-gray-700">
          ✕
        </button>
      </div>
      
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Username *</label>
            <input 
              v-model="form.username" 
              type="text" 
              class="input" 
              :disabled="!!user"
              required 
            />
          </div>
          <div>
            <label class="label">Email</label>
            <input 
              v-model="form.email" 
              type="email" 
              class="input" 
            />
          </div>
        </div>
        
        <div>
          <label class="label">Full Name</label>
          <input 
            v-model="form.full_name" 
            type="text" 
            class="input" 
          />
        </div>
        
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Role *</label>
            <select v-model="form.role" class="input" required>
              <option value="viewer">Viewer</option>
              <option value="user">User</option>
              <option value="operator">Operator</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div>
            <label class="label">Status</label>
            <select v-model="form.enabled" class="input">
              <option :value="true">Enabled</option>
              <option :value="false">Disabled</option>
            </select>
          </div>
        </div>
        
        <div v-if="!user" class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Password *</label>
            <input 
              v-model="form.password" 
              type="password" 
              class="input" 
              :required="!user"
              minlength="8"
            />
          </div>
          <div>
            <label class="label">Confirm Password</label>
            <input 
              v-model="form.confirm_password" 
              type="password" 
              class="input" 
              :required="!user"
            />
          </div>
        </div>
        
        <div v-if="user" class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">New Password (leave blank to keep current)</label>
            <input 
              v-model="form.password" 
              type="password" 
              class="input" 
              minlength="8"
            />
          </div>
          <div>
            <label class="label">Confirm New Password</label>
            <input 
              v-model="form.confirm_password" 
              type="password" 
              class="input" 
            />
          </div>
        </div>
        
        <div v-if="error" class="text-red-600 dark:text-red-400 text-sm">
          {{ error }}
        </div>
        
        <div class="flex justify-end space-x-2">
          <button type="button" @click="$emit('close')" class="btn-secondary">
            Cancel
          </button>
          <button type="submit" class="btn-primary" :disabled="saving">
            {{ saving ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { authAPI } from '../api/services'

const props = defineProps({
  user: Object
})

const emit = defineEmits(['close', 'saved'])

const form = ref({
  username: '',
  email: '',
  full_name: '',
  role: 'user',
  enabled: true,
  password: '',
  confirm_password: ''
})

const error = ref('')
const saving = ref(false)

onMounted(() => {
  if (props.user) {
    form.value = {
      username: props.user.username,
      email: props.user.email || '',
      full_name: props.user.full_name || '',
      role: props.user.role,
      enabled: props.user.enabled,
      password: '',
      confirm_password: ''
    }
  }
})

const handleSubmit = async () => {
  error.value = ''
  
  // Validate password
  if (!props.user) {
    // Creating new user - password required
    if (!form.value.password || form.value.password.length < 8) {
      error.value = 'Password must be at least 8 characters'
      return
    }
    if (form.value.password !== form.value.confirm_password) {
      error.value = 'Passwords do not match'
      return
    }
  } else {
    // Updating user - password optional
    if (form.value.password) {
      if (form.value.password.length < 8) {
        error.value = 'Password must be at least 8 characters'
        return
      }
      if (form.value.password !== form.value.confirm_password) {
        error.value = 'Passwords do not match'
        return
      }
    }
  }
  
  saving.value = true
  try {
    const userData = {
      username: form.value.username,
      email: form.value.email || null,
      full_name: form.value.full_name || null,
      role: form.value.role,
      enabled: form.value.enabled
    }
    
    // Only include password if provided
    if (form.value.password) {
      userData.password = form.value.password
    }
    
    if (props.user) {
      // Update existing user
      await authAPI.updateUser(props.user.id, userData)
    } else {
      // Create new user
      await authAPI.createUser(userData)
    }
    
    emit('saved')
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || 'Failed to save user'
  } finally {
    saving.value = false
  }
}
</script>

