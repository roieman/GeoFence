import React, { useState, useEffect } from 'react'
import { alertsAPI } from '../services/api'
import { format } from 'date-fns'

function AlertsGrid() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState({
    container_id: '',
    shipping_line: '',
    location_name: '',
    acknowledged: null,
    start_date: '',
    end_date: ''
  })
  const [pagination, setPagination] = useState({ page: 1, limit: 50, total: 0, pages: 0 })

  const loadAlerts = async (page = 1) => {
    setLoading(true)
    try {
      const params = { page, limit: pagination.limit, ...filters }
      // Remove empty filters
      Object.keys(params).forEach(key => {
        if (params[key] === '' || params[key] === null) delete params[key]
      })
      
      const response = await alertsAPI.getAll(params)
      setAlerts(response.data.alerts)
      setPagination(response.data.pagination)
    } catch (err) {
      console.error('Failed to load alerts:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAlerts(1)
  }, [])

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  const handleSearch = () => {
    loadAlerts(1)
  }

  const handleAcknowledge = async (alertId) => {
    try {
      await alertsAPI.acknowledge(alertId)
      loadAlerts(pagination.page)
    } catch (err) {
      console.error('Failed to acknowledge alert:', err)
    }
  }

  const handlePageChange = (newPage) => {
    loadAlerts(newPage)
  }

  return (
    <div>
      <div className="card">
        <h2>Alerts</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
          <div className="form-group">
            <label className="form-label">Container ID</label>
            <input
              type="text"
              className="input"
              value={filters.container_id}
              onChange={(e) => handleFilterChange('container_id', e.target.value)}
              placeholder="Filter by container ID"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Shipping Line</label>
            <input
              type="text"
              className="input"
              value={filters.shipping_line}
              onChange={(e) => handleFilterChange('shipping_line', e.target.value)}
              placeholder="Filter by shipping line"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Location Name</label>
            <input
              type="text"
              className="input"
              value={filters.location_name}
              onChange={(e) => handleFilterChange('location_name', e.target.value)}
              placeholder="Filter by location"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Acknowledged</label>
            <select
              className="input"
              value={filters.acknowledged === null ? '' : filters.acknowledged}
              onChange={(e) => handleFilterChange('acknowledged', e.target.value === '' ? null : e.target.value === 'true')}
            >
              <option value="">All</option>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Start Date</label>
            <input
              type="datetime-local"
              className="input"
              value={filters.start_date}
              onChange={(e) => handleFilterChange('start_date', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">End Date</label>
            <input
              type="datetime-local"
              className="input"
              value={filters.end_date}
              onChange={(e) => handleFilterChange('end_date', e.target.value)}
            />
          </div>
        </div>
        <button className="btn btn-primary" onClick={handleSearch} disabled={loading}>
          {loading ? 'Loading...' : 'Search'}
        </button>
      </div>

      <div className="card">
        {loading ? (
          <p>Loading alerts...</p>
        ) : (
          <>
            <div style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <p>Total: {pagination.total} alerts</p>
              <div>
                <button
                  className="btn btn-secondary"
                  onClick={() => handlePageChange(pagination.page - 1)}
                  disabled={pagination.page === 1}
                >
                  Previous
                </button>
                <span style={{ margin: '0 1rem' }}>
                  Page {pagination.page} of {pagination.pages}
                </span>
                <button
                  className="btn btn-secondary"
                  onClick={() => handlePageChange(pagination.page + 1)}
                  disabled={pagination.page >= pagination.pages}
                >
                  Next
                </button>
              </div>
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Container ID</th>
                  <th>Shipping Line</th>
                  <th>Location</th>
                  <th>Status</th>
                  <th>Acknowledged</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {alerts.length === 0 ? (
                  <tr>
                    <td colSpan="7" style={{ textAlign: 'center', padding: '2rem' }}>
                      No alerts found
                    </td>
                  </tr>
                ) : (
                  alerts.map((alert) => (
                    <tr key={alert._id}>
                      <td>
                        {alert.timestamp
                          ? format(new Date(alert.timestamp), 'PPpp')
                          : 'N/A'}
                      </td>
                      <td>{alert.container?.container_id || 'N/A'}</td>
                      <td>{alert.container?.shipping_line || 'N/A'}</td>
                      <td>
                        {alert.location?.name || 'N/A'}
                        {alert.location?.city && `, ${alert.location.city}`}
                      </td>
                      <td>
                        <span className={`badge badge-${alert.container?.status === 'in_transit' ? 'info' : 'warning'}`}>
                          {alert.container?.status || 'N/A'}
                        </span>
                      </td>
                      <td>
                        {alert.acknowledged ? (
                          <span className="badge badge-success">Yes</span>
                        ) : (
                          <span className="badge badge-warning">No</span>
                        )}
                      </td>
                      <td>
                        {!alert.acknowledged && (
                          <button
                            className="btn btn-secondary"
                            onClick={() => handleAcknowledge(alert._id)}
                            style={{ fontSize: '12px', padding: '5px 10px' }}
                          >
                            Acknowledge
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  )
}

export default AlertsGrid

