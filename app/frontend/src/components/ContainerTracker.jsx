import React, { useState, useEffect } from 'react'
import { MapContainer, TileLayer, Polyline, Marker, Popup } from 'react-leaflet'
import { containerAPI } from '../services/api'
import { format } from 'date-fns'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'

// Fix for default marker icons in React-Leaflet
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

function ContainerTracker() {
  const [containerId, setContainerId] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  const handleSearch = async () => {
    if (!containerId.trim()) {
      setError('Please enter a container ID')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await containerAPI.track(containerId, startDate, endDate)
      setData(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to fetch container data')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  const getMapCenter = () => {
    if (data?.events?.length > 0) {
      const first = data.events[0]
      if (first.location?.coordinates) {
        return [first.location.coordinates[1], first.location.coordinates[0]]
      }
      if (first.Lat && first.Lon) {
        return [first.Lat, first.Lon]
      }
    }
    return [31.2304, 121.4737] // Default to Shanghai
  }

  const getPolylinePositions = () => {
    if (!data?.events) return []
    return data.events
      .filter(e => e.location?.coordinates || (e.Lat && e.Lon))
      .map(e => {
        if (e.location?.coordinates) {
          return [e.location.coordinates[1], e.location.coordinates[0]]
        }
        return [e.Lat, e.Lon]
      })
  }

  return (
    <div>
      <div className="card">
        <h2>Track Container Movement</h2>
        <div className="form-group">
          <label className="form-label">Container ID</label>
          <input
            type="text"
            className="input"
            value={containerId}
            onChange={(e) => setContainerId(e.target.value)}
            placeholder="Enter container ID (e.g., ABCD1234567)"
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
          />
        </div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Start Date (optional)</label>
            <input
              type="datetime-local"
              className="input"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">End Date (optional)</label>
            <input
              type="datetime-local"
              className="input"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>
        </div>
        <button className="btn btn-primary" onClick={handleSearch} disabled={loading}>
          {loading ? 'Loading...' : 'Track Container'}
        </button>
      </div>

      {error && (
        <div className="card" style={{ backgroundColor: '#fee', border: '1px solid #fcc' }}>
          <p style={{ color: '#c33' }}>{error}</p>
        </div>
      )}

      {data && (
        <>
          <div className="card">
            <h3>Container Information</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
              <div>
                <strong>Container ID:</strong> {data.container_id}
              </div>
              <div>
                <strong>Tracker ID:</strong> {data.events?.[0]?.TrackerID || 'N/A'}
              </div>
              <div>
                <strong>Total Events:</strong> {data.count || data.events?.length || 0}
              </div>
              <div>
                <strong>First Event:</strong> {data.events?.[0]?.EventTime ? format(new Date(data.events[0].EventTime), 'PPpp') : 'N/A'}
              </div>
              <div>
                <strong>Last Event:</strong> {data.events?.length > 0 ? format(new Date(data.events[data.events.length - 1].EventTime), 'PPpp') : 'N/A'}
              </div>
            </div>
          </div>

          <div className="card" style={{ padding: 0, height: '600px' }}>
            <MapContainer
              center={getMapCenter()}
              zoom={data.events?.length > 0 ? 6 : 2}
              style={{ height: '100%', width: '100%' }}
              maxBounds={[[-90, -180], [90, 180]]}
              maxBoundsViscosity={1.0}
              minZoom={2}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                noWrap={true}
              />
              {data.events?.length > 0 && (
                <>
                  <Polyline
                    positions={getPolylinePositions()}
                    color="blue"
                    weight={3}
                    opacity={0.7}
                  />
                  {data.events.map((event, idx) => {
                    const lat = event.location?.coordinates?.[1] || event.Lat
                    const lon = event.location?.coordinates?.[0] || event.Lon
                    if (!lat || !lon) return null

                    const isFirst = idx === 0
                    const isLast = idx === data.events.length - 1

                    return (
                      <Marker
                        key={idx}
                        position={[lat, lon]}
                        icon={L.icon({
                          iconUrl: isFirst
                            ? 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png'
                            : isLast
                            ? 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png'
                            : 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png',
                          shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
                          iconSize: [25, 41],
                          iconAnchor: [12, 41],
                          popupAnchor: [1, -34],
                        })}
                      >
                        <Popup>
                          <div>
                            <strong>{isFirst ? 'Start' : isLast ? 'Latest' : `Point ${idx + 1}`}</strong>
                            <br />
                            Time: {event.EventTime ? format(new Date(event.EventTime), 'PPpp') : 'N/A'}
                            <br />
                            Event: {event.EventType || 'N/A'}
                            <br />
                            Location: {event.EventLocation || 'In Transit'}
                          </div>
                        </Popup>
                      </Marker>
                    )
                  })}
                </>
              )}
            </MapContainer>
          </div>
        </>
      )}
    </div>
  )
}

export default ContainerTracker

