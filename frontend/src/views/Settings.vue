<template>
  <div class="space-y-6">
    <h1 class="text-3xl font-bold">Settings</h1>
    
    <!-- User Profile -->
    <div class="card">
      <h2 class="text-xl font-semibold mb-4">User Profile</h2>
      <div v-if="authStore.user" class="space-y-4">
        <div>
          <label class="label">Username</label>
          <input :value="authStore.user.username" type="text" class="input" disabled />
        </div>
        <div>
          <label class="label">Email</label>
          <input :value="authStore.user.email || '-'" type="email" class="input" disabled />
        </div>
        <div>
          <label class="label">Role</label>
          <input :value="authStore.user.role" type="text" class="input" disabled />
        </div>
      </div>
    </div>
    
    <!-- Change Password -->
    <div class="card">
      <h2 class="text-xl font-semibold mb-4">Change Password</h2>
      <form @submit.prevent="handleChangePassword" class="space-y-4">
        <div>
          <label class="label">Current Password</label>
          <input v-model="passwordForm.current" type="password" class="input" required />
        </div>
        <div>
          <label class="label">New Password</label>
          <input v-model="passwordForm.new" type="password" class="input" required />
        </div>
        <div>
          <label class="label">Confirm New Password</label>
          <input v-model="passwordForm.confirm" type="password" class="input" required />
        </div>
        <div v-if="passwordError" class="text-red-600 dark:text-red-400 text-sm">
          {{ passwordError }}
        </div>
        <div v-if="passwordSuccess" class="text-green-600 dark:text-green-400 text-sm">
          Password changed successfully
        </div>
        <button type="submit" class="btn-primary" :disabled="changingPassword">
          {{ changingPassword ? 'Changing...' : 'Change Password' }}
        </button>
      </form>
    </div>
    
    <!-- System Settings (Admin only) -->
    <div v-if="authStore.isAdmin" class="card">
      <h2 class="text-xl font-semibold mb-4">System Configuration</h2>
      <div class="space-y-4">
        <div>
          <label class="label">Configuration File Path</label>
          <input :value="configPath" type="text" class="input" disabled />
        </div>
        
        <div class="flex space-x-2">
          <button @click="fetchConfig" class="btn-secondary" :disabled="loadingConfig">
            {{ loadingConfig ? 'Loading...' : 'View Configuration' }}
          </button>
          <button @click="handleReloadConfig" class="btn-secondary" :disabled="reloading">
            {{ reloading ? 'Reloading...' : 'Reload Configuration' }}
          </button>
        </div>
        
        <div v-if="configData" class="mt-4">
          <label class="label">Current Configuration (read-only)</label>
          <pre class="bg-gray-100 dark:bg-gray-900 p-4 rounded overflow-auto max-h-96 text-sm">{{ formattedConfig }}</pre>
        </div>
        
        <div class="mt-4">
          <h3 class="text-lg font-semibold mb-2">Upload Configuration File</h3>
          <div class="space-y-2">
            <input 
              type="file" 
              @change="handleConfigFileChange" 
              accept=".yaml,.yml"
              class="input" 
            />
            <button 
              @click="handleUploadConfig" 
              class="btn-primary" 
              :disabled="!configFile || uploadingConfig"
            >
              {{ uploadingConfig ? 'Uploading...' : 'Upload Configuration' }}
            </button>
            <p class="text-sm text-gray-600 dark:text-gray-400">
              Upload a YAML configuration file. A backup will be created automatically.
            </p>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Certificates (Admin only) -->
    <div v-if="authStore.isAdmin" class="card">
      <h2 class="text-xl font-semibold mb-4">TLS Certificates</h2>
      <div class="space-y-4">
        <div>
          <label class="label">Certificate File</label>
          <input type="file" @change="handleCertFileChange" class="input" />
        </div>
        <div>
          <label class="label">Private Key File</label>
          <input type="file" @change="handleKeyFileChange" class="input" />
        </div>
        <div>
          <label class="label">CA Certificate File (Optional)</label>
          <input type="file" @change="handleCaFileChange" class="input" />
        </div>
        <button @click="handleUploadCerts" class="btn-primary" :disabled="uploading">
          {{ uploading ? 'Uploading...' : 'Upload Certificates' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { configAPI } from '../api/services'

const authStore = useAuthStore()

const passwordForm = ref({
  current: '',
  new: '',
  confirm: ''
})

const passwordError = ref('')
const passwordSuccess = ref(false)
const changingPassword = ref(false)
const reloading = ref(false)
const uploading = ref(false)

const certFile = ref(null)
const keyFile = ref(null)
const caFile = ref(null)

const configData = ref(null)
const configPath = ref('')
const loadingConfig = ref(false)
const configFile = ref(null)
const uploadingConfig = ref(false)

const formattedConfig = computed(() => {
  if (!configData.value) return ''
  return JSON.stringify(configData.value, null, 2)
})

onMounted(() => {
  if (authStore.isAuthenticated && !authStore.user) {
    authStore.fetchUser()
  }
  if (authStore.isAdmin) {
    fetchConfig()
  }
})

const fetchConfig = async () => {
  loadingConfig.value = true
  try {
    const response = await configAPI.get()
    configData.value = response.data.config
    configPath.value = response.data.config_path
  } catch (error) {
    console.error('Failed to fetch config:', error)
    alert('Failed to fetch configuration: ' + (error.response?.data?.detail || error.message))
  } finally {
    loadingConfig.value = false
  }
}

const handleConfigFileChange = (event) => {
  configFile.value = event.target.files[0]
}

const handleUploadConfig = async () => {
  if (!configFile.value) {
    alert('Please select a configuration file')
    return
  }
  
  if (!configFile.value.name.endsWith('.yaml') && !configFile.value.name.endsWith('.yml')) {
    alert('Configuration file must be a YAML file (.yaml or .yml)')
    return
  }
  
  if (!confirm('This will replace the current configuration file. A backup will be created. Continue?')) {
    return
  }
  
  uploadingConfig.value = true
  try {
    await configAPI.upload(configFile.value)
    alert('Configuration uploaded and reloaded successfully')
    configFile.value = null
    await fetchConfig()
  } catch (error) {
    alert('Failed to upload configuration: ' + (error.response?.data?.detail || error.message))
  } finally {
    uploadingConfig.value = false
  }
}

const handleChangePassword = async () => {
  if (passwordForm.value.new !== passwordForm.value.confirm) {
    passwordError.value = 'New passwords do not match'
    return
  }
  
  if (passwordForm.value.new.length < 8) {
    passwordError.value = 'Password must be at least 8 characters'
    return
  }
  
  passwordError.value = ''
  passwordSuccess.value = false
  changingPassword.value = true
  
  const result = await authStore.changePassword(
    passwordForm.value.current,
    passwordForm.value.new
  )
  
  if (result.success) {
    passwordSuccess.value = true
    passwordForm.value = { current: '', new: '', confirm: '' }
  } else {
    passwordError.value = result.error || 'Password change failed'
  }
  
  changingPassword.value = false
}

const handleReloadConfig = async () => {
  reloading.value = true
  try {
    await configAPI.reload()
    alert('Configuration reloaded successfully')
  } catch (error) {
    alert('Failed to reload config: ' + (error.response?.data?.detail || error.message))
  } finally {
    reloading.value = false
  }
}

const handleCertFileChange = (event) => {
  certFile.value = event.target.files[0]
}

const handleKeyFileChange = (event) => {
  keyFile.value = event.target.files[0]
}

const handleCaFileChange = (event) => {
  caFile.value = event.target.files[0]
}

const handleUploadCerts = async () => {
  if (!certFile.value || !keyFile.value) {
    alert('Please select certificate and key files')
    return
  }
  
  uploading.value = true
  try {
    await configAPI.uploadCert(certFile.value, keyFile.value, caFile.value)
    alert('Certificates uploaded successfully')
  } catch (error) {
    alert('Failed to upload certificates: ' + (error.response?.data?.detail || error.message))
  } finally {
    uploading.value = false
  }
}
</script>

