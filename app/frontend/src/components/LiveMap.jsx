import React, { useState, useEffect } from 'react'
import { MapContainer, TileLayer, Polygon, CircleMarker, Popup, useMap } from 'react-leaflet'
import { geofencesAPI, containersAPI, iotEventsAPI } from '../services/api'
import 'leaflet/dist/leaflet.css'

const GEOFENCE_COLORS = {
  'Terminal': '#2196F3',
  'Depot': '#4CAF50',
  'Rail ramp': '#FF9800',
}

const CONTAINER_COLORS = {
  moving: '#4CAF50',
  stopped: '#FF9800',
  in_geofence: '#2196F3',
}

function FitBounds({ bounds }) {
  const map = useMap()
  useEffect(() => {
    if (bounds && bounds.length > 0) {
      map.fitBounds(bounds, { padding: [50, 50] })
    }
  }, [bounds, map])
  return null
}

function LiveMap() {
  const [geofences, setGeofences] = useState([])
  const [containers, setContainers] = useState([])
  const [latestEvents, setLatestEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showGeofences, setShowGeofences] = useState(true)
  const [showContainers, setShowContainers] = useState(true)
  const [showEvents, setShowEvents] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [selectedGeofenceType, setSelectedGeofenceType] = useState('')
  const [stats, setStats] = useState({})

  // Load initial data
  useEffect(() => {
    loadData()
  }, [selectedGeofenceType])

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(loadContainersAndEvents, 5000)
    return () => clearInterval(interval)
  }, [autoRefresh])

  const loadData = async () => {
    setLoading(true)
    try {
      await Promise.all([
        loadGeofences(),
        loadContainersAndEvents()
      ])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const loadGeofences = async () => {
    const params = { limit: 500 }
    if (selectedGeofenceType) params.type_id = selectedGeofenceType
    const response = await geofencesAPI.list(params)
    setGeofences(response.data.geofences)
  }

  const loadContainersAndEvents = async () => {
    try {
      const [containersRes, eventsRes] = await Promise.all([
        containersAPI.positions(),
        iotEventsAPI.latest(100)
      ])
      setContainers(containersRes.data.containers || [])
      setLatestEvents(eventsRes.data.events || [])

      // Calculate stats
      const moving = containersRes.data.containers?.filter(c => c.is_moving).length || 0
      const inGeofence = containersRes.data.containers?.filter(c => c.current_geofence).length || 0
      setStats({
        total: containersRes.data.containers?.length || 0,
        moving,
        stopped: (containersRes.data.containers?.length || 0) - moving,
        inGeofence
      })
    } catch (err) {
      console.error('Failed to refresh data:', err)
    }
  }

  const getPolygonCoords = (geometry) => {
    if (!geometry || !geometry.coordinates || !geometry.coordinates[0]) return []
    return geometry.coordinates[0].map(coord => [coord[1], coord[0]])
  }

  const getContainerColor = (container) => {
    if (container.current_geofence) return CONTAINER_COLORS.in_geofence
    if (container.is_moving) return CONTAINER_COLORS.moving
    return CONTAINER_COLORS.stopped
  }

  const getEventColor = (event) => {
    switch (event.EventType) {
      case 'Gate In': return '#2196F3'
      case 'Gate Out': return '#9C27B0'
      case 'Door Opened': return '#F44336'
      case 'Door Closed': return '#4CAF50'
      case 'In Motion': return '#00BCD4'
      case 'Motion Stop': return '#FF9800'
      default: return '#757575'
    }
  }

  return (
    <div className="live-map">
      <div className="page-header">
        <h2>Live Map</h2>
        <div className="header-stats">
          <span className="stat">
            <span className="stat-value">{stats.total || 0}</span>
            <span className="stat-label">Containers</span>
          </span>
          <span className="stat stat-moving">
            <span className="stat-value">{stats.moving || 0}</span>
            <span className="stat-label">Moving</span>
          </span>
          <span className="stat stat-stopped">
            <span className="stat-value">{stats.stopped || 0}</span>
            <span className="stat-label">Stopped</span>
          </span>
          <span className="stat stat-geofence">
            <span className="stat-value">{stats.inGeofence || 0}</span>
            <span className="stat-label">In Geofence</span>
          </span>
        </div>
      </div>

      {/* Controls */}
      <div className="map-controls">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={showGeofences}
            onChange={(e) => setShowGeofences(e.target.checked)}
          />
          Show Geofences
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={showContainers}
            onChange={(e) => setShowContainers(e.target.checked)}
          />
          Show Containers
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={showEvents}
            onChange={(e) => setShowEvents(e.target.checked)}
          />
          Show Events
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
          />
          Auto Refresh (5s)
        </label>
        <select
          value={selectedGeofenceType}
          onChange={(e) => setSelectedGeofenceType(e.target.value)}
          className="filter-select"
        >
          <option value="">All Geofence Types</option>
          <option value="Terminal">Terminals</option>
          <option value="Depot">Depots</option>
          <option value="Rail ramp">Rail Ramps</option>
        </select>
        <button onClick={loadData} className="btn btn-small">
          Refresh
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="map-container" style={{ height: '600px' }}>
        <MapContainer
          center={[20, 0]}
          zoom={2}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution='&copy; OpenStreetMap'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {/* Geofences */}
          {showGeofences && geofences.map(gf => (
            <Polygon
              key={gf._id}
              positions={getPolygonCoords(gf.geometry)}
              pathOptions={{
                color: GEOFENCE_COLORS[gf.properties.typeId] || '#666',
                fillOpacity: 0.2,
                weight: 1
              }}
            >
              <Popup>
                <strong>{gf.properties.name}</strong><br />
                Type: {gf.properties.typeId}<br />
                {gf.properties.description}
              </Popup>
            </Polygon>
          ))}

          {/* Container positions */}
          {showContainers && containers.map(c => (
            c.latitude && c.longitude && (
              <CircleMarker
                key={c.container_id}
                center={[c.latitude, c.longitude]}
                radius={8}
                pathOptions={{
                  color: getContainerColor(c),
                  fillColor: getContainerColor(c),
                  fillOpacity: 0.8
                }}
              >
                <Popup>
                  <strong>{c.container_id}</strong><br />
                  Tracker: {c.tracker_id}<br />
                  State: {c.state}<br />
                  {c.is_moving ? '🚚 Moving' : '⏸️ Stopped'}<br />
                  {c.current_geofence && `📍 At: ${c.current_geofence}`}
                </Popup>
              </CircleMarker>
            )
          ))}

          {/* Latest events */}
          {showEvents && latestEvents.slice(0, 50).map((e, idx) => (
            e.Lat && e.Lon && (
              <CircleMarker
                key={`event-${idx}`}
                center={[e.Lat, e.Lon]}
                radius={5}
                pathOptions={{
                  color: getEventColor(e),
                  fillColor: getEventColor(e),
                  fillOpacity: 0.6,
                  weight: 1
                }}
              >
                <Popup>
                  <strong>{e.EventType}</strong><br />
                  Container: {e.assetname || e.metadata?.assetname}<br />
                  Location: {e.EventLocation || 'In Transit'}<br />
                  Time: {new Date(e.EventTime || e.timestamp).toLocaleString()}
                </Popup>
              </CircleMarker>
            )
          ))}
        </MapContainer>
      </div>

      {/* Legend */}
      <div className="map-legend">
        <h4>Legend</h4>
        <div className="legend-section">
          <h5>Geofences</h5>
          {Object.entries(GEOFENCE_COLORS).map(([type, color]) => (
            <div key={type} className="legend-item">
              <span className="legend-color" style={{ backgroundColor: color }}></span>
              {type}
            </div>
          ))}
        </div>
        <div className="legend-section">
          <h5>Containers</h5>
          <div className="legend-item">
            <span className="legend-color" style={{ backgroundColor: CONTAINER_COLORS.moving }}></span>
            Moving
          </div>
          <div className="legend-item">
            <span className="legend-color" style={{ backgroundColor: CONTAINER_COLORS.stopped }}></span>
            Stopped
          </div>
          <div className="legend-item">
            <span className="legend-color" style={{ backgroundColor: CONTAINER_COLORS.in_geofence }}></span>
            In Geofence
          </div>
        </div>
      </div>

      {/* Recent events list */}
      <div className="recent-events">
        <h3>Recent Events ({latestEvents.length})</h3>
        <div className="events-list">
          {latestEvents.slice(0, 20).map((e, idx) => (
            <div key={idx} className={`event-item event-${e.EventType?.toLowerCase().replace(' ', '-')}`}>
              <span className="event-type">{e.EventType}</span>
              <span className="event-container">{e.assetname || e.metadata?.assetname}</span>
              <span className="event-location">{e.EventLocation || 'In Transit'}</span>
              <span className="event-time">
                {new Date(e.EventTime || e.timestamp).toLocaleTimeString()}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default LiveMap
