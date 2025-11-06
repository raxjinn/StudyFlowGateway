import apiClient from './client'

// Auth
export const authAPI = {
  login: (username, password) => {
    // OAuth2PasswordRequestForm expects application/x-www-form-urlencoded
    const params = new URLSearchParams()
    params.append('username', username)
    params.append('password', password)
    return apiClient.post('/auth/login', params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
  },
  logout: () => apiClient.post('/auth/logout'),
  getCurrentUser: () => apiClient.get('/auth/me'),
  changePassword: (currentPassword, newPassword) => {
    return apiClient.post('/auth/password/change', {
      current_password: currentPassword,
      new_password: newPassword
    })
  }
}

// Health
export const healthAPI = {
  check: () => apiClient.get('/health')
}

// Metrics
export const metricsAPI = {
  getMetrics: () => apiClient.get('/metrics'),
  getPrometheus: () => apiClient.get('/metrics/prometheus')
}

// Studies
export const studiesAPI = {
  list: (params = {}) => apiClient.get('/studies', { params }),
  get: (id) => apiClient.get(`/studies/${id}`),
  getByUID: (uid) => apiClient.get(`/studies/uid/${uid}`),
  forward: (id, destinationIds = []) => {
    return apiClient.post(`/studies/${id}/forward`, {
      destination_ids: destinationIds
    })
  },
  getForwardJobs: (id) => apiClient.get(`/studies/${id}/forward-jobs`)
}

// Destinations
export const destinationsAPI = {
  list: (params = {}) => apiClient.get('/destinations', { params }),
  get: (id) => apiClient.get(`/destinations/${id}`),
  create: (data) => apiClient.post('/destinations', data),
  update: (id, data) => apiClient.put(`/destinations/${id}`, data),
  delete: (id) => apiClient.delete(`/destinations/${id}`)
}

// Queues
export const queuesAPI = {
  getStats: () => apiClient.get('/queues/stats'),
  retry: (jobIds = null) => {
    return apiClient.post('/queues/retry', {
      job_ids: jobIds
    })
  },
  replay: (studyUID, destinationIds = null) => {
    return apiClient.post(`/queues/replay/${studyUID}`, {
      destination_ids: destinationIds
    })
  }
}

// Audit
export const auditAPI = {
  list: (params = {}) => apiClient.get('/audit', { params }),
  get: (id) => apiClient.get(`/audit/${id}`),
  getStats: (params = {}) => apiClient.get('/audit/stats/summary', { params })
}

// Config
export const configAPI = {
  reload: () => apiClient.post('/config/reload'),
  uploadCert: (certFile, keyFile, caFile = null) => {
    const formData = new FormData()
    formData.append('cert_file', certFile)
    formData.append('key_file', keyFile)
    if (caFile) {
      formData.append('ca_file', caFile)
    }
    return apiClient.post('/certs/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}

