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
    if (data?.movements?.length > 0) {
      const first = data.movements[0].location.coordinates
      return [first[1], first[0]] // [lat, lon]
    }
    return [31.2304, 121.4737] // Default to Shanghai
  }

  const getPolylinePositions = () => {
    if (!data?.movements) return []
    return data.movements
      .filter(m => m.location?.coordinates)
      .map(m => {
        const [lon, lat] = m.location.coordinates
        return [lat, lon]
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
                <strong>Shipping Line:</strong> {data.metadata?.shipping_line || 'N/A'}
              </div>
              <div>
                <strong>Type:</strong> {data.metadata?.container_type || 'N/A'}
              </div>
              <div>
                <strong>Refrigerated:</strong> {data.metadata?.refrigerated ? 'Yes' : 'No'}
              </div>
              <div>
                <strong>Cargo Type:</strong> {data.metadata?.cargo_type || 'N/A'}
              </div>
              <div>
                <strong>Total Readings:</strong> {data.total_readings}
              </div>
            </div>
          </div>

          <div className="card" style={{ padding: 0, height: '600px' }}>
            <MapContainer
              center={getMapCenter()}
              zoom={data.movements?.length > 0 ? 8 : 2}
              style={{ height: '100%', width: '100%' }}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {data.movements?.length > 0 && (
                <>
                  <Polyline
                    positions={getPolylinePositions()}
                    color="blue"
                    weight={3}
                    opacity={0.7}
                  />
                  {data.movements.map((movement, idx) => {
                    if (!movement.location?.coordinates) return null
                    const [lon, lat] = movement.location.coordinates
                    const isFirst = idx === 0
                    const isLast = idx === data.movements.length - 1
                    
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
                            <strong>{isFirst ? 'Start' : isLast ? 'End' : `Point ${idx + 1}`}</strong>
                            <br />
                            Time: {movement.timestamp ? format(new Date(movement.timestamp), 'PPpp') : 'N/A'}
                            <br />
                            Status: {movement.status || 'N/A'}
                            {movement.speed_knots && (
                              <>
                                <br />
                                Speed: {movement.speed_knots.toFixed(1)} knots
                              </>
                            )}
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

