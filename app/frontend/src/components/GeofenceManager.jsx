import React, { useState, useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Polygon, Popup, useMap, FeatureGroup, CircleMarker } from 'react-leaflet'
import { geofencesAPI, referenceAPI } from '../services/api'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'leaflet-draw/dist/leaflet.draw.css'
import 'leaflet-draw'

const GEOFENCE_COLORS = {
  'Terminal': '#2196F3',
  'Depot': '#4CAF50',
  'Rail ramp': '#FF9800',
}

// Component to fit map to selected geofence
function FitToGeofence({ geofence }) {
  const map = useMap()

  useEffect(() => {
    if (geofence && geofence.geometry && geofence.geometry.coordinates) {
      const coords = geofence.geometry.coordinates[0]
      if (coords && coords.length > 0) {
        const bounds = coords.map(c => [c[1], c[0]])
        map.fitBounds(bounds, { padding: [50, 50] })
      }
    }
  }, [geofence, map])

  return null
}

// Component to fit map to all geofences
function FitToAll({ geofences, trigger }) {
  const map = useMap()

  useEffect(() => {
    if (trigger && geofences && geofences.length > 0) {
      const allCoords = []
      geofences.forEach(gf => {
        if (gf.geometry && gf.geometry.coordinates && gf.geometry.coordinates[0]) {
          gf.geometry.coordinates[0].forEach(c => {
            allCoords.push([c[1], c[0]])
          })
        }
      })
      if (allCoords.length > 0) {
        map.fitBounds(allCoords, { padding: [20, 20] })
      }
    }
  }, [trigger, geofences, map])

  return null
}

// Calculate centroid of polygon
function getCentroid(geometry) {
  if (!geometry || !geometry.coordinates || !geometry.coordinates[0]) return null
  const coords = geometry.coordinates[0]
  let latSum = 0, lngSum = 0
  coords.forEach(c => {
    lngSum += c[0]
    latSum += c[1]
  })
  return [latSum / coords.length, lngSum / coords.length]
}

// Drawing control component
function DrawControl({ onCreated }) {
  const map = useMap()
  const drawControlRef = useRef(null)
  const featureGroupRef = useRef(null)

  useEffect(() => {
    // Create a feature group to store drawn items
    featureGroupRef.current = new L.FeatureGroup()
    map.addLayer(featureGroupRef.current)

    // Create draw control
    drawControlRef.current = new L.Control.Draw({
      position: 'topright',
      draw: {
        polygon: {
          allowIntersection: false,
          shapeOptions: {
            color: '#2196F3',
            weight: 2
          }
        },
        polyline: false,
        circle: false,
        circlemarker: false,
        marker: false,
        rectangle: false
      },
      edit: {
        featureGroup: featureGroupRef.current,
        remove: false,
        edit: false
      }
    })

    map.addControl(drawControlRef.current)

    // Handle draw created event
    const handleDrawCreated = (e) => {
      const layer = e.layer
      const coords = layer.getLatLngs()[0].map(ll => [ll.lng, ll.lat])
      coords.push(coords[0]) // Close the polygon

      // Clear the drawn layer (we'll save to DB instead)
      featureGroupRef.current.clearLayers()

      onCreated(coords)
    }

    map.on(L.Draw.Event.CREATED, handleDrawCreated)

    return () => {
      map.off(L.Draw.Event.CREATED, handleDrawCreated)
      if (drawControlRef.current) {
        map.removeControl(drawControlRef.current)
      }
      if (featureGroupRef.current) {
        map.removeLayer(featureGroupRef.current)
      }
    }
  }, [map, onCreated])

  return null
}

function GeofenceManager() {
  const [geofences, setGeofences] = useState([])
  const [selectedGeofence, setSelectedGeofence] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filters, setFilters] = useState({ type_id: '', search: '' })
  const [pagination, setPagination] = useState({ page: 1, limit: 50, total: 0 })
  const [mapGeofences, setMapGeofences] = useState([]) // Geofences for map (all matching current filter)
  const [geofenceTypes, setGeofenceTypes] = useState([])
  const [showEditModal, setShowEditModal] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editForm, setEditForm] = useState({})
  const [newGeofenceCoords, setNewGeofenceCoords] = useState(null)
  const [fitAllTrigger, setFitAllTrigger] = useState(0)

  // Load geofence types
  useEffect(() => {
    referenceAPI.geofenceTypes()
      .then(res => setGeofenceTypes(res.data.types))
      .catch(err => console.error('Failed to load geofence types:', err))
  }, [])

  // Load geofences when filters change
  useEffect(() => {
    loadGeofences()
    loadMapGeofences()
  }, [filters])

  // Load table page when page changes
  useEffect(() => {
    loadGeofences()
  }, [pagination.page])

  const loadMapGeofences = async () => {
    try {
      // Load ALL geofences matching current filter (for map display)
      const params = { limit: 2000 }
      if (filters.type_id) params.type_id = filters.type_id
      if (filters.search) params.search = filters.search

      const response = await geofencesAPI.list(params)
      setMapGeofences(response.data.geofences || [])
    } catch (err) {
      console.error('Failed to load map geofences:', err)
    }
  }

  const loadGeofences = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = {
        page: pagination.page,
        limit: pagination.limit,
      }
      if (filters.type_id) params.type_id = filters.type_id
      if (filters.search) params.search = filters.search

      const response = await geofencesAPI.list(params)
      setGeofences(response.data.geofences || [])
      setPagination(prev => ({ ...prev, ...response.data.pagination }))
    } catch (err) {
      console.error('Failed to load geofences:', err)
      setError(err.message || 'Failed to load geofences')
    } finally {
      setLoading(false)
    }
  }

  const handleResetFilters = () => {
    setFilters({ type_id: '', search: '' })
    setPagination(prev => ({ ...prev, page: 1 }))
  }

  const handleFilterChange = (e) => {
    const { name, value } = e.target
    setFilters(prev => ({ ...prev, [name]: value }))
    setPagination(prev => ({ ...prev, page: 1 }))
  }

  const handleGeofenceClick = (geofence) => {
    setSelectedGeofence(geofence)
  }

  const handleEdit = (geofence) => {
    setEditForm({
      _id: geofence._id,
      name: geofence.properties.name,
      description: geofence.properties.description || '',
      typeId: geofence.properties.typeId,
      UNLOCode: geofence.properties.UNLOCode || '',
      SMDGCode: geofence.properties.SMDGCode || '',
    })
    setShowEditModal(true)
  }

  const handleSaveEdit = async () => {
    try {
      await geofencesAPI.update(editForm._id, {
        name: editForm.name,
        description: editForm.description,
        typeId: editForm.typeId,
        UNLOCode: editForm.UNLOCode,
        SMDGCode: editForm.SMDGCode,
      })
      setShowEditModal(false)
      loadGeofences()
      loadMapGeofences()
    } catch (err) {
      alert('Failed to update geofence: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleDelete = async (geofence) => {
    if (!window.confirm(`Delete geofence "${geofence.properties.name}"?`)) return
    try {
      await geofencesAPI.delete(geofence._id)
      loadGeofences()
      loadMapGeofences()
      setSelectedGeofence(null)
    } catch (err) {
      alert('Failed to delete geofence: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleExportCSV = async () => {
    try {
      const response = await geofencesAPI.exportCSV(filters.type_id)
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'geofences.csv')
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      alert('Export failed: ' + err.message)
    }
  }

  const handleExportGeoJSON = async () => {
    try {
      const response = await geofencesAPI.exportGeoJSON(filters.type_id)
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'geofences.geojson')
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      alert('Export failed: ' + err.message)
    }
  }

  const handleImportCSV = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    try {
      const response = await geofencesAPI.importCSV(file)
      alert(`Imported: ${response.data.imported}, Updated: ${response.data.updated}`)
      loadGeofences()
    } catch (err) {
      alert('Import failed: ' + (err.response?.data?.detail || err.message))
    }
    e.target.value = ''
  }

  // Handle polygon drawn on map
  const handlePolygonCreated = (coords) => {
    setNewGeofenceCoords(coords)
    setEditForm({
      name: '',
      description: '',
      typeId: 'Depot',
      UNLOCode: '',
      SMDGCode: '',
    })
    setShowCreateModal(true)
  }

  const handleSaveNewGeofence = async () => {
    if (!editForm.name) {
      alert('Please enter a name for the geofence')
      return
    }

    try {
      await geofencesAPI.create({
        name: editForm.name,
        description: editForm.description,
        typeId: editForm.typeId,
        UNLOCode: editForm.UNLOCode,
        SMDGCode: editForm.SMDGCode,
        geometry: {
          type: 'Polygon',
          coordinates: [newGeofenceCoords]
        }
      })
      setShowCreateModal(false)
      setNewGeofenceCoords(null)
      loadGeofences()
      loadMapGeofences()
    } catch (err) {
      alert('Failed to create geofence: ' + (err.response?.data?.detail || err.message))
    }
  }

  const getPolygonCoords = (geometry) => {
    if (!geometry || !geometry.coordinates || !geometry.coordinates[0]) return []
    return geometry.coordinates[0].map(coord => [coord[1], coord[0]]) // [lat, lng]
  }

  return (
    <div className="geofence-manager">
      <div className="page-header">
        <h2>Geofence Management</h2>
        <div className="header-actions">
          <button onClick={handleExportCSV} className="btn btn-secondary">
            Export CSV
          </button>
          <button onClick={handleExportGeoJSON} className="btn btn-secondary">
            Export GeoJSON
          </button>
          <label className="btn btn-primary">
            Import CSV
            <input type="file" accept=".csv" onChange={handleImportCSV} hidden />
          </label>
        </div>
      </div>

      {/* Instructions */}
      <div className="info-banner">
        <strong>Tip:</strong> Click the polygon icon (pentagon) in the top-right of the map to draw a new geofence.
        Click "Fit to All" to zoom to see all geofences.
        <button
          onClick={() => setFitAllTrigger(t => t + 1)}
          className="btn btn-small btn-primary"
          style={{ marginLeft: '1rem' }}
        >
          Fit to All
        </button>
      </div>

      {/* Filters */}
      <div className="filters-bar">
        <input
          type="text"
          name="search"
          placeholder="Search by name, code..."
          value={filters.search}
          onChange={handleFilterChange}
          className="filter-input"
        />
        <select
          name="type_id"
          value={filters.type_id}
          onChange={handleFilterChange}
          className="filter-select"
        >
          <option value="">All Types</option>
          {geofenceTypes.map(type => (
            <option key={type} value={type}>{type}</option>
          ))}
        </select>
        {(filters.search || filters.type_id) && (
          <button onClick={handleResetFilters} className="btn btn-secondary btn-small">
            Reset
          </button>
        )}
        <div className="results-count">
          <strong>{pagination.total}</strong> geofences in table &bull; <strong>{mapGeofences.length}</strong> on map
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="map-container" style={{ height: '500px' }}>
        <MapContainer
          center={[20, 0]}
          zoom={2}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution='&copy; OpenStreetMap'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <DrawControl onCreated={handlePolygonCreated} />

          {selectedGeofence && <FitToGeofence geofence={selectedGeofence} />}
          <FitToAll geofences={mapGeofences} trigger={fitAllTrigger} />

          {/* Geofence markers (visible at low zoom) - show ALL geofences */}
          {mapGeofences.map(gf => {
            const centroid = getCentroid(gf.geometry)
            if (!centroid) return null
            return (
              <CircleMarker
                key={`marker-${gf._id}`}
                center={centroid}
                radius={6}
                pathOptions={{
                  color: GEOFENCE_COLORS[gf.properties?.typeId] || '#666',
                  fillColor: GEOFENCE_COLORS[gf.properties?.typeId] || '#666',
                  fillOpacity: 0.8,
                  weight: 1
                }}
                eventHandlers={{
                  click: () => handleGeofenceClick(gf)
                }}
              />
            )
          })}

          {/* Geofence polygons - show ALL geofences */}
          {mapGeofences.map(gf => {
            const coords = getPolygonCoords(gf.geometry)
            if (coords.length === 0) return null

            return (
              <Polygon
                key={gf._id}
                positions={coords}
                pathOptions={{
                  color: GEOFENCE_COLORS[gf.properties?.typeId] || '#666',
                  fillOpacity: selectedGeofence?._id === gf._id ? 0.6 : 0.4,
                  weight: selectedGeofence?._id === gf._id ? 4 : 2
                }}
                eventHandlers={{
                  click: () => handleGeofenceClick(gf)
                }}
              >
                <Popup>
                  <div className="geofence-popup">
                    <h4>{gf.properties?.name}</h4>
                    <p><strong>Type:</strong> {gf.properties?.typeId}</p>
                    <p><strong>Description:</strong> {gf.properties?.description || 'N/A'}</p>
                    <p><strong>UNLO:</strong> {gf.properties?.UNLOCode || 'N/A'}</p>
                    <p><strong>SMDG:</strong> {gf.properties?.SMDGCode || 'N/A'}</p>
                    <div className="popup-actions">
                      <button onClick={() => handleEdit(gf)} className="btn btn-small">
                        Edit
                      </button>
                      <button onClick={() => handleDelete(gf)} className="btn btn-small btn-danger">
                        Delete
                      </button>
                    </div>
                  </div>
                </Popup>
              </Polygon>
            )
          })}
        </MapContainer>
      </div>

      {/* Geofence list */}
      <div className="geofence-list">
        <h3>Geofences ({pagination.total})</h3>
        {loading ? (
          <div className="loading">Loading...</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Description</th>
                <th>UNLO Code</th>
                <th>SMDG Code</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {geofences.map(gf => (
                <tr
                  key={gf._id}
                  className={selectedGeofence?._id === gf._id ? 'selected' : ''}
                  onClick={() => handleGeofenceClick(gf)}
                >
                  <td>{gf.properties?.name}</td>
                  <td>
                    <span className={`type-badge type-${gf.properties?.typeId?.toLowerCase().replace(' ', '-')}`}>
                      {gf.properties?.typeId}
                    </span>
                  </td>
                  <td>{gf.properties?.description?.substring(0, 50) || '-'}</td>
                  <td>{gf.properties?.UNLOCode || '-'}</td>
                  <td>{gf.properties?.SMDGCode || '-'}</td>
                  <td>
                    <button onClick={(e) => { e.stopPropagation(); handleEdit(gf) }} className="btn btn-small">
                      Edit
                    </button>
                    <button onClick={(e) => { e.stopPropagation(); handleDelete(gf) }} className="btn btn-small btn-danger">
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Pagination */}
        {pagination.pages > 1 && (
          <div className="pagination">
            <button
              disabled={pagination.page <= 1}
              onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
            >
              Previous
            </button>
            <span>Page {pagination.page} of {pagination.pages}</span>
            <button
              disabled={pagination.page >= pagination.pages}
              onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Edit Modal */}
      {showEditModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>Edit Geofence</h3>
            <form onSubmit={(e) => { e.preventDefault(); handleSaveEdit() }}>
              <div className="form-group">
                <label>Name *</label>
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => setEditForm(prev => ({ ...prev, name: e.target.value }))}
                  required
                />
              </div>
              <div className="form-group">
                <label>Type *</label>
                <select
                  value={editForm.typeId}
                  onChange={(e) => setEditForm(prev => ({ ...prev, typeId: e.target.value }))}
                  required
                >
                  {geofenceTypes.map(type => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={editForm.description}
                  onChange={(e) => setEditForm(prev => ({ ...prev, description: e.target.value }))}
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>UNLO Code</label>
                  <input
                    type="text"
                    value={editForm.UNLOCode}
                    onChange={(e) => setEditForm(prev => ({ ...prev, UNLOCode: e.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label>SMDG Code</label>
                  <input
                    type="text"
                    value={editForm.SMDGCode}
                    onChange={(e) => setEditForm(prev => ({ ...prev, SMDGCode: e.target.value }))}
                  />
                </div>
              </div>
              <div className="modal-actions">
                <button type="button" onClick={() => setShowEditModal(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>Create New Geofence</h3>
            <form onSubmit={(e) => { e.preventDefault(); handleSaveNewGeofence() }}>
              <div className="form-group">
                <label>Name *</label>
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => setEditForm(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g., USNYC-NEW"
                  required
                />
              </div>
              <div className="form-group">
                <label>Type *</label>
                <select
                  value={editForm.typeId}
                  onChange={(e) => setEditForm(prev => ({ ...prev, typeId: e.target.value }))}
                  required
                >
                  {geofenceTypes.map(type => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={editForm.description}
                  onChange={(e) => setEditForm(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="e.g., USA, NEW YORK, New Terminal"
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>UNLO Code</label>
                  <input
                    type="text"
                    value={editForm.UNLOCode}
                    onChange={(e) => setEditForm(prev => ({ ...prev, UNLOCode: e.target.value }))}
                    placeholder="e.g., USNYC"
                  />
                </div>
                <div className="form-group">
                  <label>SMDG Code</label>
                  <input
                    type="text"
                    value={editForm.SMDGCode}
                    onChange={(e) => setEditForm(prev => ({ ...prev, SMDGCode: e.target.value }))}
                  />
                </div>
              </div>
              <div className="modal-actions">
                <button type="button" onClick={() => { setShowCreateModal(false); setNewGeofenceCoords(null) }} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Create Geofence
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default GeofenceManager
