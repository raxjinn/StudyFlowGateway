<template>
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="card max-w-2xl w-full max-h-[90vh] overflow-y-auto">
      <div class="flex justify-between items-center mb-4">
        <h2 class="text-2xl font-bold">
          {{ destination ? 'Edit Destination' : 'Add Destination' }}
        </h2>
        <button @click="$emit('close')" class="text-gray-500 hover:text-gray-700">
          ✕
        </button>
      </div>
      
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Name *</label>
            <input v-model="form.name" type="text" class="input" required />
          </div>
          <div>
            <label class="label">AE Title *</label>
            <input v-model="form.ae_title" type="text" class="input" maxlength="16" required />
          </div>
        </div>
        
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Host *</label>
            <input v-model="form.host" type="text" class="input" required />
          </div>
          <div>
            <label class="label">Port *</label>
            <input v-model.number="form.port" type="number" class="input" min="1" max="65535" required />
          </div>
        </div>
        
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Max PDU</label>
            <input v-model.number="form.max_pdu" type="number" class="input" />
          </div>
          <div>
            <label class="label">Timeout (seconds)</label>
            <input v-model.number="form.timeout" type="number" class="input" />
          </div>
        </div>
        
        <div>
          <label class="flex items-center space-x-2">
            <input v-model="form.tls_enabled" type="checkbox" class="rounded" />
            <span>Enable TLS</span>
          </label>
        </div>
        
        <div v-if="form.tls_enabled" class="space-y-4">
          <div>
            <label class="label">TLS Certificate Path</label>
            <input v-model="form.tls_cert_path" type="text" class="input" />
          </div>
          <div>
            <label class="label">TLS Key Path</label>
            <input v-model="form.tls_key_path" type="text" class="input" />
          </div>
          <div>
            <label class="label">TLS CA Path</label>
            <input v-model="form.tls_ca_path" type="text" class="input" />
          </div>
        </div>
        
        <div>
          <label class="label">Description</label>
          <textarea v-model="form.description" class="input" rows="3"></textarea>
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
import { destinationsAPI } from '../api/services'

const props = defineProps({
  destination: Object
})

const emit = defineEmits(['close', 'saved'])

const form = ref({
  name: '',
  ae_title: '',
  host: '',
  port: 104,
  max_pdu: 16384,
  timeout: 30,
  connection_timeout: 10,
  tls_enabled: false,
  tls_cert_path: '',
  tls_key_path: '',
  tls_ca_path: '',
  tls_no_verify: false,
  description: ''
})

const saving = ref(false)

onMounted(() => {
  if (props.destination) {
    form.value = { ...props.destination }
  }
})

const handleSubmit = async () => {
  saving.value = true
  try {
    if (props.destination) {
      await destinationsAPI.update(props.destination.id, form.value)
    } else {
      await destinationsAPI.create(form.value)
    }
    emit('saved')
  } catch (error) {
    alert('Failed to save destination: ' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}
</script>

