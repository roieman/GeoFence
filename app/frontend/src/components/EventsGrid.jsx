import React, { useState, useEffect } from 'react'
import { iotEventsAPI, gateEventsAPI, referenceAPI } from '../services/api'

function EventsGrid() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [eventTypes, setEventTypes] = useState([])
  const [activeTab, setActiveTab] = useState('iot') // 'iot' or 'gate'
  const [filters, setFilters] = useState({
    assetname: '',
    TrackerID: '',
    EventType: '',
    EventLocation: '',
    start_date: '',
    end_date: ''
  })
  const [pagination, setPagination] = useState({ page: 1, limit: 50, total: 0, pages: 0 })

  // Load event types
  useEffect(() => {
    referenceAPI.eventTypes()
      .then(res => setEventTypes(res.data.types))
      .catch(err => console.error('Failed to load event types:', err))
  }, [])

  // Load events when filters or tab changes
  useEffect(() => {
    loadEvents()
  }, [filters, pagination.page, activeTab])

  const loadEvents = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { page: pagination.page, limit: pagination.limit }

      // Add non-empty filters
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params[key] = value
      })

      const response = activeTab === 'iot'
        ? await iotEventsAPI.list(params)
        : await gateEventsAPI.list(params)

      setEvents(response.data.events || [])
      setPagination(prev => ({ ...prev, ...response.data.pagination }))
    } catch (err) {
      setError(err.message || 'Failed to load events')
    } finally {
      setLoading(false)
    }
  }

  const handleFilterChange = (e) => {
    const { name, value } = e.target
    setFilters(prev => ({ ...prev, [name]: value }))
    setPagination(prev => ({ ...prev, page: 1 }))
  }

  const clearFilters = () => {
    setFilters({
      assetname: '',
      TrackerID: '',
      EventType: '',
      EventLocation: '',
      start_date: '',
      end_date: ''
    })
  }

  const getEventTypeClass = (eventType) => {
    const type = eventType?.toLowerCase().replace(' ', '-')
    return `event-type-${type}`
  }

  const formatDateTime = (dt) => {
    if (!dt) return '-'
    return new Date(dt).toLocaleString()
  }

  return (
    <div className="events-grid">
      <div className="page-header">
        <h2>Events</h2>
        <div className="tab-buttons">
          <button
            className={`tab-btn ${activeTab === 'iot' ? 'active' : ''}`}
            onClick={() => { setActiveTab('iot'); setPagination(prev => ({ ...prev, page: 1 })) }}
          >
            IoT Events
          </button>
          <button
            className={`tab-btn ${activeTab === 'gate' ? 'active' : ''}`}
            onClick={() => { setActiveTab('gate'); setPagination(prev => ({ ...prev, page: 1 })) }}
          >
            Gate Events
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="filters-panel">
        <div className="filters-row">
          <input
            type="text"
            name="assetname"
            placeholder="Container ID"
            value={filters.assetname}
            onChange={handleFilterChange}
            className="filter-input"
          />
          <input
            type="text"
            name="TrackerID"
            placeholder="Tracker ID"
            value={filters.TrackerID}
            onChange={handleFilterChange}
            className="filter-input"
          />
          <select
            name="EventType"
            value={filters.EventType}
            onChange={handleFilterChange}
            className="filter-select"
          >
            <option value="">All Event Types</option>
            {eventTypes.map(type => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
          <input
            type="text"
            name="EventLocation"
            placeholder="Location"
            value={filters.EventLocation}
            onChange={handleFilterChange}
            className="filter-input"
          />
        </div>
        <div className="filters-row">
          <label className="date-label">
            From:
            <input
              type="datetime-local"
              name="start_date"
              value={filters.start_date}
              onChange={handleFilterChange}
              className="filter-input"
            />
          </label>
          <label className="date-label">
            To:
            <input
              type="datetime-local"
              name="end_date"
              value={filters.end_date}
              onChange={handleFilterChange}
              className="filter-input"
            />
          </label>
          <button onClick={clearFilters} className="btn btn-secondary">
            Clear Filters
          </button>
          <button onClick={loadEvents} className="btn btn-primary">
            Search
          </button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      {/* Results info */}
      <div className="results-info">
        Showing {events.length} of {pagination.total} events
        {activeTab === 'iot' && <span className="collection-type"> (Regular collection)</span>}
      </div>

      {/* Events table */}
      {loading ? (
        <div className="loading">Loading events...</div>
      ) : (
        <div className="table-container">
          <table className="data-table events-table">
            <thead>
              <tr>
                <th>Event Time</th>
                <th>Report Time</th>
                <th>Event Type</th>
                <th>Container</th>
                <th>Tracker</th>
                <th>Location</th>
                <th>Country</th>
                <th>Coordinates</th>
                {activeTab === 'gate' && <th>Geofence</th>}
              </tr>
            </thead>
            <tbody>
              {events.map((event, idx) => {
                const containerId = event.assetname || event.metadata?.assetname
                const trackerId = event.TrackerID || event.metadata?.TrackerID
                const eventTime = event.EventTime || event.timestamp

                return (
                  <tr key={event._id || idx}>
                    <td>{formatDateTime(eventTime)}</td>
                    <td>{formatDateTime(event.ReportTime)}</td>
                    <td>
                      <span className={`event-badge ${getEventTypeClass(event.EventType)}`}>
                        {event.EventType}
                      </span>
                    </td>
                    <td className="container-id">{containerId}</td>
                    <td>{trackerId}</td>
                    <td>{event.EventLocation || 'In Transit'}</td>
                    <td>{event.EventLocationCountry || '-'}</td>
                    <td className="coordinates">
                      {event.Lat && event.Lon
                        ? `${event.Lat.toFixed(4)}, ${event.Lon.toFixed(4)}`
                        : '-'
                      }
                    </td>
                    {activeTab === 'gate' && (
                      <td>{event.geofence_name || '-'}</td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {pagination.pages > 1 && (
        <div className="pagination">
          <button
            disabled={pagination.page <= 1}
            onClick={() => setPagination(prev => ({ ...prev, page: 1 }))}
          >
            First
          </button>
          <button
            disabled={pagination.page <= 1}
            onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
          >
            Previous
          </button>
          <span className="page-info">
            Page {pagination.page} of {pagination.pages}
          </span>
          <button
            disabled={pagination.page >= pagination.pages}
            onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
          >
            Next
          </button>
          <button
            disabled={pagination.page >= pagination.pages}
            onClick={() => setPagination(prev => ({ ...prev, page: pagination.pages }))}
          >
            Last
          </button>
        </div>
      )}
    </div>
  )
}

export default EventsGrid
