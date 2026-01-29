import axios from 'axios'

const API_BASE_URL = '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  },
  timeout: 300000 // 5 minute timeout
})

// Request interceptor for better error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.code === 'ECONNABORTED') {
      error.message = 'Request timeout. The operation took too long.'
    } else if (!error.response) {
      error.message = 'Network error. Please check your connection.'
    }
    return Promise.reject(error)
  }
)

// =============================================================================
// GEOFENCES API
// =============================================================================

export const geofencesAPI = {
  list: (params = {}) => {
    return api.get('/geofences', { params })
  },

  get: (id) => {
    return api.get(`/geofences/${id}`)
  },

  getByName: (name) => {
    return api.get(`/geofences/by-name/${encodeURIComponent(name)}`)
  },

  create: (geofence) => {
    return api.post('/geofences', geofence)
  },

  update: (id, updates) => {
    return api.put(`/geofences/${id}`, updates)
  },

  delete: (id) => {
    return api.delete(`/geofences/${id}`)
  },

  exportCSV: (typeId) => {
    const params = typeId ? { type_id: typeId } : {}
    return api.get('/geofences/export/csv', {
      params,
      responseType: 'blob'
    })
  },

  exportGeoJSON: (typeId) => {
    const params = typeId ? { type_id: typeId } : {}
    return api.get('/geofences/export/geojson', {
      params,
      responseType: 'blob'
    })
  },

  importCSV: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/geofences/import/csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  atPoint: (lon, lat) => {
    return api.get('/geofences/at-point', { params: { lon, lat } })
  }
}

// =============================================================================
// IOT EVENTS API
// =============================================================================

export const iotEventsAPI = {
  list: (params = {}) => {
    return api.get('/iot-events', { params })
  },

  latest: (limit = 50) => {
    return api.get('/iot-events/latest', { params: { limit } })
  },

  byContainer: (containerId, startDate, endDate, limit = 1000) => {
    const params = { limit }
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    return api.get(`/iot-events/by-container/${encodeURIComponent(containerId)}`, { params })
  },

  inGeofence: (geofenceName, startDate, endDate, limit = 100) => {
    const params = { limit }
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    return api.get(`/iot-events/in-geofence/${encodeURIComponent(geofenceName)}`, { params })
  }
}

// =============================================================================
// GATE EVENTS API (Geofence Crossings)
// =============================================================================

export const gateEventsAPI = {
  list: (params = {}) => {
    return api.get('/gate-events', { params })
  }
}

// =============================================================================
// CONTAINERS API
// =============================================================================

export const containersAPI = {
  list: (params = {}) => {
    return api.get('/containers', { params })
  },

  get: (containerId) => {
    return api.get(`/containers/${encodeURIComponent(containerId)}`)
  },

  positions: () => {
    return api.get('/containers/positions/latest')
  }
}

// =============================================================================
// STATS & REFERENCE API
// =============================================================================

export const statsAPI = {
  get: () => {
    return api.get('/stats')
  }
}

export const referenceAPI = {
  geofenceTypes: () => {
    return api.get('/reference/geofence-types')
  },

  eventTypes: () => {
    return api.get('/reference/event-types')
  }
}

// =============================================================================
// LEGACY API (for backward compatibility)
// =============================================================================

export const containerAPI = {
  track: (containerId, startDate, endDate) => {
    return iotEventsAPI.byContainer(containerId, startDate, endDate)
  }
}

export const alertsAPI = {
  getAll: (filters = {}) => {
    return gateEventsAPI.list(filters)
  },
  acknowledge: (alertId) => {
    // Gate events don't have acknowledge, but keep for compatibility
    return Promise.resolve({ data: { success: true } })
  }
}

export const locationsAPI = {
  getAll: (search, locationType, limit = 10) => {
    const params = { limit }
    if (search) params.search = search
    if (locationType) params.type_id = locationType
    return geofencesAPI.list(params)
  },
  getStatic: () => {
    return geofencesAPI.list({ limit: 10 })
  },
  getContainers: (locationName, startDate, endDate, radiusMeters, page, limit) => {
    return iotEventsAPI.inGeofence(locationName, startDate, endDate, limit)
  }
}

export default api
