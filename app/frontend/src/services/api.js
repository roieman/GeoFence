import axios from 'axios'

const API_BASE_URL = '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  },
  timeout: 300000 // 5 minute timeout (300000ms)
})

export const containerAPI = {
  track: (containerId, startDate, endDate) => {
    const params = {}
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    return api.get(`/containers/${containerId}/track`, { params })
  }
}

export const alertsAPI = {
  getAll: (filters = {}) => {
    return api.get('/alerts', { params: filters })
  },
  acknowledge: (alertId) => {
    return api.post(`/alerts/${alertId}/acknowledge`)
  }
}

export const locationsAPI = {
  getAll: (search, locationType, limit = 10) => {
    const params = { limit }
    if (search) params.search = search
    if (locationType) params.location_type = locationType
    return api.get('/locations', { params })
  },
  getStatic: () => {
    return api.get('/locations/static')
  },
  getContainers: (locationName, startDate, endDate, radiusMeters, page, limit) => {
    const params = { radius_meters: radiusMeters, page, limit }
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    return api.get(`/locations/${encodeURIComponent(locationName)}/containers`, { params })
  },
  getContainersTimeSeries: (locationName, startDate, endDate, radiusMeters, page, limit) => {
    const params = { radius_meters: radiusMeters, page, limit }
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    return api.get(`/locations/${encodeURIComponent(locationName)}/containers/timeseries`, { params })
  }
}

export const statsAPI = {
  get: () => {
    return api.get('/stats')
  }
}

export default api

